# Screen-Understanding Orchestra — System Contracts (SPEC)

This document is the single source of truth for the interfaces between orchestra members.
A member may be rewritten freely; these contracts may only change with a version bump.

## Invariants

- **I1** Neural members interpret; they never assert what a symbolic member could measure.
- **I2** Claims flow forward; evidence stays randomly accessible backward (retention window).
- **I3** Members communicate only via the stream + blackboard files — no direct member calls.
- **I4** Every stream section is ignorable by readers that don't know it (versioned, sectioned).
- **I5** Attention pyramid: each tier wakes the next on signal only (plus the singer's slow heartbeat).
- **I6** Every neural claim carries an evidence pointer; every re-watch is a specific question with a budget.

## Members

| Role | Component | Kind |
|---|---|---|
| Drums | delta encoder (`frame_dump`, Elisa) | symbolic, always-on |
| Bass | ACTIVITY triage (inside `frame_dump`) | symbolic, per batch |
| Guitar | `screenocr` (Swift/Vision CLI) | symbolic, on-demand + scene-change |
| Singer | stream watcher (cheap LLM agent) | neural, event-woken |
| Boss | orchestrator (stronger LLM agent) | neural, escalation-woken |
| Referee | eval harness (`eval/`) | offline scoring |

## Directory layout & ownership

```
/tmp/screen_batches/            owner: recorder (except *.ocr.txt: screenocr/ocr_watch)
  batch_<n>.txt                 delta-encoded text chunk (stream format v2)
  batch_<n>.jpg                 full-res keyframe image (same instant as the text keyframe)
  batch_<n>.ocr.txt             OCR annotation (lazy or eager)
  arch_<s>.bin / arch_<s>.idx   Tier A exact-frame ring (see "Archival fidelity tiers")
  latest.txt                    newest complete batch number

/tmp/screen_watch/              the blackboard
  goal.md                       owner: user/boss — what matters right now
  state.md                      owner: singer — REWRITTEN each cycle, <= 2 KB
  log.md                        owner: singer(+boss consolidations) — APPEND-ONLY
  escalation.md                 owner: singer — overwrite-style mailbox to the boss
  queries/q_<id>.md             owner: boss — one active-perception question
  queries/q_<id>.answer.md      owner: the dispatched sub-watcher
```

Single writer per file; every write is atomic (tmp + rename) or a single append.

## Stream format v2

```
BATCH <b> v=2 frames=<F> <w>x<h> fps=<fps> t0=<ms> cap=<tok>
STATS same=<s> shifted=<sh> keyframes=<k> churn_rows=<c> img=<batch_<b>.jpg|none>
ACTIVITY <still|typing|scrolling|video|switching> conf=<0-100>
KEYFRAME 0 t=<ms>
ASCII
<h rows of w luminance chars " .:-=+*#%@">
COLOR
<h rows: hue letters R O Y G C B M, uppercase=bright / lowercase=dim; grayscale uses the ramp>
FRAME <i> t=<ms>
SAME | [SHIFT dy=<d>] ROWS <a>-<b> + row content ...
... (KEYFRAME <i> may reappear mid-batch on a churn resync)
BATCH_END emitted=<E> changed_rows=<R> bytes=<N> rate=<K>
```

- `v=2` is the format version; readers must reject a major version they don't know.
- `STATS`: `same` = SAME frames, `shifted` = frames carrying SHIFT, `keyframes` = keyframe count
  including frame 0, `churn_rows` = total changed rows, `img` = the sidecar image filename or `none`.
- `ACTIVITY` is the bass's verdict (rules below). `conf` is a coarse 0–100.
- Unknown lines between the header and `KEYFRAME 0` must be skipped by readers (I4).

### Triage rules (bass), applied in priority order to the finished batch

1. `video`     — rate > 1, or mid-batch keyframes >= 2, or churn_rows >= emitted * h * 4/10
2. `switching` — exactly 1 mid-batch keyframe and churn otherwise below the video bar
3. `scrolling` — any SHIFT frame
4. `still`     — churn_rows <= h/8 and same >= 90% of emitted frames
5. `typing`    — everything else (light localized change)

Confidence: 90 when the winning rule's signal is >= 2x its threshold (or, for `still`, when
churn_rows == 0); else 60.

