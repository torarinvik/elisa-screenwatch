#!/usr/bin/env python3
"""track_probe.py — answer a scenario's motion probes from the VIOLA (tracker) records, writing
answers.jsonl for score_memory.py. This is the tracker twin of vlm_probe.py: where the VLM was put
on trial by describe, the symbolic tracker is put on trial by the SAME probes — so the two members'
answers land in one comparable table (orchestra_v2_plan.md M2).

Each probe carries an "op" telling this script what to compute from the tracker's OBS/INF records:
  count            distinct objects that ever appeared            -> a number
  direction        net centroid sign over span [t0,t1]            -> "left" | "right"
  reversal         any REVERSE event?                             -> "yes" | "no"
  reversal_zone    REVERSE event bucketed by cx/dw                 -> "left" | "middle" | "right"
  position         centroid at the end of span vs dw/2            -> "left" | "right"
  vanish_gap       any frame with ncomp==0 inside span [t0,t1]    -> "yes" | "no"
  continuous       no ncomp==0 gap anywhere in the clip           -> "yes" | "no"
  occluded         any OCCLUDED event?                            -> "yes" | "no"
An op that cannot be resolved yields "" (an honest miss, never a fabricated answer).

  track_probe.py <run_dir> [--tracker PATH] [--out answers.jsonl]
<run_dir> holds the fixture (batch_*.txt from scenegen) + staged probes.jsonl.
"""
import argparse
import json
import os
import subprocess
import sys


def parse_records(text):
    """tracker stdout -> (frames, tracks, events).
    frames: list of (t, ncomp, dw)
    tracks: dict t -> list of (id, cx, cy, dir, state)
    events: list of (id, kind, t, cx, cy, conf)
    """
    frames, events = [], []
    tracks = {}
    for ln in text.splitlines():
        p = ln.split()
        if not p:
            continue
        kv = {}
        for tok in p:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k] = v
        if p[0] == "OBS" and len(p) > 1 and p[1] == "frame":
            frames.append((int(kv["t"]), int(kv["ncomp"]), int(kv.get("dw", 0))))
        elif p[0] == "INF" and len(p) > 1 and p[1] == "track":
            t = int(kv["t"])
            tracks.setdefault(t, []).append(
                (int(kv["id"]), int(kv["cx"]), int(kv["cy"]), int(kv["dir"]), kv.get("state", "A")))
        elif p[0] == "INF" and len(p) > 1 and p[1] == "event":
            events.append((int(kv["id"]), kv["kind"], int(kv["t"]),
                           int(kv["cx"]), int(kv["cy"]), int(kv.get("conf", 0))))
    return frames, tracks, events


def dw_of(frames):
    for _, _, dw in frames:
        if dw:
            return dw
    return 0


def track_cx_over_span(tracks, t0, t1):
    """centroids (t, cx) of the busiest/consistent track within [t0,t1], flattened across ids."""
    pts = []
    for t, rows in sorted(tracks.items()):
        if t0 <= t <= t1:
            for (tid, cx, cy, d, st) in rows:
                pts.append((t, cx))
    return pts


