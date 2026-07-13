#!/bin/sh
# meta_test.sh — the metamorphic-pair battery (orchestra_v3_plan.md V1.2): for each (scene,
# variant) pair, generate the BASE fixture and the VARIANT fixture from the SAME seed (frames
# bit-identical up to the divergence moment, exactly one property changed), answer both fixtures'
# self-generated probes from the symbolic tracker, and score the FLIP probes with pair credit:
# a flip probe is credited only if it is answered correctly on BOTH sides. An answerer that gives
# the same answer to both sides is revealing a prior, and scores 0 even though one side was
# "right". Metric: metamorphic_sensitivity = credited flip pairs / total flip pairs.
#
#   eval/meta_test.sh [seed_lo] [seed_hi]        (defaults 0 9 — the first 10 dev seeds)
#
# Pairs and their flip probes (gold differs across the pair by construction):
#   motion      / no-reverse : sm_rev            (yes -> no)
#   motion-trap / no-vanish  : st_gap, st_cont   (yes -> no, no -> yes)
#   motion-trap / no-reverse : st_rev            (yes -> no)
#   launch      / early-launch: rl_order          (no -> yes; V1.3b relation_grounding)
# Audio pairs (audiogen fixed scenes; variant golds are given inline since the authored
# probes.jsonl carries only the base gold):
#   transient-in-noise / no-transient : atn_count (3 -> 0), atn_cluster (2 -> 0)
#   tone-alarm         / no-tone      : ata_count (3 -> 0)
#   av-sync            / no-transient : avs_impact (yes -> no), avs_count (1 -> 0)
#
# RESERVED SEEDS: >= 1000 are the held-out final-scoring pool; this runner refuses them.
set -e
LO=${1:-0}
HI=${2:-9}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
PY="$REPO/.venv-vlm/bin/python"; [ -x "$PY" ] || PY="${SCREENVLM_PYTHON:-python3}"

if [ "$HI" -ge 1000 ]; then
    echo "meta_test: seeds >= 1000 are RESERVED for final scoring; refusing" >&2
    exit 3
fi

