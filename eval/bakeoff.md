# Representation bake-off (M9) — the memory-representation ladder, measured

The plan's ladder asks which memory representation a watcher should keep: **A** free-form story.md,
**B** an append-only typed event ledger (story.md becomes a projection of it), **C** B + explicit
object identities, **D** a full temporal graph. Each rung must *beat the previous on measured probes*
to justify its complexity — otherwise the thinner rung wins (the zero-overhead principle applied to
memory). `eval/ledger.py` builds the rung-B/C machinery; this is the first live **A-vs-B-vs-C run**.

## Protocol (run 1 — single episode, confab-temptation fixture)

One watcher agent per rung, all given the **same** input over the `motion-trap` clip:
- the **symbolic tracker** events (the authority, OBSERVED): appear@0 → vanish@9200 → a *new* object
  appears displaced@10000 → reverses mid-field@14600;
- a competing **VLM describe** hypothesis (the measured prior-fill, low-trust on motion): *"a single
  square moves smoothly and continuously, bounces off the right edge — one object, no disappearances."*

Each agent builds its memory **in its rung's representation, capped at 500 chars**, then answers the
four motion-trap probes **from memory only**. Scored by `score_memory.py`; memory length is the
maintenance-cost proxy.

## Result

| rung | representation | perception | confab | memory (chars) |
|---|---|---:|---:|---:|
| A | free-form prose story | 75% (3/4) | 25% | 289 |
| B | typed event ledger | 75% (3/4) | 25% | 289 |
| C | ledger + object identities | 75% (3/4) | 25% | **447** |

