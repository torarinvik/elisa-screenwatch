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
        rest = re.sub(r"\[batch[^\]]*\]", "", rest)      # drop evidence pointer
        rest = re.sub(r"^[—\-]\s*", "", rest)            # v2 "— " lead
        rest = re.sub(r"^\[[^\]]*\]\s*", "", rest)       # v3 "[oN] " actor tag
        events.append((t, rest.strip()))
    return events

# ---- event matching (log <-> truth) ------------------------------------------------------------

def _tokens(s):
    return set(re.findall(r"[a-z0-9]+", _norm(s)))

def _sim(a, b):
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    j = len(ta & tb) / len(ta | tb)
    r = difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()
    return max(j, r)

def match_events(log_events, truth_events, window_ms, sim_th):
    """Greedy best-match each log event to a truth event within a time window. Returns
    (pairs, unmatched_log): pairs = list of (log_idx, truth_idx)."""
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
    return pairs, unmatched

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
    for p in probes:
        pid = p["id"]
        ans = answers.get(pid, "")
        ok = match(p["gold"], ans, p.get("match", "exact"))
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
        detail.append({"id": pid, "kind": p.get("kind"), "ok": ok,
                       "asserted": asserted, "answer": ans, "gold": p["gold"]})

    # log-derived event order + event confabulation
    log_events = parse_log_events(os.path.join(run_dir, "log.md"))
    pairs, unmatched_log = match_events(log_events, truth_events, window_ms, sim_th)
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
        "reconstruction": recon,
        "tokens": rs.get("tokens", -1),
        "latency_ms": rs.get("latency_ms", -1),
        "counts": {"probes": n_ask, "correct": n_correct, "retain_probes": n_retain_ask,
                   "assertions": assertions, "confabulations": confab,
                   "log_events": len(log_events), "matched_events": len(pairs),
                   "truth_events": len(truth_events)},
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
        f"  reconstruction        {pct(m['reconstruction'])}   (arch_tool verify)",
        f"  tokens / latency      {m['tokens']} tok / {m['latency_ms']} ms",
        "─────────────────────────────────────────────",
    ]
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

    print(fmt(m))
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
