#!/usr/bin/env python3
"""score_memory.py — grade a watcher's structured memory against a scripted ground truth.

Where score.py grades the symbolic ACTIVITY triage, this grades the NEURAL member: did the
watcher's 3-tier memory (state.md/log.md/story.md) + its probe answers actually capture what
happened? It computes the step-5 metric battery so the research thesis ("compact, evolving,
FAITHFUL understanding of a visual stream") is measured, not asserted.

Inputs (a scenario run directory):
  truth.jsonl     ground-truth timeline   (authored with the scenario; see eval/scenarios.md)
                  {"type":"event","t":ms,"id":"e1","desc":"...","object":"o?"}
                  {"type":"fact","t0":ms,"t1":ms,"key":"...","value":"..."}
                  {"type":"phase","t0":ms,"t1":ms,"label":"...","activity":"typing"}
  probes.jsonl    probe questions with gold answers
                  {"id":"p1","ask_t":ms,"kind":"perception|retention|occlusion|event",
                   "q":"...","gold":"7","match":"numeric|substring|boolean|exact","fact_t":ms}
  answers.jsonl   the watcher's probe answers (from memory only)
                  {"id":"p1","answer":"7"}          ("unknown"/"" = an honest miss, NOT a lie)
  log.md          the watcher's episodic trace (optional; enables event-order + event confab)
  runstats.json   {"tokens":N,"latency_ms":N,"batches":N}  (optional; from the run harness)

Metrics (all in [0,1] unless noted):
  perception_accuracy   correct answers / probes asked            (unknown counts as a miss)
  memory_retention      accuracy on probes whose fact aged > --retain-age ms before being asked
  event_order           concordant ordered pairs among matched log<->truth events (tau-like)
  confabulation_rate    fabrications / assertions  (LOWER is better; unknown is never a lie)
  reconstruction        1.0 if `arch_tool verify <dir>` passes, else 0.0  (symbolic; -1 = skipped)
  tokens, latency_ms    cost, from runstats.json                  (raw, not normalized)

V1 protocol extensions (orchestra_v3_plan.md — all additive; -1 = not applicable):
  twin_consistency      probes may carry "twin_of": "<sibling_id>" (+ optional "polarity").
                        A pair is consistent only if BOTH twins match their own golds — an
                        affirmation-biased answerer scores 0 here where perception gave it 50%.
  omission_rate         truth events with NO matching log event / truth events (needs log.md).
                        The dual of confabulation: suppression of real events (NOAH duality).
  omission_recall       probes with "kind":"omission" ask open recall ("list all X"); their gold
                        is item1;item2;...  — recall = recalled items / items, across all such
                        probes. Omission probes are excluded from perception_accuracy.
  by_claim_class        probes may carry "claim_class" (presence|count|position|direction|
                        timing|identity|text|audio); per-class asked/correct/asserted/confab,
                        because "75% overall" hides "100% presence, 0% direction".

Usage:
  score_memory.py <run_dir> [--retain-age 20000] [--arch-tool ./arch_tool] [--json]
  score_memory.py --selftest
"""
import sys, os, re, json, difflib, subprocess, tempfile

# ---- matchers ----------------------------------------------------------------------------------

def _num(s):
    m = re.search(r"-?\d+(?:\.\d+)?", str(s))
    return m.group(0) if m else None

def _norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())

_BOOL_YES = {"yes", "true", "present", "shown", "visible", "1"}
_BOOL_NO = {"no", "false", "absent", "hidden", "gone", "0"}

def _bool(s):
    t = _norm(s)
    for w in _BOOL_YES:
        if w in t:
            return True
    for w in _BOOL_NO:
        if w in t:
            return False
    return None

def is_unknown(ans):
    return _norm(ans) in ("", "unknown", "n/a", "not sure", "cannot tell", "can't tell", "?")