total=0; credited=0
for pair in "motion:no-reverse:sm_rev" "motion-trap:no-vanish:st_gap,st_cont" "motion-trap:no-reverse:st_rev" "launch:early-launch:rl_order"; do
    scene=${pair%%:*}; rest=${pair#*:}; variant=${rest%%:*}; flips=${rest#*:}
    p_c=0; p_n=0
    seed=$LO
    while [ "$seed" -le "$HI" ]; do
        A=/tmp/meta_base; B=/tmp/meta_var
        rm -rf "$A" "$B"
        "$REPO/scenegen" "$scene" "$A" --seed "$seed" >/dev/null 2>&1
        "$REPO/scenegen" "$scene" "$B" --seed "$seed" --variant "$variant" >/dev/null 2>&1
        "$PY" "$HERE/track_probe.py" "$A" >/dev/null 2>&1
        "$PY" "$HERE/track_probe.py" "$B" >/dev/null 2>&1
        r=$("$PY" - "$A" "$B" "$flips" <<'PYEOF'
import json, sys
A, B, flips = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
def load(d):
    probes = {json.loads(l)["id"]: json.loads(l) for l in open(f"{d}/probes.jsonl") if l.strip()}
    answers = {json.loads(l)["id"]: json.loads(l)["answer"] for l in open(f"{d}/answers.jsonl") if l.strip()}
    return probes, answers
def nb(s): s=str(s).strip().lower(); return "yes" if s in ("yes","true","1") else ("no" if s in ("no","false","0") else s)
pa, aa = load(A); pb, ab = load(B)
n=c=0; fails=[]
for pid in flips:
    n += 1
    ga, gb = pa[pid]["gold"], pb[pid]["gold"]
    if nb(ga) == nb(gb):
        fails.append(f"{pid}:golds-did-not-flip({ga}/{gb})"); continue
    ok_a = nb(aa.get(pid,"")) == nb(ga)
    ok_b = nb(ab.get(pid,"")) == nb(gb)
    if ok_a and ok_b: c += 1
    else: fails.append(f"{pid}:base={aa.get(pid,'')!r}(gold {ga}) var={ab.get(pid,'')!r}(gold {gb})")
print(f"{c} {n} " + ";".join(fails))
PYEOF
)
        c=$(echo "$r" | cut -d' ' -f1); n=$(echo "$r" | cut -d' ' -f2); f=$(echo "$r" | cut -d' ' -f3-)
        total=$((total+n)); credited=$((credited+c)); p_c=$((p_c+c)); p_n=$((p_n+n))
        [ "$c" != "$n" ] && echo "MISS $scene/$variant seed=$seed: $f"
        seed=$((seed+1))
    done
    echo "$scene/$variant: $p_c/$p_n"
done
# ---- audio pairs (fixed scenes, one run each — no seed sweep) ---------------------------------
for pair in "transient-in-noise:no-transient:atn_count=0,atn_cluster=0" \
            "tone-alarm:no-tone:ata_count=0" \
            "av-sync:no-transient:avs_impact=no,avs_count=0"; do
    scene=${pair%%:*}; rest=${pair#*:}; variant=${rest%%:*}; flips=${rest#*:}
    A=/tmp/meta_au_base; B=/tmp/meta_au_var
    rm -rf "$A" "$B"; mkdir -p "$A" "$B"
    "$REPO/audiogen" "$scene" "$A/scene.wav" >/dev/null
    "$REPO/audiogen" "$scene" "$B/scene.wav" --variant "$variant" >/dev/null
    cp "$HERE/scenarios/$scene/probes.jsonl" "$A/"
    cp "$HERE/scenarios/$scene/probes.jsonl" "$B/"
    "$PY" "$HERE/audio_probe.py" "$A" >/dev/null 2>&1
    "$PY" "$HERE/audio_probe.py" "$B" >/dev/null 2>&1
    r=$("$PY" - "$A" "$B" "$flips" <<'PYEOF'
import json, sys
A, B, spec = sys.argv[1], sys.argv[2], sys.argv[3]
def load(d):
    probes = {json.loads(l)["id"]: json.loads(l) for l in open(f"{d}/probes.jsonl") if l.strip()}
    answers = {json.loads(l)["id"]: json.loads(l)["answer"] for l in open(f"{d}/answers.jsonl") if l.strip()}
    return probes, answers
def nb(s): s=str(s).strip().lower(); return "yes" if s in ("yes","true","1") else ("no" if s in ("no","false","0") else s)
import re
def num(s): m=re.findall(r"-?\d+",str(s)); return m[0] if m else str(s).strip()
pa, aa = load(A); pb, ab = load(B)
n=c=0; fails=[]
for item in spec.split(","):
    pid, gv = item.split("=")
    n += 1
    ga = pa[pid]["gold"]; m = pa[pid]["match"]
    cmp = (lambda x,y: nb(x)==nb(y)) if m=="boolean" else (lambda x,y: num(x)==num(y))
    ok_a = cmp(aa.get(pid,""), ga)
    ok_b = cmp(ab.get(pid,""), gv)
    if ok_a and ok_b: c += 1
    else: fails.append(f"{pid}:base={aa.get(pid,'')!r}(gold {ga}) var={ab.get(pid,'')!r}(gold {gv})")
print(f"{c} {n} " + ";".join(fails))
PYEOF
)
    c=$(echo "$r" | cut -d' ' -f1); n=$(echo "$r" | cut -d' ' -f2); f=$(echo "$r" | cut -d' ' -f3-)
    total=$((total+n)); credited=$((credited+c))
    [ "$c" != "$n" ] && echo "MISS $scene/$variant: $f"
    echo "$scene/$variant: $c/$n"
done

echo
echo "metamorphic_sensitivity: $credited/$total"
pct=$((credited * 100 / total))
if [ "$pct" -lt 95 ]; then
    echo "meta_test: FAIL — sensitivity ${pct}% below the 95% bar" >&2
    exit 1
fi
echo "meta_test: PASS (${pct}%)"