### Grid ↔ pixel mapping (for zoom queries)

Text cell (col cx, row cy) on a w×h grid over a W×H screen covers the pixel rectangle:

```
x0 = cx * W / w      x1 = (cx+1) * W / w
y0 = cy * H / h      y1 = (cy+1) * H / h
```

Rows a–b of the grid = pixel band `[a*H/h, (b+1)*H/h)`. The `batch_<n>.jpg` is captured from
the same grab as the keyframe, so these coordinates are exact for the keyframe (and approximate
for later frames in the batch).

## Archival fidelity tiers

The model stream (batches) is lossless at GRID resolution by construction. Source-resolution
archival is tiered, and each tier states its guarantee honestly:

- **Tier A — exact ring** (`archive.elisa`, inside the recorder): every grabbed full-res frame,
  XOR-delta vs the previous frame + LZFSE, in segments of ~10s that each start with a keyframe
  (independently decodable). Ring bounded by a byte cap (`frame_dump` arg 8, MB, default 2048,
  0 = off); oldest segments pruned. **Bit-exactness is a TESTED property**: every index line
  carries a checksum of the raw frame, and `arch_tool verify <dir>` re-decodes the whole live
  ring and fails on any bit difference. `arch_tool extract <dir> <seq> <out.ppm>` recovers any
  archived frame. Timestamps share the batch timeline (ms since recorder start).
  Cost honesty: a calm screen keeps minutes-to-hours in the ring; full-screen video churn is
  MBs/frame and shrinks the window — that is the price of "exact", by design.
- **Tier B — high-fidelity, continuous** (planned): HEVC long-term recording. Labeled a
  high-fidelity archive, NOT lossless.
- **Tier C — evidence pinning** (planned): watcher/boss marks copy exact frames/crops out of the
  Tier A ring before pruning, so consolidated memory keeps exact evidence pointers.

## screenocr CLI contract

```
screenocr <image> [--crop x,y,w,h] [--min-conf 0.4]
```
stdout: one line per recognized string: `<x> <y> <w> <h> <conf> <text>` (pixel coords in the
FULL image's space even when cropped; conf 0–1). Exit 0 on success, 1 on unreadable image.
`batch_<n>.ocr.txt` holds the full-frame output for that batch's jpg.

## Query protocol (active perception)

`queries/q_<id>.md` (boss writes):
```markdown
# Query <id>
question: <one specific question>
type: temporal | spatial | zoom
evidence: [batch <b> f<i> rows <a>-<b>]
budget: <max sub-watcher dispatches>
deadline_batch: <give up after this batch number>
```

`queries/q_<id>.answer.md` (sub-watcher writes):
```markdown
# Answer <id>
status: answered | evidence-exhausted | pruned
answer: <the finding, observed/inferred separated>
evidence: [batch <b> f<i> ...]
```

Execution: temporal → read the pointed batch range closely; spatial → read only the pointed
rows of the keyframe grid; zoom → map rows to pixels (formula above), run
`screenocr batch_<b>.jpg --crop ...`, read the strings.

Stopping rules (hard): <= 3 queries per escalation; an `evidence-exhausted`/`pruned` question
is recorded under state.md's Unknown and never re-asked for the same event; introspective
"do I understand?" is never a loop condition.

## Attention pyramid (who wakes whom)

recorder (always) → triage (free, per batch) → OCR (scene-change batches only)
→ singer (event boundary or ~30s heartbeat; `still` batches cost ~zero tokens)
→ boss (escalation.md changes only) → sub-watchers (bounded by query budgets).