def match(gold, ans, kind):
    """True if the answer matches gold under the given matcher."""
    if is_unknown(ans):
        return False
    if kind == "numeric":
        g, a = _num(gold), _num(ans)
        return g is not None and a is not None and float(g) == float(a)
    if kind == "boolean":
        g, a = _bool(gold), _bool(ans)
        return g is not None and a is not None and g == a
    if kind == "substring":
        return _norm(gold) in _norm(ans)
    return _norm(gold) == _norm(ans)   # exact

# ---- IO ----------------------------------------------------------------------------------------

def load_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path):
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out

def parse_log_events(path):
    """Pull (t_ms, description) from a v2/v3 log.md. Tolerant of both line shapes."""
    if not os.path.exists(path):
        return []
    events = []
    for line in open(path):
        m = re.match(r"\s*t=(\d+)\s*(.*)", line)
        if not m:
            continue
        t = int(m.group(1))
        rest = m.group(2)
        rest = re.sub(r"\[(?:batch|arch)\b[^\]]*\]", "", rest)   # drop evidence pointer (batch or arch seq)
        rest = re.sub(r"^[—\-]\s*", "", rest)            # v2 "— " lead
        rest = re.sub(r"^\[[^\]]*\]\s*", "", rest)       # v3 "[oN] " actor tag
        events.append((t, rest.strip()))
    return events

# ---- event matching (log <-> truth) ------------------------------------------------------------

def _tokens(s):
    return set(re.findall(r"[a-z0-9]+", _norm(s)))

def _nums(s):
    return set(re.findall(r"\d+", str(s)))

def _sim(a, b):
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    j = len(ta & tb) / len(ta | tb)
    r = difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()
    s = max(j, r)
    # events carry salient values (a digit, a count). A shared number is a strong identity signal
    # that terse-vs-verbose phrasing hides from pure text similarity — floor the score when present.
    if _nums(a) & _nums(b):
        s = max(s, 0.6)
    return s

def match_events(log_events, truth_events, window_ms, sim_th):
    """Greedy best-match each log event to a truth event within a time window. Returns
    (pairs, unmatched_log, unmatched_truth): pairs = list of (log_idx, truth_idx).
    unmatched_truth (real events the log never mentioned) feeds omission_rate — the data was
    always computed here and previously discarded."""
    used = set()
    pairs = []
    unmatched = []
    for li, (lt, ld) in enumerate(log_events):
        best, bi = 0.0, -1
        for ti, te in enumerate(truth_events):
            if ti in used or abs(te["t"] - lt) > window_ms:
                continue
            s = _sim(ld, te["desc"])
            if s > best:
                best, bi = s, ti
        if bi >= 0 and best >= sim_th:
            used.add(bi)
            pairs.append((li, bi))
        else:
            unmatched.append(li)
    unmatched_truth = [ti for ti in range(len(truth_events)) if ti not in used]
    return pairs, unmatched, unmatched_truth

def order_score(pairs, log_events):
    """Tau-like: fraction of concordant pairs when log events are ordered by their own time."""
    seq = sorted(pairs, key=lambda p: log_events[p[0]][0])   # by log time
    ti = [p[1] for p in seq]                                 # truth indices in that order
    n = len(ti)
    if n < 2:
        return 1.0 if n == 1 else -1.0                      # -1 = not applicable
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            if ti[i] < ti[j]:
                conc += 1
            elif ti[i] > ti[j]:
                disc += 1
    tot = conc + disc
    return conc / tot if tot else 1.0

# ---- scoring -----------------------------------------------------------------------------------

