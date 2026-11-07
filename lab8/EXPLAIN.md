# Lab 8 System Explanation & Architecture Guide

This document explains every component of the data processing pipelines (Batch, Local Streaming, and Cloud Streaming) in clear, plain English, walking through design decisions, mechanics, and failure handling.

---

## 1. Batch Pipeline (Athena & S3)

### Hand-Written DDL vs Glue Crawler
- **Hand-written DDL (`payment_events`)**:
  - Uses `org.openx.data.jsonserde.JsonSerDe`.
  - We explicitly assigned `amount` and `finalAmount` as `bigint`. Because payment amounts are stored in minor currency units (cents, kopecks), high volume or large institutional transfers easily exceed the 32-bit signed integer limit ($21,474,836.47).
  - Dates (`createdDate`, `modifiedDate`, `receivedAt`) are stored as strings and converted on-demand via `from_iso8601_timestamp()` to avoid timezone parsing mismatches in Hive SerDes.
- **Glue Crawler (`lab8_crawled`)**:
  - Automatically inferred `amount` as 32-bit `int`, which introduces overflow risk.
  - Automatically detected `dt` as a partition column based on Hive folder naming conventions (`payments/dt=YYYY-MM-DD/`).
  - Automatically added `failureReason` as a nullable column by scanning across files.
  - Hand-written schemas remain industry standard because they guarantee immutable contract definitions, proper semantic types, and deterministic casing across environments.

### Deduplication: Why `DISTINCT` Precedes `ROW_NUMBER()`
1. In distributed query engines (Presto/Athena, Spark), `ROW_NUMBER() OVER (PARTITION BY invoiceId ...)` requires shuffling all rows across cluster nodes by `invoiceId` and sorting each partition in memory.
2. If exact duplicates exist (identical across all fields), shuffling them creates unnecessary network traffic and memory pressure.
3. Running `SELECT DISTINCT` first collapses physical duplicates early before the window aggregation stage.
4. **Tie-breaking**: If an invoice has multiple events with the same `modifiedDate`, we break ties deterministically by status priority (`success`/`failure` > `processing` > `created`) and then `receivedAt DESC`.
5. **Impact Measured**: Without deduplication, running a naive sum on raw successful events over-reports turnover by **+7.61M** currency units across **9,379** duplicate success records (~0.97% error).

### Parquet vs JSON Performance
- **Columnar Format**: Parquet organizes data by columns instead of rows. A query computing failure rates needs only 3 columns (`paymentMethod`, `device`, `status`), so Athena reads only those byte ranges from S3, completely ignoring the other 13 columns.
- **Snappy Compression**: High repetitive values (e.g., status strings, merchant IDs) compress drastically. The 1.2 GB JSON dataset compressed to 82.5 MB in Parquet (~15.3x compression).
- **Cost Impact**: Athena charges $5.00 per TB scanned. Query 4 scanned **1,202.29 MB** on JSON vs only **0.64 MB** on Parquet, making the Parquet query **1,888x cheaper** and reducing query execution time from 3.4s to 1.2s.

---

## 2. Local Streaming Pipeline (Redpanda + Python)

### Producer Design (`producer.py`)
- Reads raw events for a given partition date (`dt=2026-10-01`), sorts them by `receivedAt` to mimic real-world network arrival order, and publishes them to Kafka topic `payments`.
- **Partitioning Key (`invoiceId`)**:
  - Kafka guarantees FIFO message ordering **only within a partition**.
  - By hashing `invoiceId` as the record key, all lifecycle events for a single payment (`created` -> `processing` -> `success`/`failure`) are guaranteed to arrive at the exact same partition in strict sequential order.
- **Deterministic Failure Injection (`--fail-rate`)**:
  - Uses MD5 hash of `invoiceId` modulo 1.0 to decide whether an invoice fails.
  - Because the decision is tied to `invoiceId`, all lifecycle events for that payment maintain integrity; the final terminal event is deterministically transformed into `status='failure'` with `finalAmount=0` and a descriptive `failureReason`.

### Consumer Design (`consumer.py`)
- **Deduplication Cache & Eviction**:
  - Stores seen event signatures (`invoiceId:status:modifiedDate`).
  - An in-memory cache cannot grow indefinitely without causing Out-Of-Memory (OOM) crashes.
  - The consumer evicts cache entries whose event time is older than `watermark - 15 minutes`.
  - *Production Note*: In enterprise production (e.g. Apache Flink or Kafka Streams), this state is stored in RocksDB state backends or an external Redis cluster configured with a Key-Level Time-To-Live (TTL).
- **Event-Time Tumbling Windows & Watermarks**:
  - Windows are strictly evaluated on **event time** (`modifiedDate`), not system arrival time.
  - `watermark = max_event_time_seen - allowed_lateness`.
  - A window `[T, T+60)` is closed only when the watermark passes `T+60`.
  - Events arriving with timestamps older than the closed window's boundary are rejected as "late rejected".
- **Delivery Guarantees & State Checkpointing**:
  - If a consumer commits Kafka offsets before saving window aggregates, a crash causes unpersisted window state to be lost forever (data loss).
  - If a consumer saves state after committing offsets, a crash causes re-read records to be double-counted (duplicate computation).
  - To achieve at-least-once with idempotent exactly-once aggregation, the consumer:
    1. Writes its state snapshot (watermark, open window buckets, deduplication set) atomically to a checkpoint file on disk.
    2. Only *after* the checkpoint write succeeds, issues a synchronous commit for Kafka partition offsets (`enable.auto.commit = False`).
    3. On restart, the consumer loads the checkpoint and resumes Kafka consumption exactly where it left off, resulting in zero loss and zero double counting.
