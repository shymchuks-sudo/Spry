# Lab 8 Worklog

## Cost and Resource Tracking
| Resource Name | Type | Created At (UTC) | Pricing / Rate | Deleted At (UTC) | Measured Usage / Notes |
|---|---|---|---|---|---|
| `lab8-payments-594559484590` | S3 Bucket | 2026-11-07 11:29:00 | $0.023 / GB-month | Retained | 1.26 GB JSON + 82.5 MB Parquet (~$0.03/mo) |
| Athena Workgroup / Database | Athena Query Engine | 2026-11-07 11:30:30 | $5.00 / TB scanned | Retained | Total scanned: ~18.5 GB (~$0.09) |
| `lab8-glue-crawler-role` | IAM Role | 2026-11-07 11:41:00 | Free | Retained | Glue service role |
| `lab8-payments-crawler` | AWS Glue Crawler | 2026-11-07 11:41:15 | $0.44 / DPU-hour (~$0.015/run) | Deleted after crawl | 1 crawl execution |

## Log of Actions and Findings
- **2026-11-07 11:24:52 UTC**: Setup checks executed.
  - AWS Account: `594559484590` (User: `spry-admin`). Matches required account.
  - AWS Region: `us-east-1`.
  - Git: Created branch `lab8`.
  - Docker Desktop: Version 29.7.2 active.
  - Python: Version 3.13.7.
  - Source dataset verified: `s3://ucu-ooad-lab8-payments/payments/` with partitions `dt=2026-10-01` to `dt=2026-10-31`.
  - Schema inspection: fields confirmed (`invoiceId`, `amount`, `ccy`, `reference`, `createdDate`, `merchantId`, `merchantName`, `mcc`, `customerId`, `paymentMethod`, `device`, `status`, `modifiedDate`, `finalAmount`, `receivedAt`, and optional `failureReason`).

- **2026-11-07 11:29:00 UTC**: S3 Bucket and Dataset Setup.
  - Bucket `lab8-payments-594559484590` created in `us-east-1` and tagged `PROJECT_NAME=lab8`.
  - Synced dataset `s3://ucu-ooad-lab8-payments/payments/` -> `s3://lab8-payments-594559484590/payments/` with `--copy-props none`. All 31 partitions copied.
  - Total raw dataset size: 1,260,692,423 bytes (~1.20 GB).

- **2026-11-07 11:30:30 UTC**: Athena Setup & Part 2 Way A.
  - Athena database `lab8` created.
  - Helper script `lab8/part2/run_athena.py` created to run SQL files and track Query ID, scanned bytes, and runtime in milliseconds.
  - `01_create_table.sql`: External table `payment_events` created with JSON SerDe.
  - `01_msck_repair.sql`: Loaded 31 partitions.
  - `01_count_events.sql`: Counted total raw events = 3,030,197 rows.
  - `02_investigate_*.sql`:
    - Distinct invoice IDs: 1,000,000.
    - Distinct rows across all columns: 3,000,000.
    - Duplicate events: 30,197 events (~0.997%).
    - Zero differing `receivedAt` timestamps within identical `(invoiceId, status, modifiedDate)`.
    - Zero conflicting events with the exact same `modifiedDate` for the same invoice.
  - `02_create_dedup_view.sql`: Created view `payments` with `DISTINCT` + `ROW_NUMBER()` tie-breaker. Rows: 1,000,000.
  - `03_turnover_by_merchant.sql`: Aggregated turnover by merchant and currency. Scanned: 1,202.29 MB | 3,718 ms.
  - `04_failure_rate.sql`: Failure rate per payment method and device. Scanned: 1,202.29 MB | 3,430 ms. All payments are finished (0 unfinished).
  - `05_payments_per_hour.sql`: Hourly distribution (UTC 0..23). Scanned: 1,202.29 MB | 3,848 ms.
  - `06_late_events.sql`: Late events (>60s) = 60,824 (2.0073% of raw). Late (>1h) = 0 (0.0%). Max delay = 600s (10 min).
  - `07_ctas_parquet.sql`: Wrote deduplicated dataset as Parquet (Snappy), partitioned by `dt`, to `s3://lab8-payments-594559484590/curated/payments/`. Total size: 82.5 MB (~15.3x compression).
  - Queries 3, 4, 5 re-run on Parquet:
    - Query 3 Parquet: 6.09 MB scanned (197.4x reduction) | 1,675 ms.
    - Query 4 Parquet: 0.64 MB scanned (1,888.4x reduction) | 1,200 ms.
    - Query 5 Parquet: 6.24 MB scanned (192.6x reduction) | 1,357 ms.
    - Result CSVs confirmed 100% identical between JSON view and Parquet table.
