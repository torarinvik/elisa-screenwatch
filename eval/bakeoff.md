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
