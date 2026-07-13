#!/usr/bin/env bash
# make_fixture.sh — regenerate a real-video fixture (batches + wav) deterministically from its
# manifest (orchestra_v3_plan.md V0.3). Media lives in the gitignored videos/; only the manifest
# (and, once authored, truth/probes) is committed. Because vidingest uses synthetic segment-relative
# timestamps and a fixed ffmpeg decode, regenerating twice is bit-identical.
#
# The source sha256 is verified before generation: if the video changed, the fixture's committed
# gold no longer applies, so we STOP rather than silently produce a mislabeled fixture.
#
# USAGE: make_fixture.sh <manifest.json> [out_dir]
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: make_fixture.sh <manifest.json> [out_dir]" >&2
    exit 2
fi

manifest="$1"
scen_dir="$(cd "$(dirname "$manifest")" && pwd)"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"   # eval/scenarios/real -> repo root

# Parse the manifest into shell vars (KEY=VALUE lines; values are plain here).
eval "$(python3 - "$manifest" <<'PY'
import json, sys, shlex
m = json.load(open(sys.argv[1]))
for k in ("name", "video", "sha256", "t0", "dur", "fps", "width"):
    print(f'M_{k}={shlex.quote(str(m.get(k, "")))}')
print(f'M_audio={"1" if m.get("audio") else "0"}')
PY
)"

video_path="$repo/videos/$M_video"
out_dir="${2:-/tmp/fixture_$M_name}"

[[ -f "$video_path" ]] || { echo "make_fixture: video not found: $video_path" >&2; exit 1; }

# Guard: source must match the manifest's recorded hash, or the committed gold is invalid.
if [[ -n "$M_sha256" ]]; then
    actual="$(shasum -a 256 "$video_path" | awk '{print $1}')"
    if [[ "$actual" != "$M_sha256" ]]; then
        echo "make_fixture: source sha256 mismatch for $M_video" >&2
        echo "  manifest: $M_sha256" >&2
        echo "  actual:   $actual" >&2
        exit 1
    fi
fi

rm -rf "$out_dir"
mkdir -p "$out_dir"

"$repo/vidingest" "$video_path" "$out_dir" --fps "$M_fps" --width "$M_width" --t0 "$M_t0" --dur "$M_dur"
[[ "$M_audio" == "1" ]] && "$repo/audextract.sh" "$video_path" "$out_dir/scene.wav" --t0 "$M_t0" --dur "$M_dur"

# Stage gold into the run dir if it has been authored (scorer/probe tools read it from there).
for g in truth.jsonl probes.jsonl; do
    [[ -f "$scen_dir/$g" ]] && cp "$scen_dir/$g" "$out_dir/$g"
done

echo "make_fixture: $M_name -> $out_dir"
