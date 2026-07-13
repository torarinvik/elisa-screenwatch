# Orchestra v3 — the real-world plan

**Status: PLANNED (v2 complete — see orchestra_v2_plan.md for the M1–M9 record).**

This plan is the product of the four-way design debate (Claude / ChatGPT / Grok / Gemini) that
followed v2, after all corrections were accepted on both sides. It is governed by one sentence:

> **Every claim retains both its evidence and the rule that licensed it; authority is earned
> per-claim-type by measurement, never granted per-model.**

And by the converged division of labour:

```
Trap testing        discovers the failure.
Symbolic measurement answers the exact predicate.
Provenance          records what licensed each claim.
Admission policy    prevents unsupported claims from graduating.
Representation      determines whether evidence can later be retrieved,
                    revised, and reasoned over correctly.
```

Provenance does not *eliminate* prior-fill; it **contains its epistemic consequences**. The v2
bake-off measured exactly that containment (all rungs rejected the VLM prior because all carried
I8/I9 trust tags); this plan extends the same discipline to real-world material.

**What is new since v2:** the user supplied `videos/` — 17 real-world video files (~7.5 GB,
sports / board games / retro games / desktop programming). These are the anti-overfit corpus the
debate demanded: the trap suite must stop being the only examiner, because a tracker can score
100% by memorizing seven deterministic scenes. Real videos with sparse human-checkable gold are
the graduation exam.

---

## 0. The video corpus — census and tiering

All files in `videos/` (gitignored — media never enters git; only derived fixtures' *manifests*
and gold annotations are committed). ffprobe confirms: H.264 + AAC audio, various resolutions
(e.g. pharo = 1048x720@60fps, 380 s).

### Tier R1 — near-domain (desktop / retro-game screens; low palette, discrete sprites)

The closest world to scenegen's: flat-shaded regions, discrete moving objects, mostly-static
backgrounds. The tracker's first real-world rung.

| file | why it matters |
|---|---|
| `pharo programming.mp4` (380 s, smallest) | **the design domain itself** — a desktop IDE session: windows, text, cursors, scrolling. OCR-rich; the guitar's real exam. **First ingest target.** |
| `Prince of Persia … PC DOS 4K.mp4` | single sprite protagonist on near-static rooms — the *ideal* real tracker fixture: appear/vanish (doorways), reversal (turnarounds), occlusion (pillars). |
| `Leisure Suit Larry 1 … Walkthrough.mp4` | EGA palette adventure — tiny color count, slow deliberate motion, scene cuts. |
| `LEISURE SUIT LARRY 2 … Playthrough.mp4` | same, larger. **HELD OUT** (see §7). |
| `Police Stories 100 Walkthrough Part 1.mp4` | top-down 2D — multiple simultaneous small sprites; the multi-track / candidate-identity exam. |

### Tier R2 — discrete-event symbolic (board games / scoreboards)

Near-static frames punctuated by *discrete, independently verifiable events* (a stone placed, a
piece moved, a score changed). Perfect for **omission probes** (did the system report move 34?)
and OCR cross-checks (scoreboards, clocks, move lists).

| file | why it matters |
|---|---|
| `Mental Problems [Fan Tingyu VS Tu Xiaoyu] … Go … Full Game.mp4` | stones appear one at a time on a 19×19 grid — appear-events with *exact* gold from the game record. |
| `🎦 Magnus Carlsen … vs Gukesh.mp4` | chessboard + eval bar + clock — OCR (clock) and discrete events (moves). **HELD OUT.** |
| `THE MILLION POUND CHAMPION … Darts … Final.mp4` | scoreboard OCR gold (180! checkouts); dart flight = fast-motion micro-events. |

### Tier R3 — fast natural motion (stress / limits documentation)

Camera pans, motion blur, crowds, cuts every few seconds. The tracker is **not expected to win**
here — this tier exists to (a) measure the triage's ACTIVITY classification on real footage,
(b) measure where the component tracker degrades and document it honestly, (c) exercise real
audio (crowd noise, impacts, commentary speech, whistles).