def answer(op, probe, frames, tracks, events):
    dw = dw_of(frames)
    span = probe.get("span", [0, 10 ** 12])
    t0, t1 = span[0], span[1]

    if op == "count":
        # peak simultaneous objects — the honest "how many objects on screen" (a vanish+reappear is
        # never two-at-once, so motion-trap's one physical object reads 1, not 2 track segments).
        return str(max((nc for (_, nc, _) in frames), default=0))

    if op == "two_directions":
        # do a net-rightward and a net-leftward track co-exist? (two independently moving objects)
        signs = set()
        first, last = {}, {}
        for t, rows in sorted(tracks.items()):
            for (tid, cx, cy, d, st) in rows:
                if tid not in first:
                    first[tid] = cx
                last[tid] = cx
        for tid in first:
            net = last[tid] - first[tid]
            if net > 3:
                signs.add("right")
            elif net < -3:
                signs.add("left")
        return "yes" if ("right" in signs and "left" in signs) else "no"

    if op == "direction":
        pts = track_cx_over_span(tracks, t0, t1)
        if len(pts) < 2:
            return ""
        net = pts[-1][1] - pts[0][1]
        return "right" if net > 0 else ("left" if net < 0 else "")

    if op == "direction_after_reacquire":
        # V3.1/V3.2: after the object reappears from behind an occluder, which way is it moving? Prefer a
        # tracker REACQUIRE (same id kept across a short occlusion); else fall back to the last APPEAR —
        # the re-emergence born as a NEW track, which the ledger pairs as a REACQUIRE_CANDIDATE (V2). In
        # both cases follow that track's OWN id (the occluder is a separate static track — don't average).
        reacq = [e for e in events if e[1] == "REACQUIRE"]
        if reacq:
            rid, rt = reacq[0][0], reacq[0][2]
        else:
            apps = [e for e in events if e[1] == "APPEAR"]
            if not apps:
                return ""
            rid, rt = apps[-1][0], apps[-1][2]
        pts = [(t, cx) for t, rows in sorted(tracks.items()) if t >= rt
               for (tid, cx, cy, d, st) in rows if tid == rid]
        if len(pts) < 2:
            return ""
        net = pts[-1][1] - pts[0][1]
        return "right" if net > 0 else ("left" if net < 0 else "")

    if op == "reversal":
        return "yes" if any(e[1] == "REVERSE" for e in events) else "no"

    if op == "reversal_zone":
        revs = [e for e in events if e[1] == "REVERSE" and t0 <= e[2] <= t1]
        if not revs or not dw:
            return ""
        cx = revs[0][3]
        frac = cx / dw
        return "left" if frac < 0.25 else ("right" if frac > 0.75 else "middle")

    if op == "position":
        pts = track_cx_over_span(tracks, t0, t1)
        if not pts or not dw:
            return ""
        cx = pts[-1][1]
        return "left" if cx < dw / 2 else "right"

    if op == "vanish_gap":
        return "yes" if any(nc == 0 for (t, nc, _) in frames if t0 <= t <= t1) else "no"

    if op == "continuous":
        return "no" if any(nc == 0 for (t, nc, _) in frames) else "yes"

    if op == "occluded":
        return "yes" if any(e[1] == "OCCLUDED" for e in events) else "no"

    if op == "move_before_arrival":
        # relation op (V1.3b): did the RIGHT object start moving before the LEFT object reached it?
        # probe["arr_cx"] = the approacher's centroid column at contact (given by the generator).
        # Uses rightmost/leftmost trajectories, not track ids — robust to id churn at proximity.
        arr = probe.get("arr_cx")
        if arr is None:
            return ""
        seq = []
        for t, rows in sorted(tracks.items()):
            if rows:
                cxs = [cx for (_, cx, _, _, _) in rows]
                seq.append((t, max(cxs), min(cxs)))
        if not seq:
            return ""
        b0 = seq[0][1]
        move_t = next((t for (t, mx, _) in seq if mx >= b0 + 3), None)
        arrive_t = next((t for (t, _, mn) in seq if mn >= arr - 1), None)
        if move_t is None:
            return "no"
        if arrive_t is None:
            return "yes"
        return "yes" if move_t < arrive_t - 200 else "no"

    return ""


def main():
    ap = argparse.ArgumentParser(prog="track_probe")
    ap.add_argument("run_dir")
    ap.add_argument("--tracker", default=None)
    ap.add_argument("--out", default="answers.jsonl")
    a = ap.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tracker = a.tracker or os.path.join(repo, "tracker")
    probes_path = os.path.join(a.run_dir, "probes.jsonl")
    if not os.path.exists(probes_path):
        sys.exit(f"track_probe: no probes.jsonl in {a.run_dir}")
    probes = [json.loads(l) for l in open(probes_path) if l.strip()]

    r = subprocess.run([tracker, "run", a.run_dir], capture_output=True, text=True)
    frames, tracks, events = parse_records(r.stdout)

    out_path = os.path.join(a.run_dir, a.out)
    with open(out_path, "w") as out:
        for p in probes:
            ans = answer(p.get("op", ""), p, frames, tracks, events)
            out.write(json.dumps({"id": p["id"], "answer": ans}) + "\n")
    print(f"track_probe: {len(frames)} frames, {len({e[0] for e in events if e[1]=='APPEAR'})} objects, "
          f"{len(events)} events -> {a.out}")


if __name__ == "__main__":
    main()
