# pharo t=14.2–16.1s inspection — what flung track 15

Pre-work for `orchestra_v3_plan.md` V3.0 (evidence-gathering, not repair). Date: 2026-07-14.
Source: the 2026-07-13 pharo census (`/tmp/pharo_tracks.txt`, `vidingest ... --fps 10 --dur 60`);
frames re-viewed from a same-params 20 s re-ingest (identical frames at these timestamps).

## The finding — track 15 is the MOUSE CURSOR

Every frame in the window the tracker detects exactly **3 components** (`ncomp=3`):

1. `cx=56 cy=7 area~1330 bbox=0,0,191,22` — the top toolbar/title bar (full-width, static).
2. `cx=83 cy=128 area~664 bbox=0,126,191,130` — the bottom taskbar (full-width, static).
3. **one tiny 6–10 px blob** that moves through the blank white workspace — this is track 15.

Zooming into that blob at three of its positions (`t14_cursor_evidence.png`) shows the classic
**arrow pointer** at every one. Track 15 is the presenter's mouse cursor, moved in a loop across the
empty IDE workspace. The two other components are static chrome the tracker correctly ignores.

## The trajectory and the fabricated REVERSE

Grid coords (192×132), cursor path — a smooth loop, repeated:

```
t=13.5 (143,28) → 13.7 (142,66) → 13.8 (101,87) → 13.9 (37,88) → 14.1 (17,47)
  → 14.2 REVERSE (17→29,33) → 14.3 (64,30) → 14.4 (112,34) → 14.6 (140,48)
  → 14.7 turn → 14.8 (107) → 14.9 (58) …            (the loop repeats; each turn = another REVERSE)
```

At t=14.2s the cursor reaches the left extreme and turns; the tracker emits
`INF event id=15 kind=REVERSE t=14200 cx=17 cy=33 conf=85` — a high-confidence **physical-motion
event for a mouse pointer changing direction**. It does this again each time the presenter reverses
the mouse (t≈14.7s, …). These are the "4 flung REVERSEs on track 15, all conf=85" from the census.

## Velocity profile (for gate design)

`vx` (grid px / 100 ms frame): `0,0,-2,+5,-6,-41,-64,-13,-7,│+12,+35,+48,+23,+5,-1,-32,-49`
Peak |vx| = 64 — the cursor crosses **1/3 of the frame width in one frame**, with frame-to-frame
acceleration up to ~35/frame. No physical scene object moves like this; a mouse flick does.

## Implication for V3.0 — the failure has TWO sub-modes, not one

The plan (amended 2026-07-13) attributes the pharo failure to "association across unrelated UI
components." That is the AGGREGATE churn mode (61 tracks / 51 VANISH / 43 OCCLUDED). **Track 15 is a
different, cleaner sub-mode:** a single *coherent, well-associated* object (the cursor — huge
association margin, it is the only small mover) that is simply the **wrong kind** of object. Its
motion events are meaningless, yet it passes the intuitive trackability tests: persistent, stable
tiny area, sole small component (association margin ≈ ∞), no split/merge churn.

Consequences for the gate:

- **Bounded centroid acceleration / max plausible velocity** catches the *flicks* (|vx| 41/64/48/49
  are non-physical) — cheap, and it would suppress the dir=±1 integration during the fast legs.
- But the REVERSE itself sits at a *gentle* turn (vx −7 → +12); acceleration bounds alone let it
  through. Catching it needs a **scene-relative area floor** and/or a **"sole tiny mover over static
  full-frame chrome ⇒ UI pointer, not a scene object"** heuristic — i.e. applicability, not just
  motion smoothness. A 6–10 px blob whose only frame-mates are two full-width static bars is a
  cursor; `UNTRACKABLE` / `activity_type=UI_CHANGE` is the honest verdict, and no REVERSE is admitted.

Net: V3.0 must reject track 15 on **applicability (what kind of thing this is)**, because it is
otherwise a textbook-clean track. This is the sharpest possible motivation for the trackability gate:
association repairs (V3.1–V3.2) would make track 15 *better argued*, never *withheld*.
