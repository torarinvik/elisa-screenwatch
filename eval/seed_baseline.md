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

## Representation-ladder acceptance (V1.10) — 2026-07-14

Runner: `eval/meta_ladder.sh`. V1.9 proved (32f control) the raster 0/15 is the vision encoder, not
frame count. V1.10 tests the complementary lever: spend the context budget on MANY frames at LOW
detail-per-frame — the scene handed to the LLM's **language** pathway as a TEXT bounding-box log
(`screenvlm_text.py`, rungs `table:N` / `svg:N`) instead of pixels to the vision encoder. The boxes
come from an **independent** per-frame threshold + connected-components pass (`extract_blobs`): no
tracker, no track ids, no direction/event computation. A correct answer would therefore be genuine
reasoning over evidence, not a paraphrase of viola — so this rung *could* have earned real authority.

The representation is provably faithful. For motion base seed 0 the log reads cx 561→116 (t=0..7800)
then 116→557 (t=8700..19900) — the reversal, its zone (left), and the turnaround time are all right
there in the numbers; the extractor never labels them.

**Result — every rung 0, same prior.** Metamorphic pair credit (correct on BOTH sides), seed 0:

| rung | repr / frames | ladder_sensitivity |
|---|---|---|
| table:8  | box log, 8 frames  | 0/5 |
| table:24 | box log, 24 frames | 0/5 |
| svg:12   | per-frame SVG, 12  | 0/5 |

Every answer is the same constant **"No."** the raster violin gave — the text pathway leaks the
identical prior. The strongest rung run to full parity with V1.9 (`eval/meta_ladder.sh 0 2 "table:8"`,
3 seeds × 4 pairs) scores **0/15** — the same number as the raster violin, flip probe for flip probe.

**The mechanism — a prior, and it confabulates agreement with the question.** A/B on motion seed 0
(base reverses = gold yes; variant monotonic = gold no), `table:8`:

| question phrasing | base | variant |
|---|---|---|
| neutral ("does the square reverse its direction of motion?") | No | No |
| log-pointing, not leading ("using the cx values, does it reverse horizontal direction?") | No | No |
| spoon-fed ("does cx decrease and then increase?") | **Yes** | **Yes** |

The neutral and even the log-pointing phrasings return the constant "No" prior. The spoon-fed
phrasing returns "Yes" — **on both sides**, including the monotonic variant whose cx only ever
increases. So the model never consults the numbers to check the premise; it echoes whatever the
question presupposes. A separate read-comprehension probe confirms the shape: asked for cx at the
first line / its minimum / the last line, the model reports the endpoints correctly (561, 557) but
gives the minimum as row 2's value (510, true min 116) and calls the V-shape "generally decreasing"
— it does local lookups but cannot do the global aggregation (find-min, detect-a-reversal,
verify-a-premise) the event probes require.

**Methodology note kept on the record so it isn't relearned.** An early hand-diagnostic with the
spoon-fed phrasing returned "Yes" on the base and was briefly mistaken for the rung working. It was
a *leading prompt* — the same phrasing says "Yes" to the no-reversal variant too. Only the neutral
probe under pair credit is a valid measurement; it caught the error. Rule: **never score the violin
on a phrasing that names the answer's mechanism** — that is the harness reasoning, not the model.

**Takeaway.** No rung of the representation ladder earns the violin any temporal authority on these
inputs. The bottleneck is not representation fidelity (the reversal is explicit in the log) but the
3B model's inability to reason over multi-row evidence and its habit of agreeing with the question's
premise. The ladder idea was worth measuring and is now measured: authority stays with the symbolic
members. V5 (VLM cross-exam) inherits BOTH "before" lines — raster 0/15 (V1.9) and text-log 0 (V1.10).

### Real-image cross-check — the control that corrects the narrative