def score(run_dir, retain_age=20000, arch_tool="./arch_tool",
          window_ms=6000, sim_th=0.30):
    truth = load_jsonl(os.path.join(run_dir, "truth.jsonl"))
    probes = load_jsonl(os.path.join(run_dir, "probes.jsonl"))
    answers = {a["id"]: a.get("answer", "") for a in load_jsonl(os.path.join(run_dir, "answers.jsonl"))}
    truth_events = [t for t in truth if t.get("type") == "event"]
    truth_events.sort(key=lambda e: e["t"])

    # per-probe outcomes
    n_ask = 0
    n_correct = 0
    n_retain_ask = 0
    n_retain_correct = 0
    confab = 0            # fabrications
    assertions = 0        # non-unknown probe answers + log events
    detail = []
    outcome = {}          # pid -> matched-own-gold (for twin pairing)
    by_class = {}         # claim_class -> {asked, correct, asserted, confab}
    om_items = 0          # omission probes: gold items total / recalled
    om_recalled = 0
    om_probes = 0
    for p in probes:
        pid = p["id"]
        ans = answers.get(pid, "")
        if p.get("kind") == "omission":
            # open recall ("list all X"); gold = item1;item2;... — scored per item, excluded
            # from perception (it grades a different failure surface: suppression, not error)
            om_probes += 1
            items = [g for g in str(p["gold"]).split(";") if g.strip()]
            om_items += len(items)
            got = sum(1 for it in items if match(it, ans, p.get("match", "substring")))
            om_recalled += got
            detail.append({"id": pid, "kind": "omission", "ok": got == len(items),
                           "asserted": not is_unknown(ans), "answer": ans, "gold": p["gold"],
                           "recalled": got, "items": len(items)})
            continue
        ok = match(p["gold"], ans, p.get("match", "exact"))
        outcome[pid] = ok
        n_ask += 1
        n_correct += 1 if ok else 0
        asserted = not is_unknown(ans)
        if asserted:
            assertions += 1
            if not ok:
                confab += 1          # stated a specific wrong answer = fabrication
        age = p.get("ask_t", 0) - p.get("fact_t", p.get("ask_t", 0))
        is_retain = p.get("kind") == "retention" or age >= retain_age
        if is_retain:
            n_retain_ask += 1
            n_retain_correct += 1 if ok else 0
        cls = p.get("claim_class", "unclassified")
        b = by_class.setdefault(cls, {"asked": 0, "correct": 0, "asserted": 0, "confab": 0})
        b["asked"] += 1
        b["correct"] += 1 if ok else 0
        b["asserted"] += 1 if asserted else 0
        b["confab"] += 1 if (asserted and not ok) else 0
        detail.append({"id": pid, "kind": p.get("kind"), "ok": ok,
                       "asserted": asserted, "answer": ans, "gold": p["gold"]})

    # twin pairing (V1.1): a pair is consistent only if BOTH twins matched their own golds.
    # Canonicalized by sorted id so a pair declared from either side counts once.
    twin_pairs = set()
    for p in probes:
        sib = p.get("twin_of")
        if sib and sib in outcome and p["id"] in outcome:
            twin_pairs.add(tuple(sorted((p["id"], sib))))
    twin_ok = sum(1 for a, b in twin_pairs if outcome[a] and outcome[b])

    # log-derived event order + event confabulation + omission (the confab dual)
    log_events = parse_log_events(os.path.join(run_dir, "log.md"))
    pairs, unmatched_log, unmatched_truth = match_events(log_events, truth_events, window_ms, sim_th)
    assertions += len(log_events)
    confab += len(unmatched_log)      # a logged event with no truth match = fabricated event
    ordsc = order_score(pairs, log_events)

    # reconstruction (symbolic): arch_tool verify over the run dir, if a ring is present
    recon = -1.0
    if os.path.exists(arch_tool) and any(f.startswith("arch_") and f.endswith(".idx")
                                         for f in os.listdir(run_dir)):
        try:
            r = subprocess.run([arch_tool, "verify", run_dir], capture_output=True, timeout=120)
            recon = 1.0 if r.returncode == 0 else 0.0
        except Exception:
            recon = 0.0

    rs = {}
    rsp = os.path.join(run_dir, "runstats.json")
    if os.path.exists(rsp):
        rs = json.load(open(rsp))

    return {
        "perception_accuracy": (n_correct / n_ask) if n_ask else -1.0,
        "memory_retention": (n_retain_correct / n_retain_ask) if n_retain_ask else -1.0,
        "event_order": ordsc,
        "confabulation_rate": (confab / assertions) if assertions else 0.0,
        "twin_consistency": (twin_ok / len(twin_pairs)) if twin_pairs else -1.0,
        "omission_rate": (len(unmatched_truth) / len(truth_events))
                         if (truth_events and log_events) else -1.0,
        "omission_recall": (om_recalled / om_items) if om_items else -1.0,
        "reconstruction": recon,
        "tokens": rs.get("tokens", -1),
        "latency_ms": rs.get("latency_ms", -1),
        "by_claim_class": by_class,
        "counts": {"probes": n_ask, "correct": n_correct, "retain_probes": n_retain_ask,
                   "assertions": assertions, "confabulations": confab,
                   "log_events": len(log_events), "matched_events": len(pairs),
                   "truth_events": len(truth_events),
                   "twin_pairs": len(twin_pairs), "twin_consistent": twin_ok,
                   "unmatched_truth": len(unmatched_truth),
                   "omission_probes": om_probes, "omission_items": om_items,
                   "omission_recalled": om_recalled},
        "detail": detail,
    }

