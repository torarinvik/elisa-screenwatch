# Screen-watcher protocol v2

The watcher (the orchestra's *singer*) is a cheap, short-lived LLM agent that reads the
delta-encoded batch stream and maintains an *external* understanding of the screen. The
external memory is the point: a watcher session is ephemeral, but its understanding survives
in files, so cheap watchers can be rotated over an unbounded stream. System contracts
(stream format, ownership, invariants) live in SPEC.md; this file is the singer's playbook.

## Files the singer touches

| Path | Discipline |
|------|-----------|
| `/tmp/screen_batches/latest.txt`, `batch_<n>.txt`, `batch_<n>.ocr.txt` | read |
| `/tmp/screen_watch/goal.md` | read — defines what matters |
| `/tmp/screen_watch/state.md` | **rewrite every cycle**, ≤ 2 KB |
| `/tmp/screen_watch/log.md` | **append-only**, event boundaries only |
| `/tmp/screen_watch/escalation.md` | overwrite when blocked on a question |

Write disciplines are load-bearing: rewriting `state.md` under its cap IS the forgetting
mechanism; `log.md` grows only at event boundaries, every line carrying an evidence pointer
(`[batch <b> f<i> rows <a>-<b>]`). Forget representation, not evidence — claims live in the
log, pixels live in the retained batch files.

## The cycle

1. **Inherit.** Read `goal.md` (relevance), `state.md` (prior watcher's understanding),
   `log.md` tail. Cold start if absent — note it.
2. **Poll.** Read `latest.txt`; if unchanged, sleep ~2s and re-poll. Note skipped-batch gaps.
3. **Triage-gate.** Read only the batch's first 3 lines (BATCH/STATS/ACTIVITY) first.
   `ACTIVITY still` with high conf → update `Seen` in state.md and stop — do NOT read the
   frames. Most cycles should cost near-zero tokens.
4. **Perceive (non-still batches).** Read `batch_<n>.ocr.txt` FIRST if present — real text
   beats inferred shapes; quote OCR strings as Observed. Then the keyframe for layout, then
   deltas as motion evidence (`SAME` runs = still; `ROWS` clusters = localized activity;
   `SHIFT` = scroll; mid-batch `KEYFRAME`/`rate>1` = heavy change).
5. **Revise, don't append.** Rewrite `state.md` (template below). Change contradicted
   beliefs in place; keep a one-line belief history so rejected hypotheses can't return.
6. **Re-ground** every 10th batch OR when confidence < 60%: rebuild `Now` from the current
   keyframe+OCR alone, ignoring inherited beliefs; diff against the story; log corrections.
7. **Consolidate.** At an event boundary only, append ONE line to `log.md` with a pointer.
8. **Escalate** when a goal-relevant question is beyond reach (needs zoom, needs pruned
   history): overwrite `escalation.md` with the question + evidence pointer + why it matters.
   Then continue — never stall the stream.

## state.md template (≤ 2 KB)

```markdown
# Screen state — updated batch <b> (t=<ms>)
Goal: <one-line echo of goal.md>

## Now
- Window/app: …   - Activity: …   - Notable: …

## Observed vs inferred
- Observed: <pixels/OCR facts>    - Inferred: <interpretation + confidence>
- Unknown: <what you can't tell>

## Hypothesis
<current best explanation>
Belief history: <rejected → current, one line>

## Open questions
- …

## Seen
Last batch: <b> | watchers: <n>
```

## log.md entry format

```
t=<ms> — <one-sentence consolidated event>  [batch <b> f<i>]
```

## escalation.md format (mailbox to the boss)

```markdown
# Escalation — batch <b>
question: <one specific question>
evidence: [batch <b> f<i> rows <a>-<b>]
why: <one line tying it to the goal>
```

## Boss playbook (the orchestrator; a stronger model, woken by escalation.md changes)

1. Read goal.md, state.md, log.md, escalation.md.
2. If goal-relevant: formulate ≤ 2 SPECIFIC questions → write `queries/q_<id>.md` per SPEC.md
   → dispatch a cheap sub-watcher per query.
3. On answers: append a boss-attributed consolidation to log.md; update goal.md sub-goals if
   warranted; clear the escalation.
4. Hard stops: ≤ 3 queries per escalation; `evidence-exhausted`/`pruned` answers go to
   state.md's Unknown and are never re-asked for the same event. "Do I understand fully?"
   is never the loop condition — "is this question answered or the budget spent?" is.

## Sub-watcher playbook (executes one query)

Read the query file; execute by type (SPEC.md): temporal = close-read the pointed batch
range; spatial = read only the pointed keyframe rows; zoom = map rows→pixels via SPEC.md's
formula and run `screenocr batch_<b>.jpg --crop x,y,w,h`. Write `q_<id>.answer.md` with
status answered / evidence-exhausted / pruned, the finding (observed/inferred separated),
and fresh evidence pointers. Do nothing else — no state.md writes.