| file | notes |
|---|---|
| `2025 CIP FINAL Foconi v Massialas … Foil Fencing.mp4` | two-object interaction, planche-line motion (near-1D!), score-light events |
| `Down and out … Dubois v Lerena Boxing.mp4` | impacts ↔ audio transients (AV-sync probes) |
| `Lin Shidong vs Truls Moregard … EuropeSmash.mp4` | ball = tiny fast object; the small-object limit. **HELD OUT.** |
| `San Antonio Spurs vs New York Knicks … NBA Finals.mp4` | many objects, scoreboard OCR |
| `Team Speed 7-6 Team Celine … FIFA Creator Cup.mp4` | *rendered* sport — HUD OCR + game motion |
| `Дэниел Кормье vs Энтони Джонсон.mp4` | MMA; non-Latin title exercises path handling |
| `CS2 BEST MOMENTS 2025 (Highlights).mp4` | FPS game — HUD OCR, kill-feed events, violent camera motion. **HELD OUT.** |
| `I Tested If Size Matters In Every Sport.mp4` (1.5 GB) | jump cuts, mixed scenes — the ACTIVITY/scene-cut exam |
| `Extreme Idiots … Fails [HD].mp4` | uncurated handheld footage; worst case |

**Held-out protocol (§7):** `LSL2`, `Carlsen-vs-Gukesh`, `Lin-vs-Moregard`, `CS2` are **never
opened during development** — no probes authored from them, no tracker runs against them until a
milestone's final scoring. One per tier + one extra R3.

---

## Milestone map

| # | name | depends on | what it proves |
|---|---|---|---|
| V0 | `vidingest` — video→orchestra bridge | — | real material flows through the SAME pipeline as live capture |
| V1 | Evaluation protocol upgrade | — (parallel with V0) | the scorer can no longer be fooled by affirmation bias, omission, or memorized scenes |
| V2 | Supersession schema (rung B+) | V1 (scored by it) | interpretations can be revised without rewriting evidence |
| V3 | Tracker upgrades + real-video ladder | V0, V1, V2 | motion authority extends to occlusion/merge/2-D global motion, on held-out material |
| V4 | Closed-vocabulary SED audition | V0 (real audio), V1 | an audio middle tier earns per-class admission |
| V5 | Temporal-sensitivity experiment | V0, V1 | temporal claims are penalized for invariance to temporal destruction |
| V6 | Long-running integrated trial | all | the whole orchestra survives hours of real material with honest memory |

V0 and V1 start in parallel; everything else is sequential in the debate-converged order.

---

## V0 — `vidingest`: the video→orchestra bridge

**Goal:** a video file becomes indistinguishable from a live capture session — the SAME batch
format, the SAME Tier-A archive, the SAME `.idx`, consumed by the SAME tracker/triage/OCR/VLM
members. No member grows a special video path; only the *frame source* changes.

**Why it's cheap:** `frame_dump.elisa` already separates capture (`screencap.elisa`) from
encoding (`encoder.elisa` — `downscale_into(src: u32&, sw, sh, dw, dh, base)` onward). The new
member is a frontend that feeds pixels from ffmpeg instead of ScreenCaptureKit.

### V0.1 `vidingest.elisa` (new member — "tape deck")

- Spawns/consumes `ffmpeg -i <video> -vf fps=<fps> -pix_fmt bgra -f rawvideo -` (via `popen`
  extern, or a two-step: ffmpeg → temp raw file → fread; choose whichever the extern surface
  supports cleanly — popen preferred, temp-file fallback acceptable for v1).
- Reads `sw*sh*4` bytes per frame, calls the existing `downscale_into` → delta-encoder path.
- Synthetic timestamps: `t_ms = frame_idx * 1000 / fps` (deterministic, replayable — no wall
  clock, so ingesting the same video twice is **bit-identical**; verify this explicitly).
