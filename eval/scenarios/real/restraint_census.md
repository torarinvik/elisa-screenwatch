# Multi-video restraint census — V3.0 generalization evidence

Pre-work for `orchestra_v3_plan.md` V3.0 (evidence-gathering, not repair). Date: 2026-07-14.
Motivation: the pharo t=14 inspection found ONE restraint-failure sub-mode (the mouse cursor). A gate
designed on pharo alone would overfit to it. This censuses 8 videos across the plan's tiers so the
gate is built on the DIVERSITY of failure modes. **LSL2 is NOT here — it is held out for graduation.**

Tool: `eval/restraint_census.py` (annotation-free; reads the tracker's own stdout). Each row is a 20 s
clip at `--fps 10`, sampled mid-video (`--t0`) to skip intros. Metrics: track count; event mix
(APpear/VAnish/OCcluded/REverse/reacQuire); birth/death churn per second; per-track median component
area class tiny(<30)/small/large; peak |vx| (grid-px per 100 ms frame; grid is 192 wide); REVERSEs
emitted while |vx| was non-physical (≥35); and the pharo signature **soleSmallMover%** (frames whose
only non-static-bar component is a single tiny blob).

## The census

| video | tier | tracks | churn/s | OC | RE | RQ | area t/s/l | peak\|vx\| | revHiVx | soleSmall |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| pharo   | R1 IDE        |  22 |  2.0 |   3 |   4 |   6 | 18/0/4   |  64 |  3 | **89%** |
| go      | R2 board      |   9 |  0.6 |   1 |   0 |   0 | 7/0/2    |   4 |  0 | 0% |
| lsl1    | R1 adventure  |  25 |  2.3 |   7 |   2 |   8 | 16/7/2   |   8 |  0 | 0% |
| fencing | R3 sport      |  71 |  3.9 |  71 |   6 |  31 | 35/15/21 |  26 |  0 | 0% |
| police  | R1 top-down   |  83 |  5.2 | 144 |  12 | 116 | 58/21/4  |  59 |  1 | 0% |
| PoP     | R1 platformer | 107 |  7.5 |  97 |  13 |  45 | 74/28/5  |  60 |  2 | 1% |
| boxing  | (real sport)  | 123 |  9.1 | 153 | 154 | 227 | 101/18/4 | **103** | **26** | 0% |
| cs2     | (FPS)         | 144 | 11.3 | 102 |  67 | 142 | 84/47/13 | **164** | **18** | 0% |

## Four distinct restraint sub-modes — the gate needs a leg for each

**A. UI pointer (pharo).** `soleSmallMover=89%`, unique by an order of magnitude (next is PoP at 1%).
Almost every frame is one tiny mover over full-width static chrome — the cursor. Correct restraint:
**suppress**. Discriminator: soleSmallMover / applicability, exactly as the t=14 inspection concluded.
Motion tests miss it (the cursor moves smoothly); an applicability test catches it.

**B. Association churn (PoP, police, fencing).** Many tracks (71–107), high churn (3.9–7.5/s), very
high OCCLUDED/REACQUIRE (fencing 71 OC; police 144 OC / 116 RQ), but **moderate** velocity and near-zero
revHiVx. The failure is components splitting/merging/relosing across textured backgrounds and sprite
overlap — *not* implausible motion. Real objects ARE present (the fencers, the sprite), so the gate
must **cut churn without suppressing them** — this is the association-margin / birth-death-rate leg,
and the one where a too-aggressive area/velocity gate would do harm.

**C. Implausible-velocity smear (boxing, cs2).** peak |vx| = 103 / 164 — an "object" crossing 54–85%
of the frame in one 100 ms frame — with revHiVx = 26 / 18 fabricated REVERSEs at non-physical speed,
and the highest churn (9.1 / 11.3). Fast camera + fast motion smear components across the frame. Here a
**bounded-velocity / max-displacement** leg fires hard; it is nearly silent on A/B/D.

**D. Calm, already-restrained (go, lsl1).** go: 9 tracks, 0.6/s churn, **0 REVERSE, 0 REACQUIRE**,
peak |vx|=4. lsl1: peak |vx|=8, revHiVx=0. On genuinely quiet discrete-event scenes the tracker is
ALREADY restrained. These are the **do-no-harm control**: V3.0 must not degrade them (no suppression of
the Go stones-appear events, which are the R2 omission-probe targets).

## Consequence for V3.0

A pharo-only gate (sub-mode A, soleSmallMover-based) would do **nothing** for boxing/cs2 (C) or
PoP/police/fencing (B), and risks harming go/lsl1 (D). The trackability gate therefore needs
**orthogonal legs** — applicability (A), association-margin + churn (B), bounded velocity (C) — with a
**do-no-harm guarantee on D**. The pharo inspection gave one leg; this census shows there are at least
three, matched to three measurable signatures, plus a control class the gate must leave alone.

## Honest caveats

- These are failure-**signature** metrics, not fabrication counts. Some boxing REVERSEs are surely real
  (a glove does reverse); revHiVx isolates the physically-impossible ones, it does not claim all 154 are
  false. Confirming true/false counts needs gold (authored per plan §7 at the V3.6 ladder).
- 20 s single-offset clips are indicative, not exhaustive; a different offset could shift the mix.
- go's calm may partly reflect a static commentary layout, not tracker virtue alone — still a valid
  do-no-harm control either way.
