#!/usr/bin/env bash
# mangle.sh — temporal-destruction control (orchestra_v3_plan.md V1.4): rebuild a fixture with the
# temporal structure destroyed but per-frame content intact. Implemented as a composition of
# already-verified stages rather than a new encoder path: arch_tool replay (Tier-A archive ->
# bit-exact PPMs) -> deterministic reorder -> ffmpeg lossless (ffv1) -> vidingest (-> batch dir).
#
#   mangle.sh <fixture_dir> <out_dir> <mode> [fps] [width]
#     mode   freeze  — frame 0 held for the whole clip
#            repeat1 — the MIDDLE frame held (same control at a different content sample:
#                      catches probes that happen to be answerable from frame 0)
#            reverse — exact frame order reversed
#            shuffle — deterministic permutation (fixed LCG, same order every run)
#
# Gold does NOT travel: truth/probes are copied so probe tooling runs, but only the V1.4 scoring
# rule applies — a TEMPORAL claim answered identically on original and mangled input is suspect;
# STATIC claims are expected to be invariant.
set -euo pipefail

FIX=${1:?usage: mangle.sh <fixture_dir> <out_dir> <mode> [fps] [width]}
OUT=${2:?out_dir}
MODE=${3:?mode: freeze|repeat1|reverse|shuffle}
FPS=${4:-10}
W=${5:-192}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
TMP=$(mktemp -d /tmp/mangle.XXXXXX)
trap 'rm -rf "$TMP"' EXIT

n=$("$REPO/arch_tool" replay "$FIX" 0 999999 1 "$TMP/f_" | sed -n 's/arch_tool: replayed \([0-9]*\) frames/\1/p')
[[ -n "$n" && "$n" -gt 0 ]] || { echo "mangle: no frames replayed from $FIX" >&2; exit 1; }

python3 - "$TMP" "$MODE" "$n" <<'PY'
import os, sys
tmp, mode, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
if mode == "freeze":    order = [0] * n
elif mode == "repeat1": order = [n // 2] * n
elif mode == "reverse": order = list(range(n - 1, -1, -1))
elif mode == "shuffle":
    order = list(range(n)); s = 42
    for i in range(n - 1, 0, -1):           # Fisher-Yates with a fixed LCG — same order every run
        s = (s * 1103515245 + 12345) % (1 << 31)
        j = s % (i + 1)
        order[i], order[j] = order[j], order[i]
else: sys.exit(f"mangle: unknown mode {mode}")
for k, src in enumerate(order):
    os.link(f"{tmp}/f_{src}.ppm", f"{tmp}/m_{k:06d}.ppm")
PY

ffmpeg -nostdin -hide_banner -loglevel error -framerate "$FPS" -i "$TMP/m_%06d.ppm" \
    -c:v ffv1 -pix_fmt bgr0 -y "$TMP/mangled.mkv"

rm -rf "$OUT"
"$REPO/vidingest" "$TMP/mangled.mkv" "$OUT" --fps "$FPS" --width "$W" >/dev/null

for g in truth.jsonl probes.jsonl; do
    [[ -f "$FIX/$g" ]] && cp "$FIX/$g" "$OUT/$g"
done
echo "mangle: $MODE ($n frames) -> $OUT"
