# Lab 8 - Part 3: Local Streaming (Redpanda + Python) Answers

## 1. Architecture & Setup
- **Broker & Platform**: Redpanda Single Broker (v24.1+) with Redpanda Console running in Docker via [docker-compose.yml](file:///C:/Users/Andriy/ооад/Spry/lab8/part3/docker-compose.yml).
- **Topic**: `payments` configured with **3 partitions** (`rpk topic create payments -p 3`).
- **Kafka Client**: `confluent-kafka` (librdkafka C bindings) running in isolated virtual environment `lab8/.venv/`.
- **Producer ([producer.py](file:///C:/Users/Andriy/ооад/Spry/lab8/part3/producer.py))**:
  - Replays events from `lab8/data/dt=2026-10-01/events.jsonl` sorted by arrival time (`receivedAt`).
  - Message key = `invoiceId` (ensures strict FIFO ordering per payment within a single partition).
  - Deterministic failure injection via `hashlib.md5(invoiceId)`.
- **Consumer ([consumer.py](file:///C:/Users/Andriy/ооад/Spry/lab8/part3/consumer.py))**:
  - Consumer Group: `payments-cg`.
  - Manual offset commit (`enable.auto.commit = False`) strictly after writing state snapshot to disk.
  - Event-time tumbling 1-minute windows on `modifiedDate` with configurable watermarking (`watermark = max_event_time - allowed_lateness`).
  - Deduplication cache with automatic eviction of entries older than `watermark - 15 minutes`.

---

## 2. Experiment 1: Baseline vs Mid-Stream Crash & Restart

### Objective
Prove that persisting state snapshots prior to committing Kafka offsets guarantees **exactly-once per-window aggregation** without data loss or double counting when a consumer crashes mid-stream.

### Setup & Run
1. Replayed the first 60 minutes of October 1, 2026 (636 total events across 3 partitions).
2. **Sub-experiment 1A (Baseline)**: Ran consumer to full completion.
3. **Sub-experiment 1B (Crash & Restart)**: Produced the identical 636 events. Ran consumer with `--crash-at 300` (abruptly terminated after 300 events without flushing open windows). Inspected mid-stream committed offsets and lag via `rpk group describe`. Restarted the consumer using the persisted checkpoint to finish the remaining 336 events.

### Measured Results Comparison
*Source files: `lab8/part3/results/exp1_baseline.json` vs `lab8/part3/results/exp1_restart.json`*

| Metric | Clean Baseline Run (1A) | Crash & Restart Run (1B) | Difference |
|---|---|---|---|
| **Total Events Consumed** | `636` | `636` | `0` (Zero loss) |
| **Duplicates Dropped** | `7` | `7` | `0` (Zero double counting) |
| **Late Rejected Events** | `404` | `404` | `0` (Exact matching watermark progression) |
| **Windows Closed** | `42` | `42` | `0` (Identical window count) |
| **Alerts Fired (> 10% Share)** | `4` | `4` | `0` (Identical alert triggering) |
| **Unique Window Records Evaluated** | `58` | `58` | `0` |
| **Per-Window Metric Discrepancies** | **0** | **0** | **100% IDENTICAL** |

### Committed Kafka Offsets Evidence (`rpk group describe payments-cg`)

#### At Mid-Stream Crash (after 300 events):
*Source file: `lab8/part3/results/exp1_offsets_crash.txt`*
```text
TOPIC     PARTITION  CURRENT-OFFSET  LOG-START-OFFSET  LOG-END-OFFSET  LAG
payments  0          208             0                 208             0
payments  1          92              0                 204             112
payments  2          -               0                 224             224
TOTAL-LAG: 336
```

#### After Consumer Restart & Completion:
*Source file: `lab8/part3/results/exp1_offsets_final.txt` (Identical to Baseline `exp1_offsets_baseline.txt`)*
```text
TOPIC     PARTITION  CURRENT-OFFSET  LOG-START-OFFSET  LOG-END-OFFSET  LAG
payments  0          208             0                 208             0
payments  1          204             0                 204             0
payments  2          224             0                 224             0
TOTAL-LAG: 0
```

---

## 3. Experiment 2: Multi-Consumer Scalability & Partition Rebalancing

### Objective
Run two consumers concurrently in the same consumer group (`payments-cg`) over a 3-partition topic and inspect workload distribution and architectural trade-offs.

### Measured Partition Distribution
*Source files: `lab8/part3/results/exp2_c1.json`, `lab8/part3/results/exp2_c2.json`, `exp2_group_describe.txt`*

| Worker ID | Client ID | Partitions Assigned | Events Consumed | Share of Traffic | Active Dedup Set |
|---|---|---|---|---|---|
| **Worker 1** | `worker-1` | Partition 0, Partition 1 | `412` events (208 + 204) | 64.78% | 146 keys |
| **Worker 2** | `worker-2` | Partition 2 | `224` events (224) | 35.22% | 63 keys |
| **Total** | `payments-cg` | All 3 Partitions | **636 events** | **100.0%** | **209 keys** |

### Architectural Insight: Partial Window Aggregation
- **Why Partition by `invoiceId`?** Partitioning by `invoiceId` ensures that all events for a specific invoice (`created` -> `processing` -> `success`/`failure`) reach the same partition, guaranteeing in-order processing per payment without race conditions.
- **The Trade-Off**: Because transactions are partitioned by `invoiceId` rather than `paymentMethod`, each worker node only observes a partition slice of the total payment method transactions. Consequently, each worker's tumbling window computes failure rates over its assigned subset of transactions rather than a global cohort.
- **Production Solution**: A production stream processing architecture (e.g. Apache Flink, Kafka Streams) solves this by executing a two-stage stream topology:
  1. Primary ingestion stream keyed by `invoiceId` to perform stateful transaction deduplication and lifecycle resolution.
  2. A secondary key shuffle (`keyBy(paymentMethod)`) where resolved terminal events are routed to window operators grouped strictly by `paymentMethod`.

---

## 4. Experiment 3: Deterministic Failure Injection (`--fail-rate 0.3`)

### Objective
Demonstrate real-time threshold alert detection by elevating the payment failure share to ~30% using deterministic invoice-level hashing.

### Measured Comparison: Baseline vs Failure Injection
*Source files: `lab8/part3/results/exp3_failrate.json` vs `lab8/part3/results/exp1_baseline.json`*

| Metric | Baseline Run (Normal Traffic) | Injected Failure Run (`--fail-rate 0.3`) | Impact |
|---|---|---|---|
| **Total Consumed** | `636` | `636` | Same dataset |
| **Terminal Events Counted** | `74` | `76` | Terminal lifecycle preserved |
| **Observed Terminal Failures** | `4` | **27** | +23 injected failures |
| **Overall Failure Rate** | **5.41%** | **35.53%** | **+30.12% failure surge** |
| **Window Alerts Fired (> 10%)** | **4 alerts** | **25 alerts** | **6.25x increase in alerts** |

### Sample Alert Log Output (`exp3_failrate.log`)
```text
[WINDOW CLOSED] 2026-10-01T00:54:00Z | Method: card         | Terminal:    3 | Failures:   1 | Share: 33.33% [ALERT > 10%]
  *** ALERT: Failure share for card is 33.33% (exceeds 10.0% threshold) ***
[WINDOW CLOSED] 2026-10-01T00:55:00Z | Method: apple_pay    | Terminal:    2 | Failures:   1 | Share: 50.00% [ALERT > 10%]
  *** ALERT: Failure share for apple_pay is 50.00% (exceeds 10.0% threshold) ***
```

---

## 5. Experiment 4: Allowed Lateness (120s vs 0s)

### Objective
Measure the impact of watermarking buffer latency on out-of-order event ingestion and window accuracy.

### Measured Results: 120 Seconds vs 0 Seconds
*Source files: `lab8/part3/results/exp4_lateness120.json` vs `lab8/part3/results/exp4_lateness0.json`*

| Metric | Default Allowed Lateness (120s) | Zero Allowed Lateness (0s) | Variance |
|---|---|---|---|
| **Total Events Consumed** | `636` | `636` | Identical stream |
| **Late Rejected Events** | `399` | **421** | **+22 events dropped** |
| **Valid Terminal Events Included** | **76** | **69** | **-7 terminal events lost** |
| **Windows Successfully Closed** | **43** | **41** | **-2 windows dropped** |

### Key Takeaways:
1. When `--lateness 0` is set, `watermark = max_event_time_seen`. If an event arrives out-of-order (even by 1-2 seconds) behind a newer event whose 1-minute window has already closed, it is immediately discarded.
2. In our run, zero lateness caused **22 legitimate events** to be rejected, including **7 terminal payment events**, resulting in **2 entire 1-minute windows** failing to receive their closing evaluations.
3. Setting allowed lateness to **120 seconds** provides the optimal balance: it absorbs network transit jitter and delayed webhook arrivals (which max out at 600s in this dataset) without delaying real-time alert generation by more than 2 minutes.
