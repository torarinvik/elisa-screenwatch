# V3.0 trackability gate — acceptance (annotation-free)

Implemented 2026-07-14 in `tracker.elisa`. The gate licenses physical-motion claims (REVERSE) only
when the component/region is a trackable persistent object; otherwise it abstains with a first-class
`INF activity ... activity_type=UI_CHANGE trackability=LOW reason=<leg>` verdict and the OBSERVED
changed-regions are retained. Multi-leg by construction (see `restraint_census.md` for the 4 sub-modes
that forced this): **A** applicability (chrome UI pointer), **B** bounded velocity (smear), **C**
jitter/flicker (tiny + small travel span). Every event now also carries the 3-field confidence split
`dq=`/`am=`/`ec=` (detection_quality / association_margin / event_confidence).

All numbers below are annotation-free (read from the tracker's own stdout — no gold pulled forward from
§7). Baseline = the 2026-07-13 pre-gate tracker; both runs use the identical ingested fixtures.

## Pharo acceptance (the primary target — `/tmp/fix_pharo`, 60 s IDE session)

| metric | 2026-07-13 baseline | V3.0 gate | target | verdict |
|---|---:|---:|---|---|
| false REVERSE (OCR-static) | 5 | **0** | 0 | ✅ |
| revHiVx (implausible reverse) | 3 | **0** | ↓ | ✅ |
| motion-claim count (REVERSE) | 5 | **0** | ↓ | ✅ |
| VANISH (object-permanence claims) | 51 | 46 | ↓ | ✅ |
| OCCLUDED | 43 | 38 | ↓ | ✅ |
| REACQUIRE | 18 | 14 | ↓ | ✅ |
| birth/death churn /s | 1.9 | **1.8** | ↓ | ✅ (modest) |
| track count | 61 | 61 | — | see note |
| UNTRACKABLE verdicts | 0 | 2 (1 ui-pointer id=15, 1 ui-jitter id=57) | >0 | ✅ |
| OBS frame / OBS comp (evidence) | 593 / 2826 | 593 / 2826 | unchanged | ✅ retained |

The 5 baseline false REVERSEs were: **id=15 ×4** (t=14.2–16.1 s — the mouse cursor, tiny, sole mover over
the full-width toolbar+taskbar; caught by leg A applicability) and **id=57 ×1** (t=51.7 s — a tiny,
area-4 flickering caret with a ~15 px travel span; caught by leg C jitter). Both are now suppressed with
a recorded verdict; the cursor's identity churn (VANISH/OCCLUDED/REACQUIRE) is additionally withheld
(an untrackable region has no identity to lose or reacquire) — this is the source of the modest
51→46 / 43→38 / 18→14 / 1.9→1.8 reductions.

**Note on track count (honest scoping).** The 61 pharo tracks are NOT rapid flicker — only 1 lives <5
frames; the rest persist 13–143 frames. They are genuine persistent *changed regions* (IDE panels, text
areas), not noise. Collapsing that count safely requires region-level object-vs-UI classification, which
annotation-free evidence cannot do without risking the do-no-harm controls — which is exactly why the
plan schedules the gold-based "fraction correctly classified as UI activity" for the V3.6 ladder. The
V3.0 gate deliberately does not force a risky birth/region suppression to move a raw count.

## Do-no-harm + multi-video generalization (all 8-video census fixtures)

`RE` = REVERSE events, `rHV` = revHiVx. Track count and churn shown to prove no collateral churn.

| fixture | sub-mode | RE base→gate | rHV base→gate | tracks base→gate | churn base→gate |
|---|---|---|---|---|---|
| pharo   | A UI pointer      | 5 → **0**   | 3 → **0**  | 61 → 61   | 1.9 → 1.8 |
| go      | D control (hard)  | 0 → 0       | 0 → 0      | 9 → 9     | 0.6 → 0.6 |
| lsl1    | D control (soft)  | 2 → 2       | 0 → 0      | 25 → 25   | 2.3 → 2.3 |
| police  | B assoc. churn    | 12 → 6      | 1 → 0      | 83 → 83   | 5.2 → 5.2 |
| PoP     | B assoc. churn    | 13 → 8      | 2 → 0      | 107 → 107 | 7.5 → 7.5 |
| boxing  | C velocity smear  | 154 → 125   | 26 → **11**| 123 → 123 | 9.1 → 9.1 |
| cs2     | C velocity smear  | 67 → 48     | 18 → **8** | 144 → 144 | 11.3 → 11.3 |

- **Do-no-harm controls (sub-mode D) fully preserved by the V3.0 gate.** go and lsl1 are byte-for-byte
  identical on every metric under the gate alone — lsl1 keeps its 2 REVERSEs (they are not tiny-chrome,
  not smear, and span 35 exceeds the jitter floor). This was the load-bearing design pivot: an earlier
  committed-direction excursion metric wrongly flagged Larry, and a lifetime-mean-speed leg wrongly
  flagged his post-pause reverse — both rejected for the direction-agnostic, LOST-gap-robust travel
  *span*. **Correction (V3.1, below):** closer inspection showed those 2 lsl1 REVERSEs were themselves
  fabricated — from coasted prediction while Larry was OCCLUDED and hidden — so V3.1's direction re-seed
  correctly removes them. The V3.0 gate leaving them is accurate (they aren't its sub-modes); V3.1 is
  the leg that catches cross-occlusion fabrication.
- **No collateral churn.** Track count and churn are unchanged on every non-target fixture — the earlier
  one-strike "permanently reclassify the whole track UI" design caused die-and-rebirth churn on
  boxing/police/cs2; separating "chrome region ⇒ not an object" (permanent) from "this reverse is a
  smear/jitter" (per-event) removed that side effect entirely.
- **Implausible reverses crushed on the velocity-smear scenes** (boxing 26→11, cs2 18→8) with real object
  identity intact. The residual revHiVx are reverses whose instantaneous |vx| at the turn was below the
  ceiling though a nearby frame exceeded it — genuinely ambiguous, so left alone (do-no-harm over
  the ambiguous middle; full disambiguation waits on V3.6 gold).

## Association margin (leg B) — measured, hard-gating deferred to V3.2

The association margin (2nd-best − best gate distance) is computed and emitted on every event as `am=`.
Hard-gating REACQUIRE on low margin was tried and **rejected**: suppressing a reacquire turns the track
into a death + rebirth, which *increases* total churn (observed on police/boxing/cs2). The margin is
therefore surfaced as evidence in V3.0 and consumed by V3.2's candidate-identity sets / supersession
disputes (which preserve identity instead of destroying it), per the plan's ordering.

## Regression (synthetic — the gate must not suppress real motion)

- `track_test` motion / motion-trap / crossing-swap / occlude-vanish: **100%** perception, 0% confab,
  100% twin-consistency (direction 2/2 on `motion` — real reverses fire; the synthetic objects are
  above the tiny floor and sweep far).
- `seed_test`: **219/220 (99%)** — identical to baseline (the single crossing-swap seed=2 miss is
  pre-existing, verified by reverting the gate). No seeded regression.
- `score_memory.py --selftest` PASS; `v2_supersession_test.sh` PASS (ledger parses the new `dq/am/ec`
  fields and ignores them — `conf=` retained).
