#!/bin/sh
# meta_ladder.sh — V1.10: the metamorphic-pair flip battery (as in meta_vlm.sh) swept across
# REPRESENTATION RUNGS. V1.9 measured the raster violin at 0/15 and proved (32f control) the failure
# is the vision encoder, not frame count. This asks the complementary question: if we spend the same
# context budget on MANY frames at LOW detail-per-frame — the scene as a TEXT bounding-box log the
# LLM reads through its language pathway (screenvlm_text) — does the violin earn any temporal
# authority? The boxes come from an INDEPENDENT per-frame extractor (no tracker), so a correct answer
# is genuine reasoning over evidence, not a paraphrase of viola.
#
# Same pair-credit law as V1.9: a flip probe scores only when answered correctly on BOTH sides. Each
# rung is "repr:frames" (table:8, table:24, svg:12). R0/R1 (raster 8f/32f) already measured at 0/15
# in V1.9 and are cited, not re-run.
#
#   eval/meta_ladder.sh [seed_lo] [seed_hi] "rung rung ..."     (default 0 2 "table:8 table:24 svg:12")
#
# RESERVED SEEDS: >= 1000 are held out; this runner refuses them.
set -e
LO=${1:-0}
HI=${2:-2}
RUNGS=${3:-"table:8 table:24 svg:12"}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
PY="$REPO/.venv-vlm/bin/python"; [ -x "$PY" ] || PY="${SCREENVLM_PYTHON:-python3}"
SVLM="$REPO/screenvlm_text"

if [ "$HI" -ge 1000 ]; then
    echo "meta_ladder: seeds >= 1000 are RESERVED for final scoring; refusing" >&2
    exit 3
fi

for rung in $RUNGS; do
    REPR=${rung%%:*}; FRAMES=${rung#*:}
    export LADDER_REPR="$REPR"
    echo "================ rung $rung (repr=$REPR frames=$FRAMES) ================"
    total=0; credited=0
    for pair in "motion:no-reverse:sm_rev" "motion-trap:no-vanish:st_gap,st_cont" "motion-trap:no-reverse:st_rev" "launch:early-launch:rl_order"; do
        scene=${pair%%:*}; rest=${pair#*:}; variant=${rest%%:*}; flips=${rest#*:}
        p_c=0; p_n=0
        seed=$LO
        while [ "$seed" -le "$HI" ]; do
            A=/tmp/ml_base; B=/tmp/ml_var
            rm -rf "$A" "$B"
            "$REPO/scenegen" "$scene" "$A" --seed "$seed" >/dev/null 2>&1
            "$REPO/scenegen" "$scene" "$B" --seed "$seed" --variant "$variant" >/dev/null 2>&1
            for d in "$A" "$B"; do
                "$PY" - "$d" "$flips" <<'PYF'
import json, sys
d, flips = sys.argv[1], set(sys.argv[2].split(","))
keep = [l for l in open(f"{d}/probes.jsonl") if l.strip() and json.loads(l)["id"] in flips]
open(f"{d}/probes.jsonl", "w").writelines(keep)
PYF
            done
            "$PY" "$HERE/vlm_probe.py" "$A" --frames "$FRAMES" --paraphrase "$seed" --screenvlm "$SVLM" >/dev/null 2>&1
            "$PY" "$HERE/vlm_probe.py" "$B" --frames "$FRAMES" --paraphrase "$seed" --screenvlm "$SVLM" >/dev/null 2>&1
            r=$("$PY" - "$A" "$B" "$flips" <<'PYEOF'
import json, sys, re
A, B, flips = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
def load(d):
    probes = {json.loads(l)["id"]: json.loads(l) for l in open(f"{d}/probes.jsonl") if l.strip()}
    answers = {json.loads(l)["id"]: json.loads(l)["answer"] for l in open(f"{d}/answers.jsonl") if l.strip()}
    return probes, answers
def nb(s):
    s = str(s).strip().lower()
    for tok, val in (("yes","yes"),("no","no"),("true","yes"),("false","no")):
        if re.search(r"\b"+tok+r"\b", s): return val
    return s
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
    else: fails.append(f"{pid}:base={aa.get(pid,'')[:24]!r}(gold {ga}) var={ab.get(pid,'')[:24]!r}(gold {gb})")
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
    pct=0; [ "$total" -gt 0 ] && pct=$((credited * 100 / total))
    echo "--> rung $rung  ladder_sensitivity: $credited/$total (${pct}%)"
    echo
done
echo "meta_ladder: MEASUREMENT of representation-rung sensitivity, not a pass/fail bar"