To check whether "the VLM can't see" over-generalized from the synthetic scenes, the same three
representations were run on ONE natural illustration (three blue hexagonal "C" characters with
cartoon faces and a wooden Pinocchio nose growing left->right, with progression arrows — a "growing
lie"). One Qwen load, four conditions (scratch script, not committed):

| representation | model's description | verdict |
|---|---|---|
| **pixels** (448px, vision) | "three blue hexagonal characters with the letter C... a wooden stick being inserted into the nose... arrows pointing left to middle to right, indicating a sequence" | **essentially correct** (missed only the "lie" metaphor) |
| **ASCII 64-wide** (text) | "a person holding a gun, aiming at another person on the ground" | hallucination |
| **ASCII 110-wide** (text) | "a landscape with a mountain range... a river... peaceful and serene" | hallucination (and disagrees with the 64-wide one) |
| **vector / color regions** (text) | correctly restates "11 blue... 6 white... 3 wood-tan regions... a color segmentation task" | faithful readout, ZERO semantic inference |

Three corrections to the record:

1. **The 3B VLM is NOT globally blind.** On a real, in-distribution image it describes the scene
   accurately. The V1.9 raster 0/15 is specifically the DOWNSCALED SYNTHETIC scenes being
   out-of-distribution pixels — not a general perception failure. Do not cite V1.9 as "the VLM can't
   see"; cite it as "the VLM can't see OUR synthetic rasters."
2. **ASCII rendering is worse than useless.** It induces confident, unrelated hallucinations (a gun
   scene; a serene landscape) that don't even agree across resolutions — the model isn't reading the
   ASCII, it pattern-matches "ASCII-art-of-a-scene" and confabulates. Turning pixels into ASCII
   DESTROYS information for this model.
3. **Vector text is read but not interpreted.** The extractor captured the punchline with no
   semantics — three tan bars of increasing width (86 -> 203 -> 250) — but the model never connects
   that to noses/faces/a lie; it just re-lists the regions. Same V1.10 signature: local readout yes,
   semantic/global inference no.

Net: for this model **pixels >> vector-text >> ASCII**. Text renderings do not rescue perception,
because the bottleneck was never the pixels' fidelity — it is the model reading non-natural text and
reasoning semantically over faithful text. The orchestra keeps the VLM on IN-DISTRIBUTION natural
frames (where it is useful) and never as a motion/event authority on synthetic geometry.

### Reader vs. representation — the same text handed to a capable model

The above conclusions are about the 3B READER. To separate reader from representation, the SAME
ASCII and vector text (no image, blind) were handed to a full Claude agent:

| rendering | tokens | Qwen-3B reader | Claude-agent reader (blind, text only) |
|---|---|---|---|
| ASCII (80/120/160-wide) | 471 / 952 / 1437 | hallucinates a gun scene / a serene landscape | "three round face-like objects in a row, highlight + two eye-spots each" — correct gross structure, no hallucination, honest low-med confidence |
| **vector / color regions** | **457** | flat: "a color segmentation task" | "three figures in a row: blue shell + white face-panel + a tan bar growing 86->203->250, anchored left, protruding rightward -> a motion/progression sequence" |

The vector agent reconstructed the PUNCHLINE from pure geometry — the monotonic tan-bar growth as
"the deliberate point of the composition" — which even the pixel-fed 3B missed (it thought only the
rightmost figure had a nose). It missed the letter "C", the cartoon faces, and the "lie" metaphor,
but got the structure and the progression. It read the GLOBAL composition better than the pixel 3B;
the 3B had richer local semantics (faces, "C", arrows) but misread the structure.

**The correction this forces:** the representation was never the bottleneck — the READER was. The
exact vector text the 3B dismissed let a capable model rebuild the three-figure layout AND the
growing-protrusion progression, at ~457 tokens (~2 frames' worth of 448px vision budget). Two things
held across both readers: **vector > ASCII** (ASCII loses the progression; it is also the only thing
that made the 3B hallucinate outright), and the V1.9/V1.10 zeros are a statement about THAT MODEL,
not about the text-representation channel. Design fork for V5: a vector-region text channel is a
viable, cheap, evidence-grounded violin input IF the reader is capable enough — which points at an
API-class model for the violin's semantic role, not the local 3B.
