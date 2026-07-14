#!/bin/sh
# seed_test.sh — the seeded procedural battery (orchestra_v3_plan.md V1.5): run every tracker
# scene across a range of development seeds, answer each fixture's SELF-GENERATED probes from the
# symbolic tracker, and report the aggregate. This is the anti-overfit exam: parameters (positions,
# sizes, lanes, event times, mirroring) vary per seed and the gold is computed by scenegen from the
# same parameters, so a tracker cannot score by memorizing the seven fixed scenes.
#
#   eval/seed_test.sh [seed_lo] [seed_hi] [phase_ms]   (defaults 0 9 0; phase = V1.7 sub-batch
#   offset applied to every fixture so no event aligns to a 2 s batch boundary by accident)
#
# RESERVED SEEDS: >= 1000 are the held-out final-scoring pool. scenegen refuses them without
# --final; this runner never passes --final. Do not run reserved seeds during development.
set -e
LO=${1:-0}
HI=${2:-9}
PHASE=${3:-0}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
PY="$REPO/.venv-vlm/bin/python"; [ -x "$PY" ] || PY="${SCREENVLM_PYTHON:-python3}"

if [ "$HI" -ge 1000 ]; then
    echo "seed_test: seeds >= 1000 are RESERVED for final scoring; refusing" >&2
    exit 3
fi

total=0; correct=0
for scene in motion motion-trap crossing-swap occlude-vanish scroll-motion contact-merge launch occlude-reverse; do
    sc_c=0; sc_n=0
    seed=$LO
    while [ "$seed" -le "$HI" ]; do
        d=/tmp/seed_test_run
        rm -rf "$d"
        "$REPO/scenegen" "$scene" "$d" --seed "$seed" --phase "$PHASE" >/dev/null 2>&1
        "$PY" "$HERE/track_probe.py" "$d" >/dev/null 2>&1
        r=$("$PY" - "$d" <<'PYEOF'
import json, re, sys
d = sys.argv[1]
probes = {json.loads(l)["id"]: json.loads(l) for l in open(f"{d}/probes.jsonl") if l.strip()}
answers = {json.loads(l)["id"]: json.loads(l)["answer"] for l in open(f"{d}/answers.jsonl") if l.strip()}
def nb(s): s=str(s).strip().lower(); return "yes" if s in ("yes","true","1") else ("no" if s in ("no","false","0") else s)
n=c=0; fails=[]
for pid,p in probes.items():
    if not p.get("op"): continue
    n+=1; a=answers.get(pid,""); g=p["gold"]; m=p["match"]
    if m=="boolean": ok = nb(a)==nb(g)
    elif m=="substring": ok = str(g).lower() in str(a).lower()
    elif m=="numeric": ok = re.findall(r"-?\d+",str(a))[:1]==re.findall(r"-?\d+",str(g))[:1]
    else: ok = str(a).strip()==str(g).strip()
    c+=ok
    if not ok: fails.append(f"{pid}:gold={g},got={a!r}")
print(f"{c} {n} " + ";".join(fails))
PYEOF
)
        c=$(echo "$r" | cut -d' ' -f1); n=$(echo "$r" | cut -d' ' -f2); f=$(echo "$r" | cut -d' ' -f3-)
        total=$((total+n)); correct=$((correct+c)); sc_c=$((sc_c+c)); sc_n=$((sc_n+n))
        [ "$c" != "$n" ] && echo "MISS $scene seed=$seed: $f"
        seed=$((seed+1))
    done
    echo "$scene: $sc_c/$sc_n"
done
echo
echo "AGGREGATE: $correct/$total"
# acceptance bar (orchestra_v3_plan.md V1.9): >= 95%
pct=$((correct * 100 / total))
if [ "$pct" -lt 95 ]; then
    echo "seed_test: FAIL — aggregate ${pct}% below the 95% bar" >&2
    exit 1
fi
echo "seed_test: PASS (${pct}%)"
