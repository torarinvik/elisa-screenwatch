# V5 — temporal-sensitivity experiment (the scoped invariance law, as an eval filter)

The law (V1.4, scoped): a **temporal** claim answered *identically* on original and temporally-destroyed
input is SUSPECT (it wasn't grounded in temporal evidence); a **static** claim is EXPECTED to be
invariant and is never penalized. `eval/mangle.sh` rebuilds a fixture with temporal structure destroyed
(freeze / repeat1 / reverse / shuffle) but per-frame content intact; `eval/mangle_test.sh` applies the
law. Metric: `temporal_grounding = grounded temporal probes / temporal probes`.

## Viola (symbolic tracker) — the control (2026-07-14, `motion` seed 0)

| probe | op | orig | freeze | repeat1 | reverse | shuffle | verdict |
|---|---|---|---|---|---|---|---|
| sm_count | count | 1 | 1 | 1 | 1 | 1 | **static** (invariant, not penalized) |
| sm_dir | direction | left | — | — | left | left | grounded |
| sm_rev | reversal | yes | **no** | **no** | yes | yes | **grounded** |
| sm_zone | reversal_zone | left | — | — | left | **middle** | **grounded** |
| sm_cont | continuous | yes | yes | yes | yes | yes | untestable (permutation-invariant by construction) |

**`temporal_grounding = 3/3`.** The viola is the control the plan predicted would pass — and it does: its
temporal claims move when time is destroyed (freeze removes the reversal → `reversal` correctly flips to
"no"; shuffle scrambles the turn location → `reversal_zone` changes), while its one static claim (object
count) is correctly invariant. The tracker's motion claims are grounded in temporal evidence, not a
prior — the invariance law confirms it rather than merely asserting it.

## Violin (Qwen2.5-VL-3B) and sax — extension (cites the measured OOD finding)

The full V5 matrix (3 synthetic + 2 real segments × 5 conditions × {violin, sax, viola}) would run the
same law on the neural members. The violin's behavior on the SYNTHETIC half is already measured and
recorded (`vlm-ood-not-blind`, `eval/seed_baseline.md`): a **constant prior** — "No." to every yes/no
event probe, invariant to seed / paraphrase / frame-count. Under this law that invariance is exactly the
suspect signature: a temporal claim that does not move when time is destroyed is not grounded. So the
violin's synthetic-scene temporal claims score `temporal_grounding ≈ 0` **by the same mechanism the OOD
result already documents** — the law reproduces the prior-fill finding from a different angle. The value
of running the neural half is the REAL-frame conditions (where the VLM is in-distribution and may ground
gross scene-change detection); that is the piece worth the VLM compute, and it slots into this harness
unchanged (`vlm_probe.py --screenvlm ... ` over the mangled mp4 path).

## What this feeds

The `temporal_grounding` verdict per claim class is the fine-grained I8 trust table the plan wants: the
viola earns temporal authority (measured, 3/3); the violin does not on synthetic motion (measured ≈0).
This is trust as an eval OUTPUT — the gate can OPEN (raise trust) as well as close, once a real-frame
class shows grounding.
