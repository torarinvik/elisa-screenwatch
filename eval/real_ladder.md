# V3.6 — the real-video ladder (orchestra_v3_plan.md §7 gold on real footage)

Does the V3.0/V3.1 gated tracker behave correctly on REAL video, measured (not just annotation-free)?
Date 2026-07-14. Held-out protocol intact: LSL2 / Carlsen / Lin-Moregard / CS2 are **not opened here**.

## Load-bearing finding: the census fixtures are not gold-able (offset problem)

The 8-video restraint census (`restraint_census.md`) sampled each video at a single mid-video offset to
characterize *failure-mode diversity* — and it did that job. But those exact clips do NOT contain the
phenomena a tracker LADDER must probe, because the offsets landed on phenomenon-poor moments:

- **PoP census clip = the INTRO.** `batch_0` is a "Loading...." screen; `batch_5` is the title card
  ("a game by Jordan Mechner"). So the census's "PoP 107 tracks" was tracking an animated **title
  screen**, not a game protagonist. (The busy-title-screen IS a valid association-churn stress — the
  census sub-mode B stands — but it is not a protagonist-tracking gold fixture.)
- **Go census clip = a THINKING PAUSE.** `batch_0` and `batch_5` are byte-for-byte the same board at
  move "44" — no stones are placed in the 20 s window, so there are **no stone-appear events** to run
  the omission probes against.

**Consequence:** a real ladder rung requires RE-INGESTING each video at a phenomenon-rich offset (found
by seeking the source), then sparse visual gold per §7 — this is the labor §7 schedules, and it must be
done per rung. It is NOT a defect in the gate; it is how the fixtures were sampled.

## PoP rung — real gameplay (re-ingested t0=150 s, 30 s, `--fps 10 --width 192`)

Seeking the source to gameplay (t≈150 s) gives the intended fixture: the prince, a single medium sprite,
running through dungeon rooms with pillars, doorways, and two flickering torches. Keyframes inspected
(`batch_0..1`): the prince runs **RIGHT** through room 1 toward the door, then a **scene cut** to the
next room (~batch 3-4). Gold authored from the keyframes BEFORE reading tracker output:

| probe | gold | tracker result | verdict |
|---|---|---|---|
| a moving character is present | yes | 74 tracks incl. persistent movers | ✅ |
| dominant-mover direction, room 1 [0–4 s] | right | id=15 net **+9 (right)**, the only non-static mover | ✅ |
| fabricated REVERSE claims (no observed reversal in the run) | 0 | **RE = 0, revHiVx = 0** | ✅ |
| motion within physical bounds | yes | peak \|vx\| = **6** (prince-scale, slow) | ✅ |

**The gate is restrained on real gameplay.** Zero fabricated reverses, prince-scale velocity, and the
prince's rightward run is the tracker's dominant early mover. The residual churn (74 tracks, 111
REACQUIRE, 125 OCCLUDED, 4.2/s) comes from **pillars (real occlusions)** and **room cuts** (a known
limit — the plan schedules cut-detection); crucially **80 merge ambiguities are flagged as `INF dispute`
(V3.2), not silently stolen**. This is a light gold set (a scene cut and coarse 2 s keyframes bound how
much can be pinned), but every authored probe passes and nothing is fabricated.

## Honest scope of the rest of the ladder

- **pharo restraint rung** is already scored annotation-free in `v30_gate_acceptance.md` (false-REVERSE
  5→0, evidence retained) — that IS the pharo rung's core probe; the gold-based UI-activity-classification
  fraction still awaits authored phase/OCR gold.
- **Police / Go / fencing rungs** each need the same re-ingest-at-phenomenon + sparse-gold pass PoP got
  (Go specifically needs a segment where moves are actually played, not a thinking pause).
- **GRADUATION (LSL2)** remains untouched by protocol — opened once, at graduation, with gold authored
  at that time. Not done here, correctly.

The measured takeaway that generalizes beyond one fixture: on the one real-gameplay segment gold-checked
so far, the V3.0/V3.1 gate makes the tracker **restrained and honest** (no fabricated motion, ambiguity
disclosed) rather than confidently wrong — the same result the annotation-free 8-video census showed,
now corroborated against ground truth on moving real footage.