def fmt(m):
    def pct(x):
        return "  n/a" if x is None or x < 0 else f"{100*x:5.1f}%"
    c = m["counts"]
    lines = [
        "── memory score ─────────────────────────────",
        f"  perception accuracy   {pct(m['perception_accuracy'])}   ({c['correct']}/{c['probes']} probes)",
        f"  memory retention      {pct(m['memory_retention'])}   ({c['retain_probes']} aged probes)",
        f"  event order           {pct(m['event_order'])}   ({c['matched_events']}/{c['truth_events']} truth events matched)",
        f"  confabulation rate    {pct(m['confabulation_rate'])}   ({c['confabulations']}/{c['assertions']} assertions)  ↓ lower is better",
    ]
    if c.get("twin_pairs"):
        lines.append(f"  twin consistency      {pct(m['twin_consistency'])}   ({c['twin_consistent']}/{c['twin_pairs']} pairs both-correct)")
    if m.get("omission_rate", -1) >= 0:
        lines.append(f"  omission rate         {pct(m['omission_rate'])}   ({c['unmatched_truth']}/{c['truth_events']} real events unmentioned)  ↓ lower is better")
    if m.get("omission_recall", -1) >= 0:
        lines.append(f"  omission recall       {pct(m['omission_recall'])}   ({c['omission_recalled']}/{c['omission_items']} gold items recalled)")
    lines += [
        f"  reconstruction        {pct(m['reconstruction'])}   (arch_tool verify)",
        f"  tokens / latency      {m['tokens']} tok / {m['latency_ms']} ms",
    ]
    bc = {k: v for k, v in m.get("by_claim_class", {}).items() if k != "unclassified"}
    if bc:
        lines.append("  by claim class:")
        for cls in sorted(bc):
            b = bc[cls]
            lines.append(f"    {cls:12} {pct(b['correct']/b['asked'] if b['asked'] else -1)}"
                         f"   ({b['correct']}/{b['asked']}, confab {b['confab']})")
    lines.append("─────────────────────────────────────────────")
    return "\n".join(lines)

# ---- self-test ---------------------------------------------------------------------------------

