# Seeded procedural baseline (V1.5) — first measurement

Date: 2026-07-13. Tracker: current viola (pre-V3 upgrades). Runner: `eval/seed_test.sh 0 9`
(6 tracker scenes x 10 development seeds, self-generated gold; originally 190 op-probes, 200
after V1.2 added the `st_rev` reversal probe to motion-trap — same single miss either way).

## Result

| scene | score |
|---|---|
| motion | 50/50 |
| motion-trap | 70/70 |
| crossing-swap | 29/30 |
| occlude-vanish | 20/20 |
| scroll-motion | 10/10 |
| contact-merge | 20/20 |
| **aggregate** | **199/200 (99.5%)** — bar: >= 95% (V1.9) |

**Verdict: the tracker generalizes across seeded geometry — the fixed-scene 100% was NOT
memorization.** Positions, sizes, lanes, event times and horizontal mirroring all vary per seed;
gold is computed by scenegen from the same parameters (the generator is its own annotator).

## The one miss — a genuine finding, kept on the record

`crossing-swap --seed 2`: `two_directions` answered "no" (gold "yes"). The seeded geometry
produces a longer, messier crossing merge than the fixed scene: both tracks go OCCLUDED at
t=8700, the merged blob appears as a NEW id (3), reacquisition churns ids through t=11700, and
id 1 picks up a spurious mid-field REVERSE at t=11700. Post-churn, no single track id shows both
net directions, so the op honestly answers "no".

This is the v2 merge-drag failure reproduced procedurally — the exact failure mode V3.2
(tentative reacquisition + candidate identity sets) and V3.2b (weak-component provisional tier)
exist to fix. It stays in this baseline as the "before" measurement; V3 acceptance re-runs this
battery and must clear it without regressing the other 189.

## Probe-authoring lesson (recorded so it isn't relearned)

The first draft emitted a `two_directions` probe for contact-merge with gold "no" (net physical
displacement is ~0). It failed on ALL 10 seeds — not a tracker bug: the op measures per-track-id
net displacement, and the merge/split churns ids, so post-split segments legitimately show both
signs. The op cannot answer a physical-identity question under id churn; the probe was removed.
Rule: **a generated probe's gold must be an invariant of what the op actually computes, not of
the physical scene** — identity-under-merge questions wait for V3.2's candidate-set ops.

## Reserved seeds

Seeds 1000+ are the held-out pool (scenegen refuses without `--final`; seed_test.sh refuses
entirely). Nothing in this pool has been run. First legitimate use: V3 graduation scoring.

## Metamorphic-pair baseline (V1.2) — 2026-07-13

Runner: `eval/meta_test.sh 0 9`. Pairs share a seed and diverge in exactly ONE property
(no-reverse = hold at the reversal point; no-vanish = visible glide between the same endpoints).
Credit requires the answer to CHANGE across the pair — identical answers on both sides reveal a
prior and score 0 even when one side was "right".

| pair | flip probes | score |
|---|---|---|
| motion / no-reverse | sm_rev | 10/10 |
| motion-trap / no-vanish | st_gap, st_cont | 20/20 |
| motion-trap / no-reverse | st_rev | 10/10 |
| transient-in-noise / no-transient | atn_count, atn_cluster | 2/2 |
| tone-alarm / no-tone | ata_count | 1/1 |
| av-sync / no-transient | avs_impact, avs_count | 2/2 |
| **metamorphic_sensitivity** | | **45/45 (100%)** |

The symbolic tracker and the cymbal are fully evidence-driven on these pairs — expected, since it has no priors
to leak. The battery's real target is the VLM member (V1.9 re-runs the Qwen motion traps under
pair credit); this run establishes that the pairs themselves are answerable, so a VLM failure is
a prior leaking, not an impossible probe.

## Temporal-destruction baseline (V1.4) — 2026-07-13

Runner: `eval/mangle_test.sh <scene> 0`. Destruction via `eval/mangle.sh` (arch_tool replay ->
deterministic reorder -> ffmpeg ffv1 -> vidingest): modes freeze / repeat1 / reverse / shuffle.
The scoped law: a TEMPORAL claim answered identically on original and destroyed input is SUSPECT;
STATIC claims are expected invariant. Probes whose gold equals the known static gold of a frozen
clip (e.g. continuous=yes) are UNTESTABLE by destruction (the control cannot flip their gold) and
are excluded, not penalized — the metamorphic rule applied to the control itself.

