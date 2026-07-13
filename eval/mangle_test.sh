#!/bin/sh
# mangle_test.sh — the temporal-grounding exam (orchestra_v3_plan.md V1.4). Answer a fixture's
# probes on the ORIGINAL and on each temporally-destroyed variant (eval/mangle.sh), then apply the
# scoped law: a TEMPORAL claim answered identically on original and destroyed input is SUSPECT
# (the answer wasn't grounded in temporal evidence); STATIC claims are expected to be invariant
# and are never penalized. Metric: temporal_grounding = grounded temporal probes / temporal probes.
#
# The static|temporal axis is a property of what the op computes, not a per-probe annotation:
#   temporal: reversal reversal_zone direction two_directions vanish_gap occluded continuous
#   static:   count position (and all audio content ops)
# NOTE "continuous" is permutation-invariant (reverse/shuffle preserve the visibility SET), so it
# is examined only under freeze/repeat1; direction-family ops are examined under all modes.
#
#   eval/mangle_test.sh <scene> [seed]        (tracker scenes; default seed 0)
set -e
SCENE=${1:?usage: mangle_test.sh <scene> [seed]}
SEED=${2:-0}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
PY="$REPO/.venv-vlm/bin/python"; [ -x "$PY" ] || PY="${SCREENVLM_PYTHON:-python3}"

BASE=/tmp/mangle_orig
rm -rf "$BASE"
"$REPO/scenegen" "$SCENE" "$BASE" --seed "$SEED" >/dev/null
"$PY" "$HERE/track_probe.py" "$BASE" >/dev/null 2>&1

for mode in freeze repeat1 reverse shuffle; do
    "$HERE/mangle.sh" "$BASE" "/tmp/mangle_$mode" "$mode" >/dev/null
    "$PY" "$HERE/track_probe.py" "/tmp/mangle_$mode" >/dev/null 2>&1
done

"$PY" - "$BASE" <<'PYEOF'
import json, sys
base = sys.argv[1]
TEMPORAL = {"reversal","reversal_zone","direction","two_directions","vanish_gap","occluded","continuous"}
PERM_INVARIANT = {"continuous"}          # visibility-set ops: examine only under freeze/repeat1
MODES = ["freeze","repeat1","reverse","shuffle"]
def load(d):
    return {json.loads(l)["id"]: json.loads(l)["answer"] for l in open(f"{d}/answers.jsonl") if l.strip()}
probes = [json.loads(l) for l in open(f"{base}/probes.jsonl") if l.strip()]
orig = load(base)
mang = {m: load(f"/tmp/mangle_{m}") for m in MODES}
# On a frozen clip the true answer of each temporal op is KNOWN (nothing happens): a probe whose
# original gold already equals that static gold is UNTESTABLE by destruction — the control cannot
# flip its gold, so an unchanged answer is correct, not prior-driven. (Metamorphic rule: the
# control must change the expected answer.)
STATIC_GOLD = {"continuous":"yes","vanish_gap":"no","reversal":"no","occluded":"no","two_directions":"no"}
n = g = 0
print(f"{'probe':14} {'op':16} {'orig':8} " + " ".join(f"{m:8}" for m in MODES) + " verdict")
for p in probes:
    op = p.get("op") or ""
    if not op: continue
    pid = p["id"]; o = str(orig.get(pid,"")).strip()
    row = {m: str(mang[m].get(pid,"")).strip() for m in MODES}
    if op in TEMPORAL:
        if op in STATIC_GOLD and str(p.get("gold","")).strip() == STATIC_GOLD[op]:
            verdict = "untestable"
        else:
            modes = ["freeze","repeat1"] if op in PERM_INVARIANT else MODES
            changed = any(row[m] != o for m in modes)
            n += 1; g += changed
            verdict = "grounded" if changed else "SUSPECT"
    else:
        verdict = "static"
    print(f"{pid:14} {op:16} {o:8} " + " ".join(f"{row[m]:8}" for m in MODES) + f" {verdict}")
print()
print(f"temporal_grounding: {g}/{n}")
sys.exit(0 if n == 0 or g == n else 1)
PYEOF
