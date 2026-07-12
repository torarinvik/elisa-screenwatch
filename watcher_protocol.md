# Screen-watcher memory protocol

The watcher is a cheap, short-lived LLM agent that reads the delta-encoded batch stream
produced by `frame_dump` and maintains an *external* understanding of what's on screen. The
external memory is the point: a watcher session is ephemeral (it ends, or its context is
compacted), but its understanding must survive so you can rotate fresh watchers over an
unbounded stream. The memory files ARE the handoff.

## Files

| Path | Discipline | Cap | Purpose |
|------|-----------|-----|---------|
| `/tmp/screen_batches/latest.txt` | read | — | newest batch number (one integer) |
| `/tmp/screen_batches/batch_<n>.txt` | read | — | one delta-encoded 3s video chunk |
| `/tmp/screen_watch/state.md` | **rewritten every cycle** | ≤ 2 KB | working memory / sketchpad |
| `/tmp/screen_watch/log.md` | **append-only** | — | episodic memory w/ evidence pointers |

The write disciplines are load-bearing:

- `state.md` is **overwritten**, never appended. Rewriting forces consolidation — every cycle
  the model must decide what still matters enough to keep under the 2 KB cap. That size limit
  *is* the "importance determines forgetting" mechanism. If you append instead, it just becomes
  a second context window that fills up.
- `log.md` is **append-only** and grows slowly: one line only at an *event boundary* (scene
  change, activity change, something anomalous), each carrying an evidence pointer back into the
  retained batch files. The claim lives in the log; the pixels live in `batch_<n>.txt`;
  re-verification is a file read. "Forget representation, not evidence."

## Batch format (what you read)

```
BATCH <b> frames=<F> <w>x<h> fps=<fps> t0=<ms> cap=<tok>
KEYFRAME 0 t=<ms>
ASCII
<h rows: luminance ramp " .:-=+*#%@", dark->bright>
COLOR
<h rows: hue letters R O Y G C B M (uppercase=bright, lowercase=dim); grayscale cells use the ramp>
FRAME 1 t=<ms>
SAME                      # frame identical to the previous emitted frame
FRAME 2 t=<ms>
SHIFT dy=-3               # (optional) content scrolled 3 rows up since last emitted frame
ROWS 40-41               # changed row-range(s); full row content follows
<rows>
BATCH_END emitted=<E> changed_rows=<R> bytes=<N> rate=<K>
```

Read the KEYFRAME fully — that's the scene. Read the deltas as *motion evidence*: `SAME` runs =
still; `ROWS` clusters = localized activity (typing, cursor, a button); `SHIFT` = scrolling;
mid-batch `KEYFRAME` or a high `changed_rows` = a big change (window switch, video). `rate=K>1`
in the trailer means the batch was so churny it was downsampled — note that as "high motion,
detail reduced." Evidence pointer form: `[batch <b> f<i> rows<a>-<b>]`.

## The cycle (one iteration)

1. **Inherit.** Read `state.md` if it exists — that's the previous watcher's understanding. If
   absent, cold start (note it).
2. **Poll.** Read `latest.txt`. If it equals the last batch you processed, wait ~2s and re-poll.
   Otherwise read `batch_<latest>.txt`. (If it jumped by >1, you skipped batches while busy —
   note the gap; the skipped batch files may still be on disk within the retention window.)
3. **Perceive.** Reconstruct the scene from the keyframe; scan deltas for motion.
4. **Revise, don't append.** Rewrite `state.md` in place (see template). Update beliefs — if new
   evidence contradicts a prior hypothesis, *change* it, don't stack a new note beside the old.
5. **Consolidate.** Only if an event boundary occurred, append ONE line to `log.md` with an
   evidence pointer.
6. Loop to 2.

## `state.md` template (rewrite to this shape, keep under 2 KB)

```markdown
# Screen state — updated batch <b> (t=<ms>)

## Now
- Window/app: <what's in focus>
- Activity: <still | typing | scrolling | switching | video>
- Notable: <cursor region, dialog, error, anything salient>

## Observed vs inferred
- Observed: <facts read directly from pixels>
- Inferred: <interpretation, with confidence>
- Unknown: <what you can't tell yet>

## Hypothesis
- <current best explanation of what the user is doing / what's happening>

## Open questions
- <what to look for in upcoming batches>

## Seen
- Last batch: <b>   |   watchers this session: <n>
```

## `log.md` entry format (append only, event boundaries only)

```
<hh:mm:ss or t=ms> — <one-sentence consolidated event>  [batch <b> f<i>]
```

Rules that prevent drift:
- Separate **observed** from **inferred** so repeated summarization can't turn a guess into a fact.
- Every log claim keeps an evidence pointer; when uncertain later, reopen that batch file.
- Prefer rewriting the story over lengthening it. High detail while a moment is live; compress to
  the causal essence once it's past.