- CLI: `vidingest <video> <out_dir> [--fps 10] [--width 192] [--t0 <s>] [--dur <s>]`
  — `--t0/--dur` cut a segment WITHOUT re-encoding gold timestamps (probe times stay
  video-relative; the manifest records the offset).
- Also writes the Tier-A archive ring (same code path as frame_dump) so `arch_tool
  show/replay/compare` work on video-derived sessions unchanged.

### V0.2 `audextract.sh` (trivial)

- `ffmpeg -i <video> -ac 1 -ar 16000 -f s16le` (or wav) → the cymbal's exact input format.
- Segment flags mirror V0.1 so audio and video segments stay aligned to the same `t0`.

### V0.3 Fixture manifests — `eval/scenarios/real/`

Media is gitignored; what IS committed per fixture:

```
eval/scenarios/real/<name>/manifest.json   {video, t0, dur, fps, width, sha256 of source}
eval/scenarios/real/<name>/truth.jsonl     sparse gold (§7 annotation protocol)
eval/scenarios/real/<name>/probes.jsonl    probes over that gold
```

A `make_fixture.sh <manifest>` regenerates batches + wav from the manifest deterministically.

### V0.4 Acceptance

- [ ] `vidingest videos/pharo\ programming.mp4 /tmp/vid_pharo --fps 10 --dur 60` produces
      batches that `arch_tool verify` passes and the tracker/triage parse without modification.
- [ ] Ingesting the same segment twice → **bit-identical** batch files (diff clean).
- [ ] `screenocr` on a replayed pharo keyframe reads real IDE text (spot-check ≥ 5 strings).
- [ ] Cymbal runs on extracted boxing audio and emits transients (no gold yet — smoke only).
- [ ] One committed manifest per tier (pharo, PoP, Go, fencing) — held-outs get NO manifest yet.

**Estimated size:** ~1 day. The encoder reuse does all the real work.

---

## V1 — Evaluation protocol upgrade

**Goal:** upgrade the examiner before upgrading any examinee, because every later result is
scored by this layer. Eight instruments, all extending existing harnesses (`score_memory.py`,
`track_probe.py`, `audio_probe.py`, `scenegen`, `audiogen`).

### V1.1 Positive/negative question twins

- `probes.jsonl` grows `twin_of: <probe_id>` + `polarity: pos|neg`.
- Scorer: **paired credit** — a twin pair scores 1 only if BOTH answers are consistent
  (vanish=yes ∧ remained-visible=no). Report `twin_consistency` as its own metric next to
  `perception_accuracy`. An affirmation-biased model (answers "yes" to everything) scores 0 on
  pairs where it used to score 50%.
- Author twins for ALL existing motion-trap and audio-trap probes (mechanical: each existing
  probe gets a negated sibling).

### V1.2 Metamorphic scene pairs

- `scenegen` gains **pair mode**: `scenegen <scene> --variant hold` produces the identical scene
  with exactly one property changed (the object does NOT vanish / does NOT reverse / no tone).
- Scoring rule: credit requires the answer to *change across the pair*. A model answering
  "vanished" to both A (vanish) and B (no vanish) reveals a prior, and scores 0 even though it
  was "right" on A. Metric: `metamorphic_sensitivity`.
- Same for `audiogen` (`--variant no-transient`, `--variant no-tone`).

### V1.3 Omission probes (the dual of confabulation)

