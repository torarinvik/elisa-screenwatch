#!/usr/bin/env python3
"""restraint_census.py — annotation-free restraint metrics for a real-video fixture, across genres,
so the V3.0 trackability gate is designed on DIVERSE evidence and not overfit to the pharo cursor.

Reads the tracker's stdout on an already-ingested fixture and reports, with NO gold:
  - track count and event mix (APPEAR/VANISH/OCCLUDED/REVERSE/REACQUIRE)
  - birth/death churn per second
  - the applicability lens from the pharo t=14 inspection (eval/scenarios/real/pharo/t14_inspection.md):
      * each track's median component AREA -> class tiny(<30)/small/large  (cursor-scale vs real object)
      * peak |vx| and REVERSEs emitted while |vx| was non-physical (a velocity-implausibility flag)
      * sole-small-mover fraction: frames whose only non-static-bar component is a single tiny blob
        (the pharo cursor signature: "a tiny sole mover over full-width static chrome is a UI pointer")

The point is NOT a pass/fail bar — it is to expose that restraint has DIFFERENT correct answers per
genre: suppress the pharo cursor, but do NOT suppress a real Prince-of-Persia sprite. A gate tuned only
on pharo would over-suppress; this census is the guard against that.

  restraint_census.py <fixture_dir> [--label NAME] [--tracker ./tracker]
"""
import argparse, os, subprocess, sys, statistics

AREA_TINY, AREA_SMALL = 30, 400          # grid-px: cursor ~6-10; small sprite; large = bars/big objects
VX_IMPLAUSIBLE = 35                       # grid-px/frame: > ~1/5 frame width per 100ms — not a real object
BAR_MIN_WIDTH_FRAC = 0.85                 # a component spanning >=85% of grid width is static chrome (bar)


def parse_tracker(fixture, tracker):
    r = subprocess.run([tracker, "run", fixture], capture_output=True, text=True)
    frames = {}          # t -> list of comps (cx,cy,area,w)
    tracks = {}          # id -> list of (t,cx,cy,vx)
    events = []          # (kind,id,t)
    gw = 192
    for ln in r.stdout.splitlines():
        p = ln.split()
        if not p:
            continue
        if p[0] == "OBS" and p[1] == "frame":
            kv = dict(tok.split("=", 1) for tok in p if "=" in tok)
            frames.setdefault(int(kv["t"]), [])
            gw = int(kv.get("dw", gw))
        elif p[0] == "OBS" and p[1] == "comp":
            kv = dict(tok.split("=", 1) for tok in p if "=" in tok)
            t = int(kv["t"])
            bx = kv.get("bbox", "0,0,0,0").split(",")
            w = abs(int(bx[2]) - int(bx[0])) if len(bx) == 4 else 0
            frames.setdefault(t, []).append((int(kv["cx"]), int(kv["cy"]), int(kv.get("area", 0)), w))
        elif p[0] == "INF" and p[1] == "track":
            kv = dict(tok.split("=", 1) for tok in p if "=" in tok)
            tracks.setdefault(kv["id"], []).append(
                (int(kv["t"]), int(kv["cx"]), int(kv["cy"]), int(kv.get("vx", 0))))
        elif p[0] == "INF" and p[1] == "event":
            kv = dict(tok.split("=", 1) for tok in p if "=" in tok)
            events.append((kv["kind"], kv["id"], int(kv["t"])))
    return frames, tracks, events, gw


def track_area(tid, samples, frames):
    """Median area of the component nearest each of the track's positions (independent per frame)."""
    areas = []
    for t, cx, cy, _vx in samples:
        comps = frames.get(t, [])
        if not comps:
            continue
        best = min(comps, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
        if (best[0] - cx) ** 2 + (best[1] - cy) ** 2 <= 100:      # within ~10px -> it's this track
            areas.append(best[2])
    return statistics.median(areas) if areas else 0


def census(fixture, label):
    tracker = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tracker")
    frames, tracks, events, gw = parse_tracker(fixture, tracker)
    if not frames:
        print(f"{label}: no frames (ingest missing?)"); return
    ts = sorted(frames)
    dur_s = max(1e-3, (ts[-1] - ts[0]) / 1000)
    kinds = {}
    for k, _i, _t in events:
        kinds[k] = kinds.get(k, 0) + 1
    n_appear, n_vanish = kinds.get("APPEAR", 0), kinds.get("VANISH", 0)
    churn = (n_appear + n_vanish) / dur_s

    # area class per track
    cls = {"tiny": 0, "small": 0, "large": 0}
    for tid, samples in tracks.items():
        a = track_area(tid, samples, frames)
        cls["tiny" if a < AREA_TINY else "small" if a < AREA_SMALL else "large"] += 1

    # peak |vx|, and REVERSEs emitted at non-physical speed
    peak_vx = max((abs(v) for s in tracks.values() for (_t, _x, _y, v) in s), default=0)
    rev_hi = 0
    for k, tid, t in events:
        if k != "REVERSE":
            continue
        near = [abs(v) for (tt, _x, _y, v) in tracks.get(tid, []) if abs(tt - t) <= 200]
        if near and max(near) >= VX_IMPLAUSIBLE:
            rev_hi += 1

    # sole-small-mover fraction (the pharo cursor signature)
    sole = 0
    for t in ts:
        comps = frames[t]
        movers = [c for c in comps if c[3] < BAR_MIN_WIDTH_FRAC * gw and c[2] < AREA_SMALL]
        bars = [c for c in comps if c[3] >= BAR_MIN_WIDTH_FRAC * gw]
        if len(movers) == 1 and movers[0][2] < AREA_TINY and len(comps) == len(bars) + 1:
            sole += 1
    sole_frac = sole / len(ts)

    print(f"{label:16} tracks={len(tracks):3d}  "
          f"AP={n_appear:3d} VA={n_vanish:3d} OC={kinds.get('OCCLUDED',0):3d} "
          f"RE={kinds.get('REVERSE',0):3d} RQ={kinds.get('REACQUIRE',0):3d}  "
          f"churn={churn:4.1f}/s  area[tiny/sm/lg]={cls['tiny']}/{cls['small']}/{cls['large']}  "
          f"peak|vx|={peak_vx:3d} revHiVx={rev_hi}  soleSmallMover={sole_frac*100:4.0f}%")


def main():
    ap = argparse.ArgumentParser(prog="restraint_census")
    ap.add_argument("fixture")
    ap.add_argument("--label", default=None)
    a = ap.parse_args()
    census(a.fixture, a.label or os.path.basename(a.fixture.rstrip("/")))


if __name__ == "__main__":
    main()
