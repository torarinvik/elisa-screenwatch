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

## Honest scope + next run

This is one episode with four events; it cannot separate A from B, because compression and aging do not
yet bite. The ladder's predicted payoff — B/C preserving aged facts and provenance under a tight cap
where prose (A) blurs — needs a **long multi-episode stream** (many events, memory cap << total
content, probes on early facts asked much later). That larger run, plus rung D (graph) only if C first
fails a retrieval probe C's identities should have caught, is the remaining M9 work. Rung-B/C machinery
(`eval/ledger.py`) and this harness are in place for it.
