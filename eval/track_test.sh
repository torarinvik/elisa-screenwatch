#!/bin/sh
# track_test.sh — the tracker (viola) trap-test, end to end and reproducible (orchestra_v2_plan.md M2).
# Renders a scenegen fixture (deterministic, through the real encoder, Tier-A ring included), stages
# its authored truth+probes, answers each motion probe from the SYMBOLIC tracker records (no model),
# and scores perception with score_memory.py — the same scorer the VLM trap-test uses, so the viola's
# row lands next to the violin's.
#
#   eval/track_test.sh <scene> [run_dir]
#     scene    scenegen scene == scenario name: motion | motion-trap | crossing-swap | occlude-vanish
#     run_dir  fixture dir (default /tmp/kt_<scene>)
set -e
SCENE=${1:?usage: track_test.sh <scene> [run_dir]}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
RUN=${2:-/tmp/kt_$SCENE}
SCEN="$HERE/scenarios/$SCENE"
PY="$REPO/.venv-vlm/bin/python"; [ -x "$PY" ] || PY="${SCREENVLM_PYTHON:-python3}"

[ -d "$SCEN" ] || { echo "no scenario dir $SCEN" >&2; exit 1; }

echo "== render fixture: $SCENE -> $RUN"
rm -rf "$RUN"
"$REPO/scenegen" "$SCENE" "$RUN" >/dev/null
cp "$SCEN/truth.jsonl" "$SCEN/probes.jsonl" "$RUN/"

echo "== probe (tracker, symbolic — one pass over the whole run)"
"$PY" "$HERE/track_probe.py" "$RUN"

echo "== score"
"$PY" "$HERE/score_memory.py" "$RUN" --arch-tool "$REPO/arch_tool"
