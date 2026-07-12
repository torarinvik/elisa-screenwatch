# Eval — the scenario battery & memory scoring

`score.py` grades the symbolic ACTIVITY triage. `score_memory.py` grades the **neural** member:
given a scripted scenario with known ground truth, did the watcher's 3-tier memory actually capture
what happened — accurately, in order, without making things up, and while staying compact? That is
the research thesis made measurable.

## How a scenario run works

```
              produce                 watch                    score
 scene ───────────────▶ stream + archive ──────▶ memory + answers ──────▶ metrics
 (truth authored        (batch_*.txt, arch_*)   (state/log/story.md,      (score_memory.py)
  with the scene)                                 answers.jsonl)
```

1. **Produce** the stream. Two sources, same downstream format (both drive `encoder.elisa`):
   - *scripted-real*: a driver drives a real app through known phases and the real `frame_dump`
     records it (like `session_terminal.command`). Ground truth = the driver script.
   - *synthetic* (`scenegen`): render a scripted scene through the **real encoder** so frames are
     pixel-exact and reproducible. Needed for the controlled scenarios (counter, brief object,
     occlusion, invisible-event) where a real app can't hit the timing precisely.
     `scenegen <scene> <out_dir> [width] [fps] [dur_ms]` — e.g. `scenegen counter /tmp/run 192 10
     20000`. Scene timings MUST match the authored `truth.jsonl`.
2. **Watch.** Point a watcher agent at the stream + `watcher_protocol.md`. It writes the memory
   tiers and, at each probe's `ask_t`, answers that probe **from memory only** (no re-reading the
   stream) into `answers.jsonl`. Probing-from-memory is the crux: it tests the memory, not the OCR.
3. **Score.** `score_memory.py <run_dir>` compares `answers.jsonl` + `log.md` against `truth.jsonl`
   + `probes.jsonl`.

A run directory holds: `truth.jsonl`, `probes.jsonl` (authored), the recorded `batch_*.txt` /
`arch_*` (produced), and `answers.jsonl` / `log.md` / `runstats.json` (from the watch). The authored
`truth.jsonl` + `probes.jsonl` for each scenario live under `eval/scenarios/<name>/` and are copied
into the run dir.

## Files & formats

`truth.jsonl` — one JSON object per line:
```
{"type":"phase","t0":0,"t1":2000,"label":"counter shows 0","activity":"typing"}
{"type":"fact","t0":6000,"t1":8000,"key":"counter","value":"3"}
{"type":"event","t":6000,"id":"e3","desc":"counter incremented to 3","object":"o1"}
```
`probes.jsonl` — questions with gold answers and a matcher:
```
{"id":"p5","ask_t":7000,"kind":"perception","q":"What digit is shown?","gold":"3","match":"numeric","fact_t":6000}
```
- `kind`: `perception` (now), `retention` (a fact established long before `ask_t`), `occlusion`
  (a fact hidden at `ask_t`), `event` (did a specific thing happen?).
- `match`: `numeric` | `boolean` | `substring` | `exact`.
- `fact_t`: when the probed fact was established; `ask_t - fact_t` is the memory age used for
  retention. `answers.jsonl` = `{"id":"p5","answer":"3"}`; an answer of `"unknown"` is an honest
  miss and is **never** scored as a confabulation.

## Metrics (`score_memory.py`)

| metric | question it answers | good |
|---|---|---|
| perception_accuracy | did probes get the right answer at the time? | high |
| memory_retention | are old facts (age > `--retain-age`, default 20s) still answered right? | high |
| event_order | are logged events in the right order vs truth? (tau-like on matched events) | high |
| confabulation_rate | of everything the watcher asserted, how much was fabricated? | **low** |
| reconstruction | does `arch_tool verify` pass on the run's ring? (symbolic) | 1.0 |
| tokens / latency | cost of watching the whole run (from `runstats.json`) | low |

`score_memory.py --selftest` builds a fixture with known metrics and asserts the math (CI guard).

## The battery

Each scenario targets one failure mode. `src` = how it's produced (`real` now, `synth` = 5b).

| # | scenario | src | targets | key probes |
|---|----------|-----|---------|-----------|
| 1 | small-text | real | grid+OCR legibility of fine text | perception: read a small label verbatim |
| 2 | scrolling-code | real | SHIFT tracking; identity through scroll | event: "did line X pass?"; perception: current top line |
| 3 | game-motion | synth | tracking under `video`-class churn | perception: where is the moving sprite? |
| 4 | brief-object | synth | transient visible only K frames | event: "did a red box appear?"; occlusion after |
| 5 | one-digit-counter | synth ✓ | small localized perception + change | perception at several t; retention of an early value |
| 5t | counter-skip (trap) | synth ✓ | perceiving vs GUESSING | perception at batches 3,7 where the pattern breaks (7 and 3, swapped) |
| 6 | occlusion | synth | object persistence behind a dialog | occlusion: "what's behind it?"; perception after reveal |
| 7 | invisible-to-log-event | synth | change below symbolic churn thresholds | event: caught only via re-ground/OCR, not the delta |
| 8 | long-session-consolidation | real | retention + compactness over many episodes | retention of episode-1 facts at episode-N; story.md ≤ cap |

Confabulation is scored across ALL scenarios — every probe and every logged event is an assertion,
so a watcher that pattern-matches instead of perceiving is penalised everywhere, not just on a
"confabulation scenario". The honest-unknown carve-out is deliberate: we want a watcher that says "I
can't tell" over one that guesses, and the metric rewards exactly that.

## Findings from dogfooding the harness

- **Truth must be COMPLETE.** A first counter run scored 27.8% confabulation because the authored
  truth listed events only for odd increments; the watcher correctly logged every increment and was
  penalised for the ones truth omitted. Author every real event, or the metric conflates
  "unverified assertion" with "truth incompleteness". With complete truth the same run scores 0%.
- **Regular patterns don't test inference-confabulation.** The counter watcher *inferred* 5 of the
  10 digits ("inferred from counter pattern") instead of reading them, and scored perfectly because
  the pattern held. The **`counter-skip`** trap (sequence `0,1,2,7,4,5,6,3,8,9`, batches 3 & 7
  swapped) tests guessing-vs-perceiving directly: a pattern-inferrer answers 3/7 at the traps, a
  reader answers 7/3. Result — with a **neutral prompt** (no "counter"/"increment" priming) the
  watcher READ every digit including the swaps, refuted the "clean count" hypothesis, and scored
  perception 100 / retention 100 / event-order 100 / confab 5.3%. Prompt wording matters: the clean
  counter's inference shortcut vanished once the prompt stopped implying a pattern.
- **The event matcher must use salient values, not just text.** counter-skip first mis-scored 52.6%
  confab because the watcher's verbose events (`digit "7" drawn (top bar + diagonal…)`) didn't
  text-match terse truth (`display changes to 7`) despite identical timestamp + digit. Fix: floor
  event similarity to a match when the two share a number token. That dropped it to 5.3% (the
  residual is one TRUE meta-note — a hypothesis-refutation — that isn't a truth *event*; log meta in
  state.md's belief-history, not log.md, or accept the small over-count).
- Baselines (one watcher each): counter 100/100/100/0 ; counter-skip 100/100/100/5.3 ;
  reconstruction 100 on both. Reference points, not claims about all scenarios.