def selftest():
    """Build a fixture with KNOWN metrics and assert the scorer reproduces them."""
    d = tempfile.mkdtemp(prefix="scoreselftest_")
    truth = [
        {"type": "event", "t": 1000, "id": "e1", "desc": "counter reached 3"},
        {"type": "event", "t": 3000, "id": "e2", "desc": "red dialog appeared over editor"},
        {"type": "event", "t": 5000, "id": "e3", "desc": "build failed with one error"},
        {"type": "fact", "t0": 1000, "t1": 9000, "key": "counter", "value": "7"},
    ]
    probes = [
        # perception: 2 asked, 1 right (p1), 1 wrong-specific = confab (p2)
        {"id": "p1", "ask_t": 2000, "kind": "perception", "q": "counter?", "gold": "7", "match": "numeric", "fact_t": 1500},
        {"id": "p2", "ask_t": 2200, "kind": "perception", "q": "dialog color?", "gold": "red", "match": "substring", "fact_t": 2000},
        # perception: honest unknown = miss for accuracy, NOT a confab (p3)
        {"id": "p3", "ask_t": 2400, "kind": "occlusion", "q": "behind dialog?", "gold": "editor", "match": "substring", "fact_t": 2000},
        # retention: fact aged 21s > 20s, answered right (p4)
        {"id": "p4", "ask_t": 24000, "kind": "retention", "q": "counter earlier?", "gold": "7", "match": "numeric", "fact_t": 1500},
    ]
    answers = [
        {"id": "p1", "answer": "the counter shows 7"},   # correct
        {"id": "p2", "answer": "it was blue"},           # wrong + specific -> confab
        {"id": "p3", "answer": "unknown"},               # honest miss
        {"id": "p4", "answer": "7"},                     # correct, aged
    ]
    # log: 3 events; 2 match truth in-order (e1 then e3), 1 fabricated -> confab; order concordant
    log = ("t=1100 [o1] counter reached 3   [batch 1 f0]\n"
           "t=5200 [-] build failed with one error   [batch 5 f2]\n"
           "t=6000 [o9] a purple unicorn logged in   [batch 6 f0]\n")
    for name, rows in [("truth.jsonl", truth), ("probes.jsonl", probes), ("answers.jsonl", answers)]:
        with open(os.path.join(d, name), "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    with open(os.path.join(d, "log.md"), "w") as f:
        f.write(log)
    with open(os.path.join(d, "runstats.json"), "w") as f:
        json.dump({"tokens": 12345, "latency_ms": 6789, "batches": 6}, f)

    m = score(d, retain_age=20000, arch_tool="/nonexistent")
    c = m["counts"]
    checks = []
    def chk(name, got, want):
        ok = abs(got - want) < 1e-6
        checks.append((name, got, want, ok))
    # perception: 2/4 probes correct (p1,p4)  -> 0.5
    chk("perception_accuracy", m["perception_accuracy"], 2/4)
    # retention: 1/1 aged probe correct       -> 1.0
    chk("memory_retention", m["memory_retention"], 1.0)
    # assertions: p1,p2,p4 asserted (3) + 3 log events = 6 ; confab: p2 (1) + 1 fabricated log = 2
    chk("confabulation_rate", m["confabulation_rate"], 2/6)
    chk("assertions", c["assertions"], 6)
    chk("confabulations", c["confabulations"], 2)
    # event order: 2 matched (e1,e3) in correct order -> 1.0
    chk("event_order", m["event_order"], 1.0)
    chk("matched_events", c["matched_events"], 2)
    chk("reconstruction_skipped", m["reconstruction"], -1.0)

    # V1 back-compat pins on the ORIGINAL fixture: no twins/omission probes -> n/a sentinels,
    # and the log misses e2 -> omission_rate 1/3. Existing metric math above is untouched.
    chk("twin_na", m["twin_consistency"], -1.0)
    chk("omission_recall_na", m["omission_recall"], -1.0)
    chk("omission_rate", m["omission_rate"], 1/3)

    # ---- fixture 2 (V1 protocol): twins, omission probes, claim classes ----
    d2 = tempfile.mkdtemp(prefix="scoreselftest2_")
    truth2 = [
        {"type": "event", "t": 1000, "id": "e1", "desc": "alarm tone sounded"},
        {"type": "event", "t": 4000, "id": "e2", "desc": "square vanished"},
    ]
    probes2 = [
        # twin pair 1: both answered correctly -> consistent
        {"id": "q1", "ask_t": 5000, "kind": "perception", "q": "did it vanish?", "gold": "yes",
         "match": "boolean", "fact_t": 4000, "claim_class": "presence", "polarity": "pos"},
        {"id": "q1n", "ask_t": 5000, "kind": "perception", "q": "did it remain visible?", "gold": "no",
         "match": "boolean", "fact_t": 4000, "claim_class": "presence",
         "twin_of": "q1", "polarity": "neg"},
        # twin pair 2: affirmation bias — "yes" to both; pos half right, pair INCONSISTENT
        {"id": "q2", "ask_t": 6000, "kind": "perception", "q": "was there a tone?", "gold": "yes",
         "match": "boolean", "fact_t": 1000, "claim_class": "audio", "polarity": "pos"},
        {"id": "q2n", "ask_t": 6000, "kind": "perception", "q": "was it silent throughout?", "gold": "no",
         "match": "boolean", "fact_t": 1000, "claim_class": "audio",
         "twin_of": "q2", "polarity": "neg"},
        # direction claim, wrong + specific -> per-class confab
        {"id": "q3", "ask_t": 7000, "kind": "perception", "q": "moving which way?", "gold": "left",
         "match": "substring", "fact_t": 6000, "claim_class": "direction"},
        # omission probe: 3 gold items, answer recalls 2 -> recall 2/3; excluded from perception
        {"id": "q4", "ask_t": 8000, "kind": "omission", "q": "list every event you saw",
         "gold": "alarm tone;square vanished;error dialog", "match": "substring", "fact_t": 0},
    ]
    answers2 = [
        {"id": "q1", "answer": "yes"},
        {"id": "q1n", "answer": "no"},
        {"id": "q2", "answer": "yes"},
        {"id": "q2n", "answer": "yes"},          # the bias the twin catches
        {"id": "q3", "answer": "right"},         # wrong + specific
        {"id": "q4", "answer": "I saw an alarm tone and then the square vanished"},
    ]
    for name, rows in [("truth.jsonl", truth2), ("probes.jsonl", probes2), ("answers.jsonl", answers2)]:
        with open(os.path.join(d2, name), "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    m2 = score(d2, retain_age=20000, arch_tool="/nonexistent")
    c2 = m2["counts"]
    # 5 graded probes (omission excluded): q1,q1n,q2,q3 right... q2n wrong, q3 wrong -> 3/5
    chk("v1_perception", m2["perception_accuracy"], 3/5)
    chk("v1_twin_consistency", m2["twin_consistency"], 1/2)
    chk("v1_twin_pairs", c2["twin_pairs"], 2)
    chk("v1_omission_recall", m2["omission_recall"], 2/3)
    # no log.md -> omission_rate n/a (never spuriously 100%)
    chk("v1_omission_rate_na", m2["omission_rate"], -1.0)
    chk("v1_class_presence", m2["by_claim_class"]["presence"]["correct"], 2)
    chk("v1_class_audio", m2["by_claim_class"]["audio"]["correct"], 1)
    chk("v1_class_dir_confab", m2["by_claim_class"]["direction"]["confab"], 1)

    print(fmt(m))
    print()
    print(fmt(m2))
    print("\nself-test:")
    ok_all = True
    for name, got, want, ok in checks:
        ok_all = ok_all and ok
        print(f"  {'ok ' if ok else 'BAD'} {name:24} got={got:.4f} want={want:.4f}")
    print("PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1

# ---- main --------------------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        raise SystemExit(selftest())
    if not args:
        raise SystemExit(__doc__)
    run_dir = args[0]
    retain_age = 20000
    arch_tool = "./arch_tool"
    as_json = "--json" in args
    if "--retain-age" in args:
        retain_age = int(args[args.index("--retain-age") + 1])
    if "--arch-tool" in args:
        arch_tool = args[args.index("--arch-tool") + 1]
    m = score(run_dir, retain_age=retain_age, arch_tool=arch_tool)
    print(json.dumps(m, indent=2) if as_json else fmt(m))

if __name__ == "__main__":
    main()
