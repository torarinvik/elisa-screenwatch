#!/usr/bin/env python3
"""score.py — grade the recorder's ACTIVITY triage against a scripted ground-truth session.

Usage: score.py <batch_dir> [truth_log=/tmp/screen_eval_truth.log]

Alignment: batch t0 is recorder-relative, so we anchor on each batch FILE's mtime (epoch of
the atomic rename, i.e. the batch's end) and treat the batch as covering [mtime-3s, mtime].
A batch is graded against the truth phase covering its midpoint. Batches straddling a phase
boundary (midpoint within 1.5s of a transition) are scored leniently (either side accepted).

Tolerance mapping (a terminal window covers only part of the screen, so full-grid signals
like SHIFT may not fire; these are the labels we accept per truth phase):
  still     -> {still}
  typing    -> {typing, scrolling}          (terminal echo scrolls once past the fold)
  scrolling -> {scrolling, typing}          (partial-screen scroll may not clear SHIFT's 70% gate)
  video     -> {video, switching}
"""
import sys, os, re, glob

ACCEPT = {
    "still": {"still"},
    "typing": {"typing", "scrolling"},
    "scrolling": {"scrolling", "typing"},
    "video": {"video", "switching"},
}

def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: score.py <batch_dir> [truth_log]")
    batch_dir = sys.argv[1]
    truth_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/screen_eval_truth.log"

    phases = []  # (start_ms, label)
    for line in open(truth_path):
        ts, name = line.split()
        label = name.replace("begin_", "")
        phases.append((int(ts), label))
    if not phases or phases[-1][1] != "end":
        raise SystemExit("truth log incomplete (no end marker)")

    def phase_at(ms):
        cur = None
        for start, label in phases:
            if ms >= start:
                cur = (start, label)
        nxt = next(((s, l) for s, l in phases if s > ms), None)
        return cur, nxt

    session_start, session_end = phases[0][0], phases[-1][0]
    rows, correct, lenient_hits, graded = [], 0, 0, 0
    paths = [p for p in glob.glob(os.path.join(batch_dir, "batch_*.txt"))
             if re.fullmatch(r"batch_\d+\.txt", os.path.basename(p))]
    for path in sorted(paths, key=lambda p: int(re.search(r"batch_(\d+)", p).group(1))):
        end_ms = int(os.path.getmtime(path) * 1000)
        mid_ms = end_ms - 1500
        if mid_ms < session_start or mid_ms > session_end:
            continue
        with open(path) as f:
            f.readline()
            f.readline()
            act_line = f.readline().split()
        got = act_line[1] if len(act_line) >= 2 else "?"
        (pstart, truth), nxt = phase_at(mid_ms)
        if truth == "end":
            continue
        graded += 1
        ok = got in ACCEPT.get(truth, {truth})
        boundary = (mid_ms - pstart) < 1500 or (nxt and (nxt[0] - mid_ms) < 1500)
        if not ok and boundary:
            prev_label = next((l for s, l in reversed(phases) if s < pstart), truth)
            nxt_label = nxt[1] if nxt else truth
            ok = got in ACCEPT.get(prev_label, set()) | ACCEPT.get(nxt_label, set())
            lenient_hits += 1 if ok else 0
        correct += 1 if ok else 0
        rows.append((os.path.basename(path), truth, got, "ok" if ok else "MISS",
                     "boundary" if boundary else ""))

    for r in rows:
        print(f"{r[0]:>16}  truth={r[1]:<10} got={r[2]:<10} {r[3]:<4} {r[4]}")
    if graded == 0:
        raise SystemExit("no batches overlapped the truth session — was the recorder running?")
    print(f"\nscore: {correct}/{graded} = {100*correct/graded:.0f}%  "
          f"({lenient_hits} accepted at phase boundaries)")

if __name__ == "__main__":
    main()
