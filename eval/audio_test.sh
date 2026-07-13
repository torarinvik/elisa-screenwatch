#!/bin/sh
# audio_test.sh — the cymbal (audiotriage) trap-test, deterministic and CI-runnable (orchestra_v2
# plan M5). Renders an audiogen WAV, answers each audio probe from the SYMBOLIC detector events (no
# model), and scores with score_memory.py — the same scorer the viola/violin trap-tests use. This is
# the DIRECT PCM path (no live capture); the played-through-capture path validates audiocap later.
#
#   eval/audio_test.sh <scene> [run_dir]
#     scene    audiogen scene == scenario name: transient-in-noise | silence-gap | level-ramp
#              | tone-alarm | av-sync
set -e
SCENE=${1:?usage: audio_test.sh <scene> [run_dir]}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
RUN=${2:-/tmp/au_$SCENE}
SCEN="$HERE/scenarios/$SCENE"
PY="$REPO/.venv-vlm/bin/python"; [ -x "$PY" ] || PY="${SCREENVLM_PYTHON:-python3}"

[ -d "$SCEN" ] || { echo "no scenario dir $SCEN" >&2; exit 1; }

echo "== render WAV: $SCENE -> $RUN"
rm -rf "$RUN"; mkdir -p "$RUN"
"$REPO/audiogen" "$SCENE" "$RUN/scene.wav" >/dev/null
cp "$SCEN/truth.jsonl" "$SCEN/probes.jsonl" "$RUN/"

echo "== probe (audiotriage, symbolic)"
"$PY" "$HERE/audio_probe.py" "$RUN"

echo "== score"
"$PY" "$HERE/score_memory.py" "$RUN"
