#!/usr/bin/env python3
"""ledger.py — the evidence ledger (orchestra_v2 plan M9, rung B of the representation ladder).

The ladder asks: story.md alone (A) vs an append-only typed event ledger with story.md as a *projection*
of it (B) vs +track identities (C) vs a full temporal graph (D). This tool builds rung B and its
projection from the SYMBOLIC members' event streams — the viola (tracker) and the cymbal (audiotriage)
— so the factual ledger is the source of truth and the narrative is derived, never independently edited
(I7). Each record keeps provenance, family, OBSERVED-vs-INFERRED, confidence, and an evidence pin — the
anti-confabulation spine (I8/I9). The A↔D *comparative* scoring still needs live watcher runs; this is
the deterministic ledger foundation those runs build on.

  ledger.py build   <fixture_dir> [--wav scene.wav]   # tracker + audiotriage events -> ledger.jsonl
  ledger.py project <fixture_dir>                      # ledger.jsonl -> story.md (deterministic)
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tracker_events(fixture):
    """viola INF events -> ledger records (family symbolic-tracker)."""
    tracker = os.path.join(REPO, "tracker")
    if not os.path.exists(os.path.join(fixture, "batch_0.txt")):
        return []
    r = subprocess.run([tracker, "run", fixture], capture_output=True, text=True)
    recs = []
    KIND = {"APPEAR": "object appears", "VANISH": "object vanishes",
            "REVERSE": "object reverses direction", "REACQUIRE": "object reacquired",
            "OCCLUDED": "object occluded (passes behind another)"}
    for ln in r.stdout.splitlines():
        p = ln.split()
        if len(p) < 2 or not (p[0] == "INF" and p[1] == "event"):
            continue
        kv = {}
        for tok in p:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k] = v
        t = int(kv["t"])
        recs.append({
            "t0": t, "t1": t, "kind": kv["kind"],
            "summary": f"{KIND.get(kv['kind'], kv['kind'])} (track {kv['id']}) at cx={kv.get('cx','?')}",
            "member": "viola", "family": "symbolic-tracker",
            "obs_or_inf": "INF", "conf": int(kv.get("conf", 0)),
            "object": f"o{kv['id']}",
            "evidence": f"[track id={kv['id']} t={t} cx={kv.get('cx','?')}]",
        })
    return recs


def audio_events(fixture, wav):
    """cymbal AUDIO events -> ledger records (family symbolic-audio)."""
    at = os.path.join(REPO, "audiotriage")
    wpath = os.path.join(fixture, wav)
    if not os.path.exists(wpath):
        return []
    r = subprocess.run([at, wpath], capture_output=True, text=True)
    recs = []
    KIND = {"TRANSIENT": "an impact/transient sound", "SILENCE_START": "audio goes silent",
            "SILENCE_END": "audio resumes", "TONE": "a sustained tone", "LEVEL_SHIFT": "sound level shifts"}
    for ln in r.stdout.splitlines():
        p = ln.split()
        if len(p) < 2 or p[0] != "AUDIO":
            continue
        kv = {}
        for tok in p[2:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k] = v
        t = int(kv.get("t", 0))
        extra = f" ({kv['freq']} Hz)" if "freq" in kv else ""
        recs.append({
            "t0": t, "t1": t + int(kv.get("dur", 0)), "kind": p[1],
            "summary": f"{KIND.get(p[1], p[1])}{extra}",
            "member": "cymbal", "family": "symbolic-audio",
            "obs_or_inf": "OBS", "conf": int(kv.get("conf", 0)),
            "object": "audio",
            "evidence": f"[aud {p[1]} t={t}{' dur='+kv['dur'] if 'dur' in kv else ''}]",
        })
    return recs


def build(fixture, wav):
    recs = tracker_events(fixture) + audio_events(fixture, wav)
    recs.sort(key=lambda r: (r["t0"], r["member"]))
    out = os.path.join(fixture, "ledger.jsonl")
    with open(out, "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    fams = {}
    for r in recs:
        fams[r["family"]] = fams.get(r["family"], 0) + 1
    print(f"ledger: {len(recs)} records {fams} -> ledger.jsonl")


def project(fixture):
    """Deterministic story.md projection: an EVENTS trace + DURABLE_OBJECTS, every line evidence-pinned.
    story.md is DERIVED from the ledger (I7): it never adds a claim the ledger does not carry."""
    path = os.path.join(fixture, "ledger.jsonl")
    if not os.path.exists(path):
        sys.exit("ledger: no ledger.jsonl (run build first)")
    recs = [json.loads(l) for l in open(path) if l.strip()]
    objs = {}
    for r in recs:
        objs.setdefault(r["object"], []).append(r)
    lines = ["# story.md (projected from ledger.jsonl — I7: derived, not independently edited)", "",
             "## EVENTS"]
    for r in recs:
        tag = "OBSERVED" if r["obs_or_inf"] == "OBS" else "INFERRED"
        lines.append(f"t={r['t0']} [{r['object']}] {r['summary']} — {tag}({r['member']},conf={r['conf']}) {r['evidence']}")
    lines += ["", "## DURABLE_OBJECTS"]
    for o, rs in sorted(objs.items()):
        kinds = ",".join(sorted({x["kind"] for x in rs}))
        lines.append(f"{o}: {len(rs)} events [{kinds}] family={rs[0]['family']}")
    out = os.path.join(fixture, "story.md")
    open(out, "w").write("\n".join(lines) + "\n")
    print(f"ledger: projected {len(recs)} events, {len(objs)} objects -> story.md")


def main():
    ap = argparse.ArgumentParser(prog="ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("fixture")
    b.add_argument("--wav", default="scene.wav")
    p = sub.add_parser("project")
    p.add_argument("fixture")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.fixture, a.wav)
    else:
        project(a.fixture)


if __name__ == "__main__":
    main()
