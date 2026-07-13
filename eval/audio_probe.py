#!/usr/bin/env python3
"""audio_probe.py — answer a scenario's audio probes from the CYMBAL (audiotriage) events, writing
answers.jsonl for score_memory.py. The audio twin of track_probe.py: the deterministic audio detector
is put on trial by authored probes, scored by the same matchers (orchestra_v2 plan M5).

Each probe carries an "op" computed from the AUDIO event lines:
  transient_count    count TRANSIENT events (optionally within probe["span"])   -> a number
  tone_count         count TONE events                                          -> a number
  level_shift_count  count LEVEL_SHIFT events                                    -> a number
  has_silence        any SILENCE_START?                                         -> yes|no
  has_level_shift    any LEVEL_SHIFT?                                            -> yes|no
  transient_near     any TRANSIENT within probe["tol"] ms of probe["at"] ms     -> yes|no
  silence_near       any SILENCE_START within tol of at                         -> yes|no
  tone_freq          frequency (Hz) of the first TONE                           -> a number

  audio_probe.py <run_dir> [--audiotriage PATH] [--wav in.wav] [--out answers.jsonl]
"""
import argparse
import json
import os
import subprocess
import sys


def parse_events(text):
    ev = []
    for ln in text.splitlines():
        p = ln.split()
        if len(p) < 2 or p[0] != "AUDIO":
            continue
        kv = {}
        for tok in p[2:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k] = v
        ev.append((p[1], int(kv.get("t", 0)), int(kv.get("freq", 0)), int(kv.get("dur", 0))))
    return ev


def answer(op, probe, ev):
    span = probe.get("span")
    if op == "transient_count":
        ts = [e for e in ev if e[0] == "TRANSIENT"]
        if span:
            ts = [e for e in ts if span[0] <= e[1] <= span[1]]
        return str(len(ts))
    if op == "tone_count":
        return str(len([e for e in ev if e[0] == "TONE"]))
    if op == "level_shift_count":
        return str(len([e for e in ev if e[0] == "LEVEL_SHIFT"]))
    if op == "has_silence":
        return "yes" if any(e[0] == "SILENCE_START" for e in ev) else "no"
    if op == "has_level_shift":
        return "yes" if any(e[0] == "LEVEL_SHIFT" for e in ev) else "no"
    if op == "transient_near":
        at, tol = probe["at"], probe.get("tol", 100)
        return "yes" if any(e[0] == "TRANSIENT" and abs(e[1] - at) <= tol for e in ev) else "no"
    if op == "silence_near":
        at, tol = probe["at"], probe.get("tol", 300)
        return "yes" if any(e[0] == "SILENCE_START" and abs(e[1] - at) <= tol for e in ev) else "no"
    if op == "tone_freq":
        for e in ev:
            if e[0] == "TONE":
                return str(e[2])
        return ""
    return ""


def main():
    ap = argparse.ArgumentParser(prog="audio_probe")
    ap.add_argument("run_dir")
    ap.add_argument("--audiotriage", default=None)
    ap.add_argument("--wav", default="scene.wav")
    ap.add_argument("--out", default="answers.jsonl")
    a = ap.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    at = a.audiotriage or os.path.join(repo, "audiotriage")
    wav = os.path.join(a.run_dir, a.wav)
    probes_path = os.path.join(a.run_dir, "probes.jsonl")
    if not os.path.exists(probes_path):
        sys.exit(f"audio_probe: no probes.jsonl in {a.run_dir}")
    if not os.path.exists(wav):
        sys.exit(f"audio_probe: no {wav}")
    probes = [json.loads(l) for l in open(probes_path) if l.strip()]

    r = subprocess.run([at, wav], capture_output=True, text=True)
    ev = parse_events(r.stdout)

    out_path = os.path.join(a.run_dir, a.out)
    with open(out_path, "w") as out:
        for p in probes:
            out.write(json.dumps({"id": p["id"], "answer": answer(p.get("op", ""), p, ev)}) + "\n")
    kinds = {}
    for e in ev:
        kinds[e[0]] = kinds.get(e[0], 0) + 1
    print(f"audio_probe: {len(ev)} events {kinds} -> {a.out}")


if __name__ == "__main__":
    main()
