#!/bin/sh
# longrun.sh — the deterministic half of the V6 long-running trial (orchestra_v3_plan.md V6.1).
# Drives vidingest -> tracker -> ledger over a longer real segment and measures the properties V6
# cares about that DON'T need the 2-hour LLM-in-the-loop singer:
#   - ledger growth is LINEAR IN EVENTS (bytes/record ~ constant across increasing batch prefixes),
#   - projection latency stays bounded,
#   - the ledger REBUILD from batches is byte-identical (the crash-recovery foundation: re-running
#     from the archive reconstructs identical working state, since timestamps are synthetic/replayable),
#   - the one law (supersedes -> INFERRED only) holds on real footage.
# The 2-hour wall-clock run, per-member RSS curves, queue depth, and the live kill -9 restart under the
# singer loop are the RESOURCE-GATED remainder (need the running singer) — see V6.3 status.
#
#   eval/longrun.sh <video> <t0_s> <dur_s> [fps] [width]
set -e
VID=${1:?usage: longrun.sh <video> <t0_s> <dur_s> [fps] [width]}
T0=${2:?t0_s}
DUR=${3:?dur_s}
FPS=${4:-10}
W=${5:-192}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
PY="$REPO/.venv-vlm/bin/python"; [ -x "$PY" ] || PY="${SCREENVLM_PYTHON:-python3}"
D=/tmp/longrun_fix; rm -rf "$D"

echo "== ingest $DUR s @ fps=$FPS from t0=$T0 =="
"$REPO/vidingest" "$VID" "$D" --fps "$FPS" --width "$W" --t0 "$T0" --dur "$DUR" >/dev/null 2>&1
NB=$(ls "$D"/batch_*.txt 2>/dev/null | wc -l | tr -d ' ')
echo "ingested $NB batches"
[ "$NB" -ge 3 ] || { echo "too few batches"; exit 1; }

echo "== ledger growth over increasing batch prefixes (linear in EVENTS?) =="
printf "%-8s %8s %10s %10s %10s\n" batches records bytes b/rec proj_ms
for k in $(seq 2 3 "$NB"); do
    P=/tmp/longrun_pfx; rm -rf "$P"; mkdir -p "$P"
    i=0; while [ "$i" -lt "$k" ]; do cp "$D/batch_$i.txt" "$P/" 2>/dev/null || true; i=$((i+1)); done
    "$PY" "$HERE/ledger.py" build "$P" >/dev/null 2>&1 || continue
    rec=$(wc -l < "$P/ledger.jsonl"); byt=$(wc -c < "$P/ledger.jsonl")
    brec=$([ "$rec" -gt 0 ] && echo $((byt/rec)) || echo 0)
    t0ms=$("$PY" -c "import time;print(int(time.time()*1000))")
    "$PY" "$HERE/ledger.py" project "$P" >/dev/null 2>&1
    t1ms=$("$PY" -c "import time;print(int(time.time()*1000))")
    printf "%-8s %8s %10s %10s %10s\n" "$k" "$rec" "$byt" "$brec" "$((t1ms-t0ms))"
done

echo "== crash-recovery foundation: rebuild byte-identical? =="
"$PY" "$HERE/ledger.py" build "$D" >/dev/null 2>&1
cp "$D/ledger.jsonl" /tmp/longrun_a.jsonl
"$PY" "$HERE/ledger.py" build "$D" >/dev/null 2>&1
if diff -q /tmp/longrun_a.jsonl "$D/ledger.jsonl" >/dev/null; then
    echo "REBUILD BYTE-IDENTICAL ✓"
else
    echo "REBUILD MISMATCH ✗"; exit 1
fi
sup=$("$PY" -c "import json;print(sum(1 for l in open('$D/ledger.jsonl') if json.loads(l).get('supersedes') is not None))")
echo "== law + supersessions on real footage =="
"$PY" "$HERE/ledger.py" validate "$D" | tail -1
echo "supersessions: $sup"