- New probe kind `omission`: gold = an event that DID occur; the question is open ("list all
  alarms you heard", "how many objects appeared?") and the metric is **recall of real events**,
  scored per event. Current probes catch invention; these catch suppression (a model narrating
  "calm session" past a real error dialog).
- Add `omission_rate` (missed real events / real events) to `score_memory.py` output beside
  `confabulation_rate` — the two failure surfaces, reported as a pair, per NOAH's duality.

### V1.4 Temporal-destruction controls (scoped — this is a metamorphic probe, NOT TCD)

- `arch_tool` gains `mangle <dir> <mode>` where mode ∈ `freeze|reverse|shuffle|repeat1` —
  produces a batch directory with the temporal structure destroyed but per-frame content intact.
- Probes gain `claim_class: static|temporal`. Scoring rule (the scoped law from the debate):
  **a `temporal` claim answered identically on original and mangled input is marked suspect**
  (metric `temporal_grounding`); `static` claims are EXPECTED to be invariant and are never
  penalized for it. ("There is a boxing ring" must survive shuffling; "he moved left then right"
  must not.)

### V1.5 Seeded procedural scenes + held-out seeds (anti-overfit, synthetic half)

- `scenegen <scene> --seed N`: positions, velocities, colors, sizes, event times, distractor
  count all derived from the seed via the existing xorshift; **gold answers computed from the
  same seed** and emitted as `truth.jsonl` alongside the fixture (scenegen becomes its own
  annotator — it already knows where everything is).
- Seed ranges: `0–999` development, `1000–1099` **reserved** — never run during development;
  final milestone scoring only. Enforced socially + a comment in `trap_test.sh`; the runner
  refuses reserved seeds unless `--final` is passed.
- `audiogen --seed N` identically (tone freqs, transient times, ramp rates).

### V1.6 Per-claim-type scoring

- Every probe already has `kind`; extend the report to break perception/confab/omission down
  **by claim class** (`presence|count|position|direction|timing|identity|text|audio`), because
  "75% overall" hides "100% on presence, 0% on direction" — which is exactly the structure the
  Qwen results had. Table output per member per class.

### V1.7 Randomized paraphrases + phase offsets

- `vlm_probe.py`/`track_probe.py`: each probe carries 2–3 phrasings; the harness rotates them
  by seed. Kills prompt-shape memorization.
- `--phase <ms>` on fixture generation shifts all event times by a sub-batch offset so nothing
  aligns to batch boundaries by accident.

### V1.8 Confidence-blind scoring

- Scorers already ignore self-reported confidence for credit; make it explicit and audited: any
  matcher consuming a `conf` field is a bug. Confidence calibration is reported SEPARATELY
  (reliability diagram data: claimed conf vs measured accuracy per bucket) — trust remains an
  eval OUTPUT.

### V1.9 Acceptance

- [ ] All 9 existing trap suites re-pass under the upgraded scorer (twins added, pairs added).
- [ ] The VLM prior-fill result REPRODUCES under twins: Qwen's motion-trap score drops or holds
      (it cannot rise — twins only remove false credit) and `twin_consistency` is reported.
- [ ] `scenegen --seed` at 10 development seeds: tracker ≥ 95% aggregate (if it drops far below
      the fixed-scene 100%, that gap IS the overfit measurement — report it, then fix in V3).
- [ ] Mangle modes verified: viola on shuffled input reports garbage-or-nothing (it has no
      prior to fill with — confirm, don't assume).
- [ ] scorer `--selftest` extended to cover twins, omission, metamorphic pairing, claim classes.

**Estimated size:** 2–3 days. Highest value-per-line in the plan.

---

## V2 — Minimal supersession schema (rung B+)

**Goal:** interpretations become revisable without rewriting evidence, BEFORE the tracker starts
producing revisable interpretations (V3's tentative reacquisition writes into this schema).

### V2.1 Schema (extends `eval/ledger.py` records)

```
valid_start / valid_end      when the claim is about
recorded_at                  when the claim was made (bi-temporal minimum)
obs_or_inf                   OBSERVED | INFERRED          (exists)
status                       active | superseded | disputed   (NEW; default active)
supersedes                   record id | null              (NEW)
evidence_handles             batch/frame/track pins        (exists)
license                      the RULE that admitted it, e.g. "viola:VANISH",
                             "cymbal:TRANSIENT", "vlm:describe(static)"   (NEW)
```

### V2.2 The one law (enforced, not conventional)

**`supersedes` may only point at an INFERRED record.** `ledger.py build` hard-fails on a
supersession targeting an OBSERVED record. Evidence is immutable; interpretations retire.
Worked example (the v2 bake-off's own pt_count case):

```
OBSERVED  no-component 9200–10000ms            (immutable, forever)
INFERRED  track-17 VANISHED @9200      → status: superseded
INFERRED  track-17 OCCLUDED, reacquired as track-19 (candidates {17-continues, new-object})
          supersedes: ^                 status: active, conf split across candidates
```

### V2.3 Projection + probes

- `ledger.py project` renders active interpretations; superseded ones appear only under a
  `revisions:` note when `--audit` is passed (story.md stays clean; the audit trail exists).
- New probe kind `revision`: "what did the system originally believe about X, and why did it
  change?" — answerable ONLY if supersession preserved the retired claim. This is the probe
  that makes the schema pay measured rent (per the ladder rule: every rung must earn its cost).

### V2.4 Acceptance

- [ ] Law enforced: build-time hard error on OBSERVED-targeting supersession (negative test).
- [ ] Re-run bake-off run 1 with supersession: the reacquire case now answers pt_count with the
      candidate split ("1 if same object (occlusion), 2 if new — evidence: no-component gap")
      and the `revision` probe passes. Bytes overhead vs plain rung B measured and reported
      (expected: small; if > ~20% revisit the field encoding).
- [ ] All prior bake-off probes still pass (no regression).

**Estimated size:** 1 day.

---

## V3 — Tracker upgrades + the real-video ladder

**Goal:** extend the viola's motion authority to the failure modes v2 documented (merge-drag,
long occlusion, textured background) and then walk it up the real-video tiers. Every change is
gated by the V1 scorer on seeded scenes; graduation is scored on held-out seeds AND one held-out
video.

### V3.1 Velocity/direction freeze during OCCLUDED (smallest diff first)

- `tracker.elisa` already has the OCCLUDED state and `TR_DIR/TR_EXT/TR_STARTX`. Change: while a
  track is OCCLUDED, **stop integrating direction/extreme state** (freeze at last observed
  values); on reacquire, re-seed direction from the first MOVE_MIN of post-reacquire motion
  instead of trusting coasted state. This is OC-SORT's observation-centric idea adapted to grid
  components — no Kalman needed at this scale.
- New scenegen scene (seeded): `occlude-reverse` — object enters occluder moving right, exits
  moving LEFT. Current tracker gets the exit direction wrong (coasted state); frozen tracker
  re-measures. Trap probe: direction-after-reacquire.

### V3.2 Tentative reacquisition + candidate identity sets

- On reacquire near a VANISH/OCCLUDED site, emit `INFERRED REACQUIRE` with a **candidate set**
  (`same:track-17 | new-object`) and per-candidate confidence from gate distance + size match +
  color match (the palette letter is already in the grid — a free, honest appearance signal that
  is NOT learned re-ID; use it only as a candidate-set discriminator, per the debate's weakened
  rule).
- Candidates write into V2's supersession schema. A later contradiction (both candidates seen
  simultaneously) *disputes* the same-identity candidate — the first live supersession.

### V3.3 Two-dimensional global translation (generalize `SHIFT`)

- Encoder currently detects vertical `SHIFT dy=`. Add horizontal: `SHIFT dx= dy=` (integer grid
  cells, detected by the same row/column-match scan transposed). Format bump is additive —
  `dy`-only lines remain valid; tracker parses both.
- **Affine is explicitly deferred** until integer 2-D translation measurably fails on an R1
  fixture (the debate's earn-your-complexity constraint; record the trigger condition here:
  "an R1/R2 fixture where per-frame residual after best integer translation still touches
  > 40% of cells during a pan").

### V3.4 Residual segmentation (simultaneous global + local motion)

- After compensating the detected translation, run component extraction on the residual grid so
  an object moving DURING a scroll is still tracked. New seeded scene: `scroll-plus-motion`
  (background scrolls dy=2/frame while a square moves horizontally). Currently conflated;
  post-V3.4 both motions reported separately (`INF global-motion dy=2`, `INF track-1 RIGHT`).

### V3.5 Per-stage confidence split

- Separate confidences on detection (component quality: area, stability), association (gate
  margin), and event interpretation (VANISH vs OCCLUDED alternatives) instead of one blended
  number. These feed the V1.8 calibration report — measured, not asserted.

### V3.6 The real-video ladder (run in this order, gold per §7)

1. **`PoP` (R1):** protagonist track through 2–3 rooms; gold = sparse annotated events
   (enters-left @t, vanishes-doorway @t, reappears @t, reverses @t). Target: presence/direction/
   reversal probes ≥ 80%; every miss documented with a frame pin.
2. **`pharo` (R1):** NOT an object-tracking exam — a triage+OCR exam. Gold = window/scroll/
   typing phases + 10 OCR strings. Tracker expected to report mostly global motion; that
   restraint (no fabricated object tracks during scrolling) IS the probe.
3. **`Police Stories` (R1):** multi-sprite; candidate-set stress.
4. **`Go` (R2):** stones-appear events vs the (partial, human-checked) move record; omission
   probes shine here — "did a stone appear in the upper-right between t1–t2?"
5. **`fencing` (R3, diagnostic only):** document degradation honestly — where components smear,
   what ACTIVITY reports, which claim classes survive (timing of light-flash events likely
   does; identity does not). Limits go in the report, not under the rug.
6. **GRADUATION (held-out):** `LSL2` segment ingested for the FIRST time, gold annotated by the
   user/inspection at annotation time, tracker + full V1 scorer run ONCE. The score is the
   score.

### V3.7 Acceptance

- [ ] Seeded occlude-reverse: direction-after-reacquire ≥ 95% on dev seeds, then held-out seeds.
- [ ] scroll-plus-motion: both motions separated on dev + held-out seeds.
- [ ] merge-drag trap (the v2 documented failure): candidate sets prevent the silent identity
      steal — the merge emits disputed candidates instead of a confident wrong track.
- [ ] All 9 original suites + V1 twins still green (no regression — the traps are now the
      regression suite, which is their correct final role).
- [ ] PoP ≥ 80% on annotated probes; pharo restraint probe passes; LSL2 held-out run recorded
      in `eval/real_ladder.md` with per-claim-class table, whatever the number is.

**Estimated size:** 4–6 days. The biggest milestone; V3.1→V3.5 are separately committable.

---

## V4 — Closed-vocabulary SED audition (the audio middle tier)

**Goal:** a sound-event classifier between the cymbal (exact DSP) and the sax (generative),
admitted **per class**, never as a model. Architecture cannot invent timestamps or narratives —
but "can't confabulate" ≠ "calibrated", so it takes the same exam as everyone.

### V4.1 Candidate + harness

- Baseline candidate: PANNs CNN14 (AudioSet-tagging, well-understood, runs on CPU/MPS). It is a
  *baseline*, not a selection — if a lighter/better SED clears the same gate later, swap.
- `screensed.py` + shim, mirroring `screenaud`: input 16 kHz mono window → top-k (class, score,
  window-time) tuples. Own venv only if its transformers/torch pins conflict (lesson learned:
  check `config.json` pins BEFORE first run).

### V4.2 The exam (synthetic + real, per class)

- Synthetic: audiogen scenes (it knows gold). Expect near-ceiling on tone/transient — that's a
  smoke test, not admission.
- Real: extracted audio from the video corpus — boxing (impacts, bell, crowd), darts (throws,
  crowd roar, announcer), Go/chess commentary (speech, stone clicks), pharo (keyboard, UI
  sounds, near-silence), fencing (blade contact, appel, referee). Gold: sparse human-checked
  event annotations (§7), ~10–15 events per clip.
- Per-class report: precision/recall per claimed class on real audio. **Admission rule:** a
  class becomes admissible evidence iff precision ≥ threshold (start 0.8) on ≥ 10 real
  instances; everything else stays `INFERRED, low-trust, inadmissible`. Expect a SUBSET of
  AudioSet's ontology to survive desktop/broadcast audio — that subset is the deliverable.

### V4.3 Orchestra integration

- Admitted classes emit into the ledger as `INFERRED` with `license: sed:<class>@<precision>`;
  the cymbal remains the ONLY timing authority (SED windows are coarse; the cymbal's transient
  timestamps refine them — a cymbal transient inside an SED "impact" window is the AV-sync
  join, and per the debate: **temporal coincidence is OBSERVED; causation is INFERRED** — the
  I10 wording, adopted verbatim into SPEC.md invariants).

### V4.4 Acceptance

- [ ] Per-class P/R table on ≥ 4 real clips committed to `eval/sed_audition.md`.
- [ ] At least the classes {speech, music, crowd, impact-like} measured; admitted set explicit.
- [ ] Twin/omission probes from V1 applied: "was there speech in 0–30 s?" twins with "was it
      silent?"; omission recall on annotated real events.
- [ ] Sax re-scoped in SPEC.md: escalation-only (rich description on demand), never presence/
      absence/timestamp authority — same epistemic tier as the violin.

**Estimated size:** 2 days.

---

## V5 — Temporal-sensitivity experiment

**Goal:** run the scoped invariance law at scale, as an eval filter (NOT decoding-time TCD).

- Inputs: 3 synthetic seeded scenes + 2 real segments (PoP, boxing) × 5 conditions each
  (original / freeze / reverse / shuffle / repeat1, via `arch_tool mangle` + ffmpeg equivalents
  for the VLM's mp4 path).
- Members examined: violin (Qwen2.5-VL-3B — the current describe), sax, and the viola as
  control (expected: near-zero temporal claims on mangled input — verify).
- Metric: `temporal_grounding` per claim class. Deliverable: `eval/temporal_grounding.md` — for
  each member, WHICH claim classes are actually grounded in temporal evidence vs invariant
  priors. This becomes the fine-grained I8 trust table (per-claim-class trust, replacing the
  current coarse motion/static split, if the data shows finer structure).
- **Acceptance:** the report exists with all 25 runs; the I8 table in SPEC.md is regenerated
  from measurements; any VLM claim class that turns out temporally grounded (possible! e.g.
  gross scene-change detection) gets its trust RAISED — the gate must be able to open, not only
  close, or it's dogma rather than measurement.

**Estimated size:** 1–2 days (mostly compute babysitting).

---

## V6 — Long-running integrated trial

**Goal:** the full orchestra on hours of real material — the failure modes that only appear at
duration: ledger growth, timestamp drift, revision chains, queue pressure, crash recovery.

### V6.1 The consent-free variant (default): video-driven

The videos make a long trial possible WITHOUT live capture of the user's session: `vidingest`
streams `I Tested If Size Matters In Every Sport` (long, scene-varied) or a playlist of R1+R2
segments in real time (batches emitted at wall-clock pace), all members subscribed, singer
building the rung-B+ ledger continuously.

- Duration: ≥ 2 hours continuous.
- Live probes injected every ~10 min (retention: early facts; omission: recent real events;
  revision: at least one forced supersession via an occlusion event).
- Measured: RSS of every member over time (flat or bounded), batch queue depth under churn
  (R3 segments = worst case), ledger size growth rate + projection latency, probe scores
  vs time-in-session (retention decay curve), recovery: `kill -9` the singer mid-session,
  restart, verify it rebuilds working state from ledger + archive (the crash/recovery exam —
  this is what append-only + evidence pins are FOR).

### V6.2 The live variant (user-initiated only)

Same battery on a real screen session + `audiocap` system audio. **Runs only when the user
starts it** — screen and audio capture of the user's actual session is never initiated
autonomously. This is also `audiocap`'s deferred live verification slot.

### V6.3 Acceptance

- [ ] 2-hour video-driven run completes; all metrics logged to `eval/longrun.md`.
- [ ] Memory bounded (no member RSS grows unbounded; ledger growth linear in EVENTS not time).
- [ ] Singer crash-recovery: post-restart probe scores within noise of pre-crash.
- [ ] At least 3 genuine supersessions occurred and project correctly with `--audit`.

**Estimated size:** 2 days of runs + instrumentation.

---

## §7 Cross-cutting protocols

### Gold annotation for real videos (sparse, honest, cheap)

1. Choose a 60–180 s segment (manifest records `t0/dur` + source sha256).
2. Generate a contact sheet (`arch_tool replay` keyframes → grid montage) + audio waveform plot.
3. Annotate 8–20 SPARSE events/facts a human can verify from the sheet in minutes — never
   dense labeling. Store as standard `truth.jsonl`.
4. Probes authored from gold BEFORE any member runs on the segment (no peeking — probes written
   from the annotation, not from system output).
5. Held-out videos: steps 1–4 happen at graduation time only, and the member runs ONCE.

### The audition gate (replaces "mechanistic claim required")

**Expected information gain must justify integration + evaluation cost.** Mechanistic claims
(adversarial-negative training, frame differencing, temporal objectives, measurement heads)
raise expected gain; integration cost (custom preprocessing, gated access, uncertain MPS) lowers
it. Cheap tests of null hypotheses are fine (Qwen3-VL-2B precedent); expensive ones need a
reason to expect a different answer (Marlin stays parked unless its gate cost drops to ~zero via
the user's token, in which case `eval/marlin_audition.py` runs as-is).

### Multi-agent convergence policy

The four-model consensus that produced this plan is **hypothesis generation and adversarial
review, not empirical validation** — the models share ancestry and context; their errors are
correlated. Validation is exclusively: measured traps, held-out seeds, held-out videos,
long-duration operation. No design change lands citing consensus alone.

### Standing carry-overs from v2

- `audiocap` live verification — waits for V6.2 (user-initiated).
- Marlin-2B literal audition — parked at the gate; harness committed and ready.
- Recent-preprint rule: no citation-derived design detail enters the repo without a fetched
  abstract; MoHallBench/MemStrata numbers are treated as unverified until read.

---

## Risk register

| risk | mitigation |
|---|---|
| ffmpeg pipe plumbing from Elisa (popen extern) is fiddly | temp-raw-file fallback is 20 lines and still deterministic; optimize later |
| real-video grids at 192-wide lose small objects (table-tennis ball ≈ sub-cell) | that IS a finding — document the resolution/object-size limit with numbers; try `--width 256` (encoder max) for R3 |
| seeded scenegen reveals overfit (score collapse on seeds) | good — that's V1 doing its job; the gap becomes V3's baseline |
| PANNs domain shift worse than expected (few classes admitted) | the admitted-set-is-the-deliverable framing already covers this; a small honest set beats a large fake one |
| broadcast videos have scene CUTS (no continuity at all) | ACTIVITY should classify `switching`; tracker must emit track-end on keyframe resync, not spurious VANISH events — add a cut-detection probe to V1 |
| annotation gold is itself wrong | keep gold sparse + human-verifiable from the contact sheet; every probe carries an evidence pin so disputes are resolvable |
| 2-hour run finds a crash in a member | that's the point; fix and re-run — V6 is last for a reason |

## Definition of done (v3)

1. V0–V6 acceptance boxes all checked, results committed under `eval/`.
2. The trap suite (now: fixed scenes + twins + metamorphic pairs + dev seeds) is green and has
   formally become the regression suite.
3. Held-out results (seeds 1000+, LSL2, and any other held-out opened at graduation) reported
   as-is in `eval/real_ladder.md` — including failures.
4. SPEC.md updated: I10 (coincidence-vs-causation) verbatim, per-claim-class I8 table from V5
   measurements, SED tier + admitted classes, supersession law, the constitution sentence.
5. story.md remains a projection of the rung-B+ ledger; C/D still unbuilt unless a V6 retrieval
   probe fails in a way identities/graph would have caught (the ladder rule stands).
