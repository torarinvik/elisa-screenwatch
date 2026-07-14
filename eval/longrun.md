# V6 — long-running integrated trial (deterministic backbone)

The verifiable, deterministic half of V6.1, run by `eval/longrun.sh` over real footage — the properties
that DON'T need the 2-hour LLM-in-the-loop singer. Date 2026-07-14.

## Run: PoP gameplay, t0=150 s, 90 s @ fps=10 (45 batches)

Ledger built over increasing batch prefixes (a proxy for time-in-session), measuring growth + latency:

| batches | records | bytes | bytes/record | project_ms |
|---:|---:|---:|---:|---:|
| 2  | 56  | 22 262  | 397 | 36 |
| 8  | 191 | 80 499  | 421 | 35 |
| 14 | 339 | 143 829 | 424 | 35 |
| 20 | 483 | 204 892 | 424 | 36 |
| 26 | 626 | 266 162 | 425 | 36 |
| 32 | 761 | 324 153 | 425 | 36 |
| 38 | 834 | 352 595 | 422 | 36 |
| 44 | 925 | 392 389 | 424 | 36 |

- **Ledger growth is LINEAR IN EVENTS, not wall-clock.** bytes/record is flat at ~424 across 56→925
  records (a 16× range). Size tracks the number of events, exactly as V6.3 requires.
- **Projection latency is BOUNDED.** `project` stays ~35–36 ms from 56 to 925 records — it does not grow
  with ledger size (the projection re-reads but the render cost is dominated by active records, which
  churn rather than accumulate). No latency blow-up over the session.
- **Crash-recovery foundation: rebuild is BYTE-IDENTICAL.** Rebuilding the ledger from the batches twice
  produces identical bytes — because vidingest timestamps are synthetic/replayable (no wall clock). This
  is the property crash recovery relies on: re-running from the archive reconstructs identical working
  state. (The live `kill -9`-mid-session restart, under the running singer, is the resource-gated piece.)
- **The one law holds on real footage** (`validate` clean); **32 genuine supersessions** occurred (V2
  reacquire-candidates from the video's own vanish→appear pairs), all law-valid and audit-projectable.

## What remains (resource-gated)

The full V6.1 needs the 2-hour wall-clock run with the LLM singer building memory live: per-member RSS
curves over time, batch-queue depth under R3 churn, retention-decay probe scores vs time-in-session, and
the live `kill -9` restart. `singer_harness.py` prepares the singer's context but does not drive the loop
autonomously, so that run is left as a dedicated, resourced session. The deterministic backbone above is
what can be measured without it — and it passes.
