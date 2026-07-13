#!/bin/sh
# trap_test.sh — the VLM trap-test, end to end and reproducible (cursor_vlm_plan.md §4).
# Renders a scenegen fixture (deterministic, through the real encoder, Tier-A ring included), stages
# its authored truth+probes, runs each describe probe through screenvlm, and scores perception +
# confabulation with score_memory.py. No watcher in the loop; the VLM is on trial directly.
#
#   eval/trap_test.sh <scene> [frames] [run_dir]
#     scene    scenegen scene == scenario name: motion | motion-trap | counter | counter-skip
#     frames   screenvlm frames per probe (default: each probe's own; e.g. 8/16/32 for density)
#     run_dir  fixture dir (default /tmp/tt_<scene>)
set -e
SCENE=${1:?usage: trap_test.sh <scene> [frames] [run_dir]}
FRAMES=$2
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
RUN=${3:-/tmp/tt_$SCENE}
SCEN="$HERE/scenarios/$SCENE"
PY="$REPO/.venv-vlm/bin/python"; [ -x "$PY" ] || PY="${SCREENVLM_PYTHON:-python3}"

[ -d "$SCEN" ] || { echo "no scenario dir $SCEN" >&2; exit 1; }

echo "== render fixture: $SCENE -> $RUN"
rm -rf "$RUN"
"$REPO/scenegen" "$SCENE" "$RUN" >/dev/null
cp "$SCEN/truth.jsonl" "$SCEN/probes.jsonl" "$RUN/"

echo "== probe (screenvlm, one call per probe${FRAMES:+, ${FRAMES} frames}${MODEL:+, model=$MODEL})"
set --
[ -n "$FRAMES" ] && set -- "$@" --frames "$FRAMES"
[ -n "$MODEL" ] && set -- "$@" --model "$MODEL"
"$PY" "$HERE/vlm_probe.py" "$RUN" "$@"

echo "== score"
"$PY" "$HERE/score_memory.py" "$RUN" --arch-tool "$REPO/arch_tool"
