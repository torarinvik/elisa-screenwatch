#!/usr/bin/env python3
"""marlin_audition.py — the M8 audition harness for NemoStation/Marlin-2B (a coarse video captioner,
a Qwen3.5-2B fine-tune). Everything is wired; the ONLY thing missing is gated-repo access, which is a
one-time USER action (accept the model's terms on HuggingFace + provide a token) — the assistant may
not create accounts or accept terms. Once you have access, this runs end to end.

SETUP (one time, by the user):
  1. Create/sign in to a HuggingFace account and open https://huggingface.co/NemoStation/Marlin-2B
  2. Click "Agree and access repository" (accept the gated terms).
  3. Create a token at https://huggingface.co/settings/tokens and either:
       export HF_TOKEN=hf_...        # then run this script, OR
       huggingface-cli login         # stores the token, then run this script

RUN:
  .venv-vlm/bin/python eval/marlin_audition.py            # captions + finds + motion-trap probes
It reuses the screenvlm harness's transformers stack (Marlin is Qwen3.5-2B-based) and torchcodec for
video decode (installed). It builds an mp4 from the motion-trap fixture (arch_tool replay -> ffmpeg)
if one is not present at /tmp/mar_mt.mp4.

Expected result (per the M7 family finding): Marlin, trained at 2 FPS / 240 frames, should PRIOR-FILL
the motion traps — a coarse captioner, never the motion authority. This harness records whether that
holds and prints Marlin's caption/events + its find() span for the vanish.
"""
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = "/tmp/mar_mt.mp4"
FIXTURE = "/tmp/mar_mt"


def ensure_video():
    if os.path.exists(VIDEO):
        return
    print("building test mp4 from the motion-trap fixture...", flush=True)
    subprocess.run([os.path.join(REPO, "scenegen"), "motion-trap", FIXTURE],
                   check=True, capture_output=True)
    frames = "/tmp/mar_frames"
    os.makedirs(frames, exist_ok=True)
    subprocess.run([os.path.join(REPO, "arch_tool"), "replay", FIXTURE, "0", "199", "1",
                    f"{frames}/f"], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-framerate", "10", "-start_number", "0",
                    "-i", f"{frames}/f%d.ppm", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-r", "10", VIDEO], check=True, capture_output=True)


def main():
    from huggingface_hub.utils import get_token
    if not (os.environ.get("HF_TOKEN") or get_token()):
        sys.exit("marlin_audition: no HF token. Marlin-2B is a GATED repo — see this file's header:\n"
                 "  accept terms at https://huggingface.co/NemoStation/Marlin-2B, then\n"
                 "  export HF_TOKEN=hf_...  (or huggingface-cli login) and re-run.")
    import torch
    from transformers import AutoModelForCausalLM
    ensure_video()

    dev = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"loading Marlin-2B on {dev}...", flush=True)
    t = time.time()
    try:
        m = AutoModelForCausalLM.from_pretrained("NemoStation/Marlin-2B", trust_remote_code=True,
                                                 dtype=torch.float16).to(dev).eval()
    except Exception as e:
        sys.exit(f"marlin_audition: load failed ({type(e).__name__}): {str(e)[:200]}\n"
                 "if this is a 401/gated error, the token lacks access — accept the terms first.")
    print(f"loaded in {time.time()-t:.0f}s", flush=True)

    r = m.caption(VIDEO)
    print("\nCAPTION:")
    print("  scene:", r.get("scene", "")[:500])
    for ev in r.get("events", [])[:16]:
        print(f"  <{ev['start']:.1f}-{ev['end']:.1f}> {ev['description']}")

    f = m.find(VIDEO, event="the bright square disappears or vanishes")
    print(f"\nFIND vanish: span={f.get('span')} format_ok={f.get('format_ok')}")
    print("\nInterpretation: does the caption mention the 2s vanish (t=8-10s) and the mid-field "
          "reversal (t=14s), or does it report smooth continuous motion (prior-fill)? Compare to the "
          "viola's exact answer (VANISH@9.2s, REVERSE mid-field) — the motion authority.")


if __name__ == "__main__":
    main()
