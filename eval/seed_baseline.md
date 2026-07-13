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