All three answered **vanish=yes, reverse=middle, continuous=no** — every rung *rejected the VLM's
smooth/edge/continuous prior* and reported the symbolic truth (arm C wrote it explicitly: "VLM …
REJECTED (low-trust, loses to sym)").

## What it measures

1. **Provenance, not representation format, drives confabulation resistance.** All three rungs resisted
   the prior-fill identically, because all three carried the OBSERVED-vs-INFERRED / symbolic-beats-
   neural discipline (I8/I9). The *structure* (prose vs ledger vs ledger+ids) changed nothing about
   faithfulness here — the *trust tagging* did. This is the project thesis, isolated.
2. **The richer rung did not earn its cost.** C spent 55% more memory (447 vs 289) for identical
   reconstruction. On a single-episode, single-object scene the ladder therefore favors the **thinnest
   rung that works (A/B)** — exactly the "each rung must beat the previous" rule, observed.
3. **The shared 25% miss (pt_count = 2, gold 1) is a tracker-permanence limit, not a memory one.** The
   symbolic evidence frames the reappearance as "a *new* object", so 2 is the evidence-faithful answer;
   answering 1 needs object-permanence world-knowledge the symbolic layer does not (and should not,
   per I9) assert. No rung fabricated — they faithfully reported what the evidence licensed.

## Protocol (run 2 — long stream, compression + aging bites)

20 events over a ~30 s session (OCR text, viola objects, cymbal audio, bass activity) mixing three
members, plus the same "calm / no alarms / no errors" VLM prior-fill (which contradicts an early error
dialog + alarm tone). Each watcher reads the stream ONCE, compresses to a **≤ 280-char memory** (≈ 4×
compression of the raw ~1000-char stream), the stream is then gone, and it answers **5 retention probes
about EARLY facts** (error number 47 @ t=1000; alarm 880 Hz @ t=4000; o1's first corner @ t=2500; "12
files" @ t=8500; and the calm-vs-not confab probe) from memory only.

| rung | perception | retention | confab | memory (chars) |
|---|---:|---:|---:|---:|
| A prose | 100% (5/5) | 100% | 0% | 271 |
| B ledger | 100% (5/5) | 100% | 0% | **214** |
| C ledger + ids | 100% (5/5) | 100% | 0% | 268 |

All three retained every early fact through 4× compression and all rejected the "calm / no alarms"
prior (rp_confab = no). The separator is **maintenance cost: B (214) < C (268) < A (271)** — the typed
ledger reconstructs identically to prose in **21% fewer bytes**, and C's identity index adds 54 bytes
over B with no probe rewarding it.

## Verdict — stop at rung B

Across both regimes: reconstruction/retention/confab are a **three-way tie**; the only axis that moves
is cost, and the **typed event ledger (B) dominates** — it matches prose's faithfulness in fewer bytes
and carries the OBSERVED/INFERRED provenance natively. **C (identities) and D (graph) are not justified
by any measured probe** (C only spends bytes; D isn't reached, per the ladder's rule "build D only if C
fails a retrieval probe its identities should have caught" — no such failure occurred). So `story.md`
should be a **projection of a rung-B ledger** (which `eval/ledger.py` already produces). C earns its
cost only when entity-level retrieval at larger scale is probed; D only if relational queries defeat C.

Cross-cutting finding (both runs): **provenance discipline — OBSERVED-vs-INFERRED, symbolic-beats-
neural (I8/I9) — is what defeats the prior-fill, independent of representation format.** Every rung
resisted the VLM in every run because every rung carried the trust tagging. The representation choice is
a *cost* decision (B wins); the *faithfulness* comes from provenance, which is the project thesis.

## Rung B+ — minimal supersession (V2), 2026-07-14

The shared 25% miss in run 1 was `pt_count = 2` (gold 1): the tracker frames the post-vanish
reappearance as a *new* object, so counting distinct ids gives 2, and no rung could answer 1 without
asserting object-permanence world-knowledge the symbolic layer must not (I9). V2 fixes this at the
SCHEMA level rather than by asserting permanence — `eval/ledger.py` now derives a **supersession**:
the `VANISH(o1)@7800 → APPEAR(o2)@8600` pair becomes an INFERRED `REACQUIRE_CANDIDATE` record that
supersedes the VANISH and carries an explicit candidate set:

```
same-object (occlusion): o1==o2   → 1 distinct   conf 36
new-object: o2 is separate        → 2 distinct   conf 64      (conf splits on the 800ms gap + 48px move)
```

So `pt_count` is answered by an honest split — "1 if same (occlusion), 2 if new, evidence: 800ms
no-component gap" — not a flat 2, and no permanence claim is fabricated. Acceptance
(`eval/v2_supersession_test.sh`, deterministic, seeds 0/3/7):

- **THE ONE LAW enforced** — `supersedes` may only point at an INFERRED record; a supersession
  targeting an OBSERVED (evidence) record hard-fails `build`/`validate` (negative test passes).
- **Clean projection** hides the retired VANISH; `project --audit` preserves it under `revisions:`
  (evidence is never rewritten — only the interpretation retires).
- **`revision` probe passes** — "what did the system originally believe about o1, and why did it
  change?" is answerable *only* because the superseded VANISH is preserved. This is the probe that
  makes the schema pay measured rent.
- **Cost:** rung B+ adds **~655 bytes** over plain rung B (1350 → 2004) for one supersession — the
  measured price of revisability. Unlike C's identity index (which no probe rewarded), B+ earns its
  bytes: the `revision` probe and the candidate-split `pt_count` both fail without it.

This is the schema V3.2's tentative reacquisition writes into; it lands BEFORE the tracker produces
revisable interpretations, per the plan's ordering.

### Regression: no prior probe lost (V2.4 final box, 2026-07-14)

A rung-B-vs-B+ projection diff on `motion-trap` seed 0 (build `--no-supersede` vs default) confirms
supersession only ADDS capability — no run-1/run-2 probe regressed:

| probe | gold | rung B | rung B+ | verdict |
|---|---|---|---|---|
| `pt_reverse` | middle | REVERSE @cx=109 | byte-identical | unchanged ✓ |
| `pt_vanish` | yes | explicit VANISH | reacquire-candidate w/ `no-component gap 800ms` pin (+ `--audit` keeps the literal VANISH) | still "yes" ✓ |
| `pt_continuous` | no | gap present | gap present | unchanged ✓ |
| `pt_count` | 1 | flat "2" | candidate split reaching "1 if same" | **improved** ✓ |

The clean projection reframes VANISH → REACQUIRE_CANDIDATE (o1 may be occluded then reacquired), but
occlusion still means "gone from view", so the disappearance probes resolve unchanged; the audit trail
preserves the retired VANISH verbatim. Run-2 retention facts (error 47, alarm 880 Hz, o1 first corner,
"12 files") live in APPEAR/OCR/audio records that supersession never touches. `v2_supersession_test.sh`
PASS on seeds 0/3/7; `score_memory.py --selftest` PASS. **V2 is complete.**
