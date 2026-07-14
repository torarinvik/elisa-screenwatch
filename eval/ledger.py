#!/usr/bin/env python3
"""ledger.py — the evidence ledger (orchestra_v2 plan M9, rung B of the representation ladder;
orchestra_v3_plan.md V2 adds minimal SUPERSESSION — rung B+).

The ladder asks: story.md alone (A) vs an append-only typed event ledger with story.md as a *projection*
of it (B) vs +track identities (C) vs a full temporal graph (D). This tool builds rung B and its
projection from the SYMBOLIC members' event streams — the viola (tracker) and the cymbal (audiotriage)
— so the factual ledger is the source of truth and the narrative is derived, never independently edited
(I7). Each record keeps provenance, family, OBSERVED-vs-INFERRED, confidence, and an evidence pin — the
anti-confabulation spine (I8/I9). The A↔D *comparative* scoring still needs live watcher runs; this is
the deterministic ledger foundation those runs build on.

V2 — minimal supersession (rung B+): interpretations become REVISABLE without rewriting evidence.
Each record gains `id`, `recorded_at` (bi-temporal minimum: valid time = t0/t1, transaction time =
recorded_at epoch), `license` (the RULE that admitted it), `status` (active|superseded|disputed), and
`supersedes` (id | null). THE ONE LAW, enforced at build/validate: **`supersedes` may only point at an
INFERRED record** — evidence (OBSERVED) is immutable; only interpretations retire. A conservative
reacquire detector turns each VANISH→(later)APPEAR pair into an INFERRED supersession carrying an
explicit candidate set {same-object(occlusion) → 1 distinct, new-object → 2 distinct}, so the count
question is answered by an honest split instead of a flat "2". This is the schema V3.2's tentative
reacquisition writes into; V2 lands it BEFORE the tracker produces revisable interpretations.

  ledger.py build    <fixture_dir> [--wav scene.wav] [--no-supersede]  # events -> ledger.jsonl (law-checked)
  ledger.py project  <fixture_dir> [--audit]                           # ledger.jsonl -> story.md
  ledger.py validate <fixture_dir|ledger.jsonl>                        # enforce the one law; exit!=0 on breach
  ledger.py revision <fixture_dir> <object>                            # the `revision` probe, answered from the ledger
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Reacquire detector (conservative): pair a VANISH with the first later APPEAR of a DIFFERENT object
# within this window. The candidate set preserves BOTH readings, so a loose pairing stays honest.
REACQUIRE_GAP_MS = 2000


def tracker_events(fixture):
    """viola INF events -> ledger records (family symbolic-tracker)."""
    tracker = os.path.join(REPO, "tracker")
    if not os.path.exists(os.path.join(fixture, "batch_0.txt")):
        return []
    r = subprocess.run([tracker, "run", fixture], capture_output=True, text=True)
    recs = []
    # V3.2: INF dispute lines mark a REACQUIRE whose component another live track also claimed (a merge).
    # Keyed by (id, t) so the matching REACQUIRE record becomes a DISPUTED candidate, not a silent steal.
    disputes = {}
    for ln in r.stdout.splitlines():
        p = ln.split()
        if len(p) >= 2 and p[0] == "INF" and p[1] == "dispute":
            kv = dict(tok.split("=", 1) for tok in p if "=" in tok)
            disputes[(kv["id"], int(kv["t"]))] = kv.get("contests", "0")
    KIND = {"APPEAR": "object appears", "VANISH": "object vanishes",
            "REVERSE": "object reverses direction", "REACQUIRE": "object reacquired",
            "OCCLUDED": "object occluded (passes behind another)"}
    for ln in r.stdout.splitlines():
        p = ln.split()
        if len(p) < 2 or not (p[0] == "INF" and p[1] == "event"):
            continue
        kv = {}
        for tok in p:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k] = v
        t = int(kv["t"])
        disp = disputes.get((kv["id"], t))
        rec = {
            "t0": t, "t1": t, "kind": kv["kind"],
            "summary": f"{KIND.get(kv['kind'], kv['kind'])} (track {kv['id']}) at cx={kv.get('cx','?')}",
            "member": "viola", "family": "symbolic-tracker",
            "obs_or_inf": "INF", "conf": int(kv.get("conf", 0)),
            "object": f"o{kv['id']}",
            "license": f"viola:{kv['kind']}",
            "evidence": f"[track id={kv['id']} t={t} cx={kv.get('cx','?')}]",
            "cx": int(kv["cx"]) if kv.get("cx", "?").lstrip("-").isdigit() else None,
        }
        if disp is not None and kv["kind"] == "REACQUIRE":
            # Merge-drag: the reacquired blob was ALSO claimed by track `disp`. Record the identity as
            # DISPUTED with an explicit candidate set instead of a confident (possibly stolen) identity.
            rec["status"] = "disputed"
            rec["summary"] = (f"track {kv['id']} reacquired a blob ALSO claimed by track {disp} "
                              f"at cx={kv.get('cx','?')} — identity DISPUTED (merge)")
            rec["license"] = "viola:reacquire-disputed"
            rec["candidates"] = [
                {"label": f"blob is track {kv['id']} (o{kv['id']})", "distinct_count": 2, "conf": 50},
                {"label": f"blob is track {disp} (o{disp}) — identity stolen by the merge",
                 "distinct_count": 2, "conf": 50}]
        recs.append(rec)
    return recs


def audio_events(fixture, wav):
    """cymbal AUDIO events -> ledger records (family symbolic-audio)."""
    at = os.path.join(REPO, "audiotriage")
    wpath = os.path.join(fixture, wav)
    if not os.path.exists(wpath):
        return []
    r = subprocess.run([at, wpath], capture_output=True, text=True)
    recs = []
    KIND = {"TRANSIENT": "an impact/transient sound", "SILENCE_START": "audio goes silent",
            "SILENCE_END": "audio resumes", "TONE": "a sustained tone", "LEVEL_SHIFT": "sound level shifts"}
    for ln in r.stdout.splitlines():
        p = ln.split()
        if len(p) < 2 or p[0] != "AUDIO":
            continue
        kv = {}
        for tok in p[2:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k] = v
        t = int(kv.get("t", 0))
        extra = f" ({kv['freq']} Hz)" if "freq" in kv else ""
        recs.append({
            "t0": t, "t1": t + int(kv.get("dur", 0)), "kind": p[1],
            "summary": f"{KIND.get(p[1], p[1])}{extra}",
            "member": "cymbal", "family": "symbolic-audio",
            "obs_or_inf": "OBS", "conf": int(kv.get("conf", 0)),
            "object": "audio",
            "license": f"cymbal:{p[1]}",
            "evidence": f"[aud {p[1]} t={t}{' dur='+kv['dur'] if 'dur' in kv else ''}]",
        })
    return recs


def _finalize(r, rid, recorded_at):
    """Stamp the V2 bi-temporal / supersession fields with sane defaults (non-destructive)."""
    r["id"] = rid
    r.setdefault("recorded_at", recorded_at)
    r.setdefault("status", "active")
    r.setdefault("supersedes", None)
    r.setdefault("license", f"{r.get('member','?')}:{r.get('kind','?')}")
    return r


def detect_reacquires(recs):
    """Conservative reacquire pass: for each viola VANISH, pair the first later APPEAR of a DIFFERENT
    object within REACQUIRE_GAP_MS. Emit an INFERRED supersession record carrying an explicit candidate
    set {same-object → 1 distinct, new-object → 2 distinct}; mark the VANISH superseded. The pairing may
    be loose because the candidate set asserts NEITHER reading — it preserves both and splits confidence
    on the measured gap + displacement. recorded_at = 1 (a later transaction epoch than the base build)."""
    new = []
    appears = [r for r in recs if r["member"] == "viola" and r["kind"] == "APPEAR"]
    claimed = set()
    for v in [r for r in recs if r["member"] == "viola" and r["kind"] == "VANISH"]:
        cand = None
        for a in sorted(appears, key=lambda r: r["t0"]):
            if a["object"] == v["object"] or a["id"] in claimed:
                continue
            gap = a["t0"] - v["t0"]
            if 0 < gap <= REACQUIRE_GAP_MS:
                cand = a
                break
        if cand is None:
            continue
        claimed.add(cand["id"])
        v["status"] = "superseded"
        gap = cand["t0"] - v["t0"]
        disp = abs((cand.get("cx") or 0) - (v.get("cx") or 0))
        same = max(10, min(85, 80 - gap // 40 - disp // 2))   # transparent: weaker as gap/disp grow
        new.append(_finalize({
            "t0": v["t0"], "t1": cand["t0"], "kind": "REACQUIRE_CANDIDATE",
            "summary": (f"{v['object']} may be occluded then reacquired as {cand['object']} "
                        f"(gap {gap}ms, moved {disp}px): 1 distinct object if same, 2 if new"),
            "member": "viola", "family": "symbolic-tracker", "obs_or_inf": "INF",
            "conf": same, "object": v["object"],
            "license": "viola:reacquire-candidate",
            "candidates": [
                {"label": f"same-object (occlusion): {v['object']}=={cand['object']}",
                 "distinct_count": 1, "conf": same},
                {"label": f"new-object: {cand['object']} is separate",
                 "distinct_count": 2, "conf": 100 - same}],
            "evidence": f"[supersede {v['evidence']} + {cand['evidence']} | no-component gap {gap}ms]",
        }, rid=-1, recorded_at=1))
        new[-1]["supersedes"] = v["id"]
    return new


def validate(recs):
    """THE ONE LAW: `supersedes` may only point at an INFERRED record. Returns a list of violations
    (empty == valid). Evidence (OBSERVED) is immutable; only interpretations retire."""
    by_id = {r.get("id"): r for r in recs if "id" in r}
    bad = []
    for r in recs:
        tgt = r.get("supersedes")
        if tgt is None:
            continue
        if tgt not in by_id:
            bad.append(f"record id={r.get('id')} supersedes missing id {tgt}")
        elif by_id[tgt]["obs_or_inf"] == "OBS":
            bad.append(f"record id={r.get('id')} supersedes OBSERVED id={tgt} "
                       f"({by_id[tgt].get('license','?')}) — evidence is immutable")
    return bad


def build(fixture, wav, supersede=True):
    recs = tracker_events(fixture) + audio_events(fixture, wav)
    recs.sort(key=lambda r: (r["t0"], r["member"]))
    for i, r in enumerate(recs):
        _finalize(r, rid=i, recorded_at=0)
    if supersede:
        extra = detect_reacquires(recs)
        base = len(recs)
        for j, r in enumerate(extra):
            r["id"] = base + j
        recs += extra
    violations = validate(recs)
    if violations:
        sys.exit("ledger: LAW VIOLATION (supersedes must target INFERRED):\n  " + "\n  ".join(violations))
    out = os.path.join(fixture, "ledger.jsonl")
    with open(out, "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    fams = {}
    for r in recs:
        fams[r["family"]] = fams.get(r["family"], 0) + 1
    nsup = sum(1 for r in recs if r["supersedes"] is not None)
    print(f"ledger: {len(recs)} records {fams} -> ledger.jsonl ({nsup} supersession(s))")


def load_ledger(fixture_or_file):
    path = fixture_or_file if fixture_or_file.endswith(".jsonl") else os.path.join(fixture_or_file, "ledger.jsonl")
    if not os.path.exists(path):
        sys.exit(f"ledger: no ledger.jsonl at {path} (run build first)")
    return [json.loads(l) for l in open(path) if l.strip()]


def project(fixture, audit=False):
    """Deterministic story.md projection: an EVENTS trace + DURABLE_OBJECTS, every line evidence-pinned.
    story.md is DERIVED from the ledger (I7): it never adds a claim the ledger does not carry.
    Plain projection renders only ACTIVE interpretations (superseded ones are hidden — the story stays
    clean); `--audit` appends a `revisions:` note so the retired claim + its supersession are auditable."""
    recs = load_ledger(fixture)
    active = [r for r in recs if r.get("status") != "superseded"]
    objs = {}
    for r in active:
        objs.setdefault(r["object"], []).append(r)
    lines = ["# story.md (projected from ledger.jsonl — I7: derived, not independently edited)", "",
             "## EVENTS"]
    for r in active:
        tag = "OBSERVED" if r["obs_or_inf"] == "OBS" else "INFERRED"
        extra = ""
        if r.get("candidates"):
            extra = " | candidates: " + "; ".join(
                f"{c['label']} (conf={c['conf']})" for c in r["candidates"])
        lines.append(f"t={r['t0']} [{r['object']}] {r['summary']} — "
                     f"{tag}({r['member']},conf={r['conf']},license={r['license']}) {r['evidence']}{extra}")
    lines += ["", "## DURABLE_OBJECTS"]
    for o, rs in sorted(objs.items()):
        kinds = ",".join(sorted({x["kind"] for x in rs}))
        lines.append(f"{o}: {len(rs)} events [{kinds}] family={rs[0]['family']}")
    if audit:
        superseded = [r for r in recs if r.get("status") == "superseded"]
        if superseded:
            lines += ["", "## revisions: (retired interpretations, preserved — evidence never rewritten)"]
            by_sup = {r["supersedes"]: r for r in recs if r.get("supersedes") is not None}
            for r in superseded:
                nxt = by_sup.get(r["id"])
                who = f" -> superseded by id={nxt['id']} ({nxt['summary']})" if nxt else ""
                lines.append(f"[RETIRED id={r['id']}] t={r['t0']} {r['summary']} "
                             f"(conf={r['conf']},license={r['license']}){who}")
    out = os.path.join(fixture, "story.md")
    open(out, "w").write("\n".join(lines) + "\n")
    print(f"ledger: projected {len(active)} active events, {len(objs)} objects -> story.md"
          + (f" (+{len(recs)-len(active)} revisions)" if audit else ""))


def revision(fixture, obj):
    """The V2 `revision` probe: 'what did the system originally believe about <obj>, and why did it
    change?' — answerable ONLY because supersession preserved the retired claim. Prints the original
    belief, the revised interpretation, and the licensing evidence. Exit 0 if a revision exists."""
    recs = load_ledger(fixture)
    by_id = {r["id"]: r for r in recs}
    retired = [r for r in recs if r.get("status") == "superseded" and r["object"] == obj]
    if not retired:
        print(f"revision[{obj}]: no revision — the system never retired a belief about {obj}")
        return 1
    by_sup = {r["supersedes"]: r for r in recs if r.get("supersedes") is not None}
    for r in retired:
        nxt = by_sup.get(r["id"])
        print(f"revision[{obj}]:")
        print(f"  ORIGINALLY believed: {r['summary']} "
              f"(INFERRED {r['member']} conf={r['conf']}, license={r['license']})")
        if nxt:
            print(f"  REVISED to: {nxt['summary']} (conf={nxt['conf']}, license={nxt['license']})")
            if nxt.get("candidates"):
                for c in nxt["candidates"]:
                    print(f"    - candidate: {c['label']} -> {c['distinct_count']} distinct (conf={c['conf']})")
            print(f"  WHY: {nxt['evidence']}")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("fixture")
    b.add_argument("--wav", default="scene.wav")
    b.add_argument("--no-supersede", action="store_true", help="rung B (no reacquire supersession) for A/B measure")
    p = sub.add_parser("project")
    p.add_argument("fixture")
    p.add_argument("--audit", action="store_true", help="append the revisions: audit trail")
    v = sub.add_parser("validate")
    v.add_argument("target", help="fixture dir or ledger.jsonl")
    rv = sub.add_parser("revision")
    rv.add_argument("fixture")
    rv.add_argument("object")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.fixture, a.wav, supersede=not a.no_supersede)
    elif a.cmd == "project":
        project(a.fixture, audit=a.audit)
    elif a.cmd == "validate":
        bad = validate(load_ledger(a.target))
        if bad:
            sys.exit("ledger: LAW VIOLATION (supersedes must target INFERRED):\n  " + "\n  ".join(bad))
        print("ledger: valid — no OBSERVED-targeting supersession")
    elif a.cmd == "revision":
        sys.exit(revision(a.fixture, a.object))


if __name__ == "__main__":
    main()
