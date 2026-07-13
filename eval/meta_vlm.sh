#!/bin/sh
# meta_vlm.sh — V1.9 acceptance: the metamorphic-pair battery (eval/meta_test.sh) with the QWEN VLM
# as the answerer instead of the symbolic tracker. Same law: a flip probe is credited only when the
# VLM answers it correctly on BOTH sides of the pair (base and variant). An identical answer to both
# sides reveals a prior and scores 0 even if one side happened to be right. Where meta_test proves the
# pairs are answerable (the tracker passes 100% by construction), THIS run measures how far the VLM's
# priors leak — the batteries' real target.
#
# Cost control (the VLM reloads the model per probe, ~13s each):
#   - each fixture's probes.jsonl is FILTERED to only the pair's flip probe(s) before inference;
#   - paraphrase index is rotated by seed (V1.7 q_alt rotation) at no extra model-load cost.
#
#   eval/meta_vlm.sh [seed_lo] [seed_hi] [frames]      (defaults 0 2 8 — a bounded acceptance run)
#
# RESERVED SEEDS: >= 1000 are the held-out final-scoring pool; this runner refuses them.
set -e
LO=${1:-0}
HI=${2:-2}
FRAMES=${3:-8}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
PY="$REPO/.venv-vlm/bin/python"; [ -x "$PY" ] || PY="${SCREENVLM_PYTHON:-python3}"

if [ "$HI" -ge 1000 ]; then
    echo "meta_vlm: seeds >= 1000 are RESERVED for final scoring; refusing" >&2
    exit 3
fi

total=0; credited=0
for pair in "motion:no-reverse:sm_rev" "motion-trap:no-vanish:st_gap,st_cont" "motion-trap:no-reverse:st_rev" "launch:early-launch:rl_order"; do
    scene=${pair%%:*}; rest=${pair#*:}; variant=${rest%%:*}; flips=${rest#*:}
    p_c=0; p_n=0
    seed=$LO
    while [ "$seed" -le "$HI" ]; do
        A=/tmp/mv_base; B=/tmp/mv_var
        rm -rf "$A" "$B"
        "$REPO/scenegen" "$scene" "$A" --seed "$seed" >/dev/null 2>&1
        "$REPO/scenegen" "$scene" "$B" --seed "$seed" --variant "$variant" >/dev/null 2>&1
        # keep only the flip probes in each fixture (bounds VLM cost to 1-2 inferences/fixture)
        for d in "$A" "$B"; do
            "$PY" - "$d" "$flips" <<'PYF'
import json, sys
d, flips = sys.argv[1], set(sys.argv[2].split(","))
keep = [l for l in open(f"{d}/probes.jsonl") if l.strip() and json.loads(l)["id"] in flips]
open(f"{d}/probes.jsonl", "w").writelines(keep)
PYF
        done
        "$PY" "$HERE/vlm_probe.py" "$A" --frames "$FRAMES" --paraphrase "$seed" >/dev/null 2>&1
        "$PY" "$HERE/vlm_probe.py" "$B" --frames "$FRAMES" --paraphrase "$seed" >/dev/null 2>&1
        r=$("$PY" - "$A" "$B" "$flips" <<'PYEOF'
import json, sys, re
A, B, flips = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
def load(d):
    probes = {json.loads(l)["id"]: json.loads(l) for l in open(f"{d}/probes.jsonl") if l.strip()}
    answers = {json.loads(l)["id"]: json.loads(l)["answer"] for l in open(f"{d}/answers.jsonl") if l.strip()}
    return probes, answers
def nb(s):
    s = str(s).strip().lower()
    # first yes/no token wins ("No." -> no, "yes, it does" -> yes)
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
        [ "$c" != "$n" ] && echo "MISS $scene/$variant seed=$seed (paraphrase $seed): $f"
        seed=$((seed+1))
    done
    echo "$scene/$variant: $p_c/$p_n"
done

echo
echo "vlm_metamorphic_sensitivity: $credited/$total"
pct=0; [ "$total" -gt 0 ] && pct=$((credited * 100 / total))
echo "meta_vlm: measured ${pct}% (this is a MEASUREMENT of VLM prior-leak, not a pass/fail bar)"
