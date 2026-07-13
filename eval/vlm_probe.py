#!/usr/bin/env python3
"""vlm_probe.py — run a scenario's describe probes through screenvlm against a fixture ring, writing
answers.jsonl for score_memory.py. This is the VLM TRAP-TEST harness (cursor_vlm_plan.md §4): the
violin is scored the way counter-skip scored the watcher — one screenvlm invocation per probe, no
watcher in the loop, greedy decode for reproducibility.

Each probe in probes.jsonl carries a describe span (and optional region/frames):
  {"id":"pt_vanish", ..., "span":[6000,12000], "q":"...", "gold":"yes", "match":"boolean",
   "region":[x,y,w,h]?, "frames":N?}

<run_dir> must hold BOTH the fixture's Tier-A ring (arch_*.idx/.bin, from scenegen) and the staged
truth.jsonl + probes.jsonl. Writes <run_dir>/answers.jsonl (default) as {id, answer, evidence,
cost, q}; an evidence-exhausted probe yields an honest empty answer (a miss, never a confab).

  vlm_probe.py <run_dir> [--frames N] [--screenvlm PATH] [--out answers.jsonl]
"""
import argparse
import json
import os
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(prog="vlm_probe")
    ap.add_argument("run_dir")
    ap.add_argument("--frames", type=int, default=None, help="override every probe's frame count")
    ap.add_argument("--model", default=None, help="screenvlm --model override (e.g. the 7B audition)")
    ap.add_argument("--screenvlm", default=None)
    ap.add_argument("--out", default="answers.jsonl")
    a = ap.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    svlm = a.screenvlm or os.path.join(repo, "screenvlm")
    probes_path = os.path.join(a.run_dir, "probes.jsonl")
    if not os.path.exists(probes_path):
        sys.exit(f"vlm_probe: no probes.jsonl in {a.run_dir}")
    probes = [json.loads(l) for l in open(probes_path) if l.strip()]

    out_path = os.path.join(a.run_dir, a.out)
    with open(out_path, "w") as out:
        for p in probes:
            span = p["span"]
            frames = a.frames if a.frames else p.get("frames", 16)
            cmd = [svlm, a.run_dir, "--span", f"{span[0]},{span[1]}",
                   "--frames", str(frames), "--q", p["q"], "--json"]
            if a.model:
                cmd += ["--model", a.model]
            if "region" in p:
                cmd += ["--region", ",".join(str(v) for v in p["region"])]
            r = subprocess.run(cmd, capture_output=True, text=True)
            answer, evidence, cost = "", None, None
            lines = [ln for ln in r.stdout.strip().splitlines() if ln.strip()]
            if lines:
                try:
                    j = json.loads(lines[-1])
                    answer = j.get("answer", "")
                    evidence, cost = j.get("evidence"), j.get("cost")
                except json.JSONDecodeError:
                    answer = ""
            if not answer and r.returncode not in (0, 1):
                # true error (bad args etc.) vs evidence-exhausted — surface it
                print(f"  ! {p['id']}: screenvlm exit {r.returncode}: {r.stderr.strip()[:160]}",
                      file=sys.stderr)
            rec = {"id": p["id"], "answer": answer, "evidence": evidence, "cost": cost, "q": p["q"]}
            out.write(json.dumps(rec) + "\n")
            tag = f"[{frames}f]"
            print(f"  {p['id']:16} {tag:6} gold={p['gold']:8} -> {answer[:90]}")

    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
