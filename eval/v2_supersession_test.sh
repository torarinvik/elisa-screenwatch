#!/bin/sh
# v2_supersession_test.sh — acceptance for orchestra_v3_plan.md V2 (minimal supersession, rung B+).
# Deterministic, no agent/model runs: exercises the schema, THE ONE LAW, the candidate-split answer to
# the bake-off pt_count case, the `revision` probe, and the byte overhead vs plain rung B.
#
#   eval/v2_supersession_test.sh [seed]      (default 0)
set -e
SEED=${1:-0}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
PY="$REPO/.venv-vlm/bin/python"; [ -x "$PY" ] || PY="${SCREENVLM_PYTHON:-python3}"
L() { "$PY" "$HERE/ledger.py" "$@"; }
D=/tmp/v2_supersession; rm -rf "$D"
"$REPO/scenegen" motion-trap "$D" --seed "$SEED" >/dev/null 2>&1

fail() { echo "FAIL: $1" >&2; exit 1; }

# 1. Build with supersession — the motion-trap VANISH(o1)@7800 -> APPEAR(o2)@8600 reacquire pair.
L build "$D" --wav scene.wav >/dev/null
nsup=$("$PY" -c "import json;print(sum(1 for l in open('$D/ledger.jsonl') if json.loads(l)['supersedes'] is not None))")
[ "$nsup" = "1" ] || fail "expected 1 supersession, got $nsup"

# 2. THE ONE LAW is satisfied on the derived ledger.
L validate "$D" >/dev/null || fail "derived ledger failed validation"

# 3. Negative test: a supersedes -> OBSERVED record must hard-fail.
cat > /tmp/v2_bad.jsonl <<'J'
{"id":0,"t0":1000,"kind":"TRANSIENT","member":"cymbal","family":"symbolic-audio","obs_or_inf":"OBS","conf":80,"object":"audio","license":"cymbal:TRANSIENT","status":"active","supersedes":null,"evidence":"[e]"}
{"id":1,"t0":1000,"kind":"REINTERP","member":"viola","family":"symbolic-tracker","obs_or_inf":"INF","conf":50,"object":"o1","license":"viola:x","status":"active","supersedes":0,"evidence":"[e]"}
J
if L validate /tmp/v2_bad.jsonl >/dev/null 2>&1; then fail "law NOT enforced: OBSERVED-targeting supersession accepted"; fi

# 4. The bake-off pt_count case: projection carries the candidate split, not a flat "2".
L project "$D" >/dev/null
grep -q "1 distinct object if same, 2 if new" "$D/story.md" || fail "candidate split missing from projection"
grep -q "no-component gap" "$D/story.md" || fail "gap evidence missing from projection"
# Superseded VANISH is hidden from the clean story, preserved under --audit.
if grep -q "object vanishes" "$D/story.md"; then fail "clean projection leaked a superseded record"; fi
L project "$D" --audit >/dev/null
grep -q "RETIRED id=1.*object vanishes" "$D/story.md" || fail "audit trail did not preserve the retired VANISH"

# 5. The `revision` probe passes (answerable only because supersession preserved the retired claim).
L revision "$D" o1 | grep -q "ORIGINALLY believed: object vanishes" || fail "revision probe did not recover the original belief"

# 6. Byte overhead vs rung B.
L build "$D" --wav scene.wav >/dev/null; bplus=$(wc -c < "$D/ledger.jsonl")
L build "$D" --wav scene.wav --no-supersede >/dev/null; b=$(wc -c < "$D/ledger.jsonl")
L build "$D" --wav scene.wav >/dev/null   # leave the B+ ledger in place

echo "v2_supersession: PASS"
echo "  supersessions: $nsup   law: enforced (negative test hard-fails)"
echo "  pt_count: answered as candidate split {1 if same (occlusion), 2 if new} — no flat '2'"
echo "  revision probe: PASS   overhead: $((bplus-b)) bytes (rung B $b -> B+ $bplus) for the revision capability"