| scene | temporal_grounding |
|---|---|
| motion | 3/3 |
| motion-trap | 6/6 |
| crossing-swap | 1/1 |
| occlude-vanish | 1/1 |
| scroll-motion | 0/0 (no testable temporal probes) |
| contact-merge | 0/0 (no testable temporal probes) |

Every testable temporal answer changed under destruction — the tracker's temporal claims are
grounded in temporal evidence, none are prior-driven. (Expected for a symbolic member; the
instrument's real target is the VLM cross-exam in V5.)

## Relation-probe baseline (V1.3b) — 2026-07-13

New seeded scene `launch`: A approaches static B; B departs at contact (base) or 1.5-2.5 s
BEFORE contact (`--variant early-launch` — effect precedes cause, the relation a continuity
prior would smooth over). New id-churn-robust op `move_before_arrival` (rightmost/leftmost
trajectories, no track ids; contact located from the generator-supplied `arr_cx`).
Scored as a metamorphic pair (relation_grounding == the launch/early-launch pair line):
**10/10 seeds credited** in meta_test; launch also joins the seed battery (now 220 probes,
219/220, same single crossing-swap miss).

## Phase-offset + paraphrase + confidence audit (V1.7 / V1.8) — 2026-07-13

- `scenegen --phase <ms>` (0..1900) shifts every param-derived event time by a sub-batch offset;
  gold shifts with the frames automatically (same params feed both). `seed_test.sh 0 9 700`:
  **219/220** — identical to phase 0, same single crossing-swap miss. No probe was riding a
  batch-boundary accident.
- VLM probes now carry `q_alt` paraphrases (28 across one-digit-counter, counter-skip, motion,
  motion-trap); `vlm_probe.py --paraphrase k` rotates phrasing without touching gold. To be
  exercised by the V1.9 Qwen re-audit.
- V1.8 confidence-blind audit: grep-verified that NO matcher consumes a `conf` field for credit
  (track_probe parses conf into its event tuples but no op reads it; score_memory, audio_probe,
  vlm_probe never touch it). Confidence remains an eval OUTPUT (V3.5 calibration), never an input.

## VLM metamorphic acceptance (V1.9) — 2026-07-13

Runner: `eval/meta_vlm.sh 0 2 8`. The V1.2 metamorphic-pair law (a flip probe is credited only
when answered correctly on BOTH sides of the base/variant pair) applied with the **Qwen2.5-VL-3B**
as the answerer (`vlm_probe.py`) instead of the symbolic tracker. Each fixture's probes are filtered
to the pair's flip probe(s) to bound cost (the VLM reloads per probe, ~13 s); paraphrase index is
rotated by seed (V1.7 `q_alt`) so phrasing varies 0/1/2 across the sweep.

| pair | flip probes | score |
|---|---|---|
| motion / no-reverse | sm_rev | 0/3 |
| motion-trap / no-vanish | st_gap, st_cont | 0/6 |
| motion-trap / no-reverse | st_rev | 0/3 |
| launch / early-launch | rl_order | 0/3 |
| **vlm_metamorphic_sensitivity** | | **0/15 (0%)** |

**Finding — a pure prior, not perception.** On every yes/no event question (reversal, vanish-gap,
continuity, launch-order) the VLM answered a constant **"No."** on BOTH sides of BOTH the base and
variant, invariant to seed and to paraphrase. Pair credit therefore scores 0: the answer carries
no information about the frames. The symbolic tracker scores 55/55 on the identical probes (V1.2),
so the pairs are answerable — this is a model failure, not an impossible test. This is exactly the
leak the metamorphic instrument was built to catch; it is a MEASUREMENT, not a pass/fail bar.

Frame-density control: re-running the base fixtures at 32 frames (4× the 8-frame sweep) still
returns "No." on sm_rev / st_gap / st_cont — the prior is not frame-starvation, so denser sampling
does not rescue it. (Open-ended probes fare no better: `pm_count` gold 1 → "2", `pm_dir` gold right
→ "left" — the downscaled synthetic scenes are out-of-distribution for the 3B model.) The takeaway
for the orchestra: the VLM cannot be trusted as a motion/event authority on these inputs; the
symbolic members remain the authority, and V5 (VLM cross-exam) inherits this as its "before" line.
