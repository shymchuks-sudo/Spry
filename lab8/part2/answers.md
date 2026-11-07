# Lab 8 - Part 2: Batch on AWS (Athena + Glue) Answers

## 1. Scale Answers (Measured)
- **Total raw events**: `3,030,197`
- **Total unique `invoiceId`**: `1,000,000`
- **Total distinct events across all columns**: `3,000,000`
- **Total duplicate events**: `30,197` (computed as `3,030,197 - 3,000,000`, representing `0.9965%` ~ `1.0%` duplicate events)
- **Share of events arriving > 60s late**: `2.0073%` (60,824 out of 3,030,197 raw events; 60,231 out of 3,000,000 deduplicated events)
- **Share of events arriving > 1 hour late**: `0.0%` (0 events out of 3,030,197; maximum observed arrival delay across the entire dataset is 600 seconds = 10 minutes)

---

## 2. Deduplication Findings & Design
- **Investigation of Duplicates**:
  - All 30,197 duplicate events are 100% identical across all columns (including `receivedAt` and `dt`). No instances were found where the same event `(invoiceId, status, modifiedDate)` had diverging `receivedAt` values (`diff_received_at_count = 0`).
  - No tie collisions were detected where two distinct events for the same `invoiceId` shared the exact same `modifiedDate` timestamp.
- **Deduplication Strategy**:
  - We first apply `DISTINCT` across all columns to eliminate physical duplicate records early.
  - Then we evaluate `ROW_NUMBER() OVER (PARTITION BY invoiceId ORDER BY modifiedDate DESC, status_priority DESC, receivedAt DESC)` to deterministically select the final state of each payment.
  - Status priority hierarchy: `success` (3) / `failure` (3) > `processing` (2) > `created` (1) > other (0).
  - Tie-breaker: `from_iso8601_timestamp(receivedAt) DESC`.
- **Impact of Missing Deduplication**:
  - Computing turnover on raw `payment_events` where `status = 'success'` yields **949,199** events and a turnover of **788,712,575.40** (inflated by **9,379** duplicate success events and **7,615,229.53** in phantom turnover, an error of ~0.97%).
  - With proper deduplication in the `payments` view, there are exactly **939,820** successful payments totaling **781,097,345.87**.
 DISTINCT is applied before row_number() because a re-delivered final event exists twice with the same modifiedDate, so the two copies tie and which one receives rank 1 is arbitrary. In this dataset the duplicates are exact copies (0 differing receivedAt values were measured), so the result happens to be the same either way, but if the copies ever differ (for example in receivedAt) the result can change between runs, and rank() would return both rows. Removing exact duplicates first makes the ranking deterministic. Without deduplication, counts and sums are inflated: the raw table gives 949,199 success events and a turnover of 788,712,575.40, while the deduplicated data gives 939,820 successful payments and 781,097,345.87, so the raw figures are about 1% too high.

---

## 3. Query Results (Queries 3 to 6)

### Query 3: Turnover by Merchant and Currency (Successful Payments)
*Source file: `lab8/part2/results/03_turnover_by_merchant_parquet.csv` (identical to JSON view)*

| merchantId | merchantName | currency | payment_count | total_turnover |
|---|---|---|---|---|
| `m-001` | Кав'ярня | EUR | 2,802 | 365,038.15 |
| `m-001` | Кав'ярня | UAH | 87,637 | 11,435,687.68 |
| `m-001` | Кав'ярня | USD | 3,819 | 505,697.22 |
| `m-002` | Супермаркет | EUR | 2,841 | 1,737,547.31 |
| `m-002` | Супермаркет | UAH | 87,283 | 54,147,597.02 |
| `m-002` | Супермаркет | USD | 3,776 | 2,310,115.59 |
| `m-003` | Таксі | EUR | 2,875 | 724,136.69 |
| `m-003` | Таксі | UAH | 87,307 | 21,528,219.39 |
| `m-003` | Таксі | USD | 3,742 | 923,507.17 |
| `m-004` | Доставка їжі | EUR | 2,727 | 1,427,829.18 |
| `m-004` | Доставка їжі | UAH | 87,820 | 46,044,018.26 |
| `m-004` | Доставка їжі | USD | 3,754 | 2,036,639.20 |
| `m-005` | Онлайн-кінотеатр | EUR | 2,840 | 423,160.00 |
| `m-005` | Онлайн-кінотеатр | UAH | 87,357 | 13,016,193.00 |
| `m-005` | Онлайн-кінотеатр | USD | 3,688 | 549,512.00 |
| `m-006` | Музичний сервіс | EUR | 2,777 | 274,923.00 |
| `m-006` | Музичний сервіс | UAH | 87,517 | 8,664,183.00 |
| `m-006` | Музичний сервіс | USD | 3,762 | 372,438.00 |
| `m-007` | Аптека | EUR | 2,758 | 1,203,052.19 |
| `m-007` | Аптека | UAH | 87,374 | 38,554,151.04 |
| `m-007` | Аптека | USD | 3,727 | 1,659,126.96 |
| `m-008` | АЗС | EUR | 2,873 | 4,708,258.32 |
| `m-008` | АЗС | UAH | 87,560 | 144,641,341.06 |
| `m-008` | АЗС | USD | 3,600 | 5,856,481.33 |
| `m-009` | Інтернет-магазин | EUR | 2,840 | 10,084,500.30 |
| `m-009` | Інтернет-магазин | UAH | 87,115 | 310,259,259.21 |
| `m-009` | Інтернет-магазин | USD | 3,725 | 13,840,942.83 |
| `m-010` | Квитки | EUR | 2,745 | 2,451,613.23 |
| `m-010` | Квитки | UAH | 87,303 | 77,749,863.65 |
| `m-010` | Квитки | USD | 3,876 | 3,602,313.89 |

### Query 4: Failure Rate per Payment Method and Device
*Definition: Finished payments = status IN ('success', 'failure'). Failure rate (%) = failed_count / finished_count * 100. Unfinished payments = status NOT IN ('success', 'failure').*
*Source file: `lab8/part2/results/04_failure_rate_parquet.csv`*

| paymentMethod | device | total_payments | success_count | failed_count | finished_count | unfinished_count | failure_rate_pct |
|---|---|---|---|---|---|---|---|
| `qr` | `android` | 6,675 | 6,227 | 448 | 6,675 | 0 | **6.71%** |
| `apple_pay` | `android` | 83,677 | 78,547 | 5,130 | 83,677 | 0 | **6.13%** |
| `google_pay` | `web` | 59,996 | 56,351 | 3,645 | 59,996 | 0 | **6.08%** |
| `apple_pay` | `ios` | 83,164 | 78,139 | 5,025 | 83,164 | 0 | **6.04%** |
| `card` | `android` | 183,332 | 172,253 | 11,079 | 183,332 | 0 | **6.04%** |
| `card` | `web` | 183,435 | 172,415 | 11,020 | 183,435 | 0 | **6.01%** |
| `google_pay` | `ios` | 59,761 | 56,171 | 3,590 | 59,761 | 0 | **6.01%** |
| `qr` | `web` | 6,669 | 6,269 | 400 | 6,669 | 0 | **6.00%** |
| `google_pay` | `android` | 59,450 | 55,887 | 3,563 | 59,450 | 0 | **5.99%** |
| `apple_pay` | `web` | 83,505 | 78,539 | 4,966 | 83,505 | 0 | **5.95%** |
| `card` | `ios` | 183,541 | 172,629 | 10,912 | 183,541 | 0 | **5.95%** |
| `qr` | `ios` | 6,795 | 6,393 | 402 | 6,795 | 0 | **5.92%** |

*Note: Exactly 0 unfinished payments exist in the final state of the dataset; all 1,000,000 payments reached terminal status.*

### Query 5: Number of Payments per Hour of Day (UTC)
*Source file: `lab8/part2/results/05_payments_per_hour_parquet.csv`*

| Hour (UTC) | Payment Count |
|---|---|
| `00:00` | 6,597 |
| `01:00` | 6,622 |
| `02:00` | 6,592 |
| `03:00` | 6,629 |
| `04:00` | 6,585 |
| `05:00` | 13,291 |
| `06:00` | 26,851 |
| `07:00` | 46,684 |
| `08:00` | 59,947 |
| `09:00` | 53,492 |
| `10:00` | 46,521 |
| `11:00` | 53,438 |
| `12:00` | 66,304 |
| `13:00` | 59,948 |
| `14:00` | 53,306 |
| `15:00` | 53,783 |
| `16:00` | 60,256 |
| `17:00` | 72,905 |
| `18:00` | 80,338 |
| `19:00` | 73,167 |
| `20:00` | 60,219 |
| `21:00` | 46,627 |
| `22:00` | 26,669 |
| `23:00` | 13,229 |

### Query 6: Late Events Summary
*Source file: `lab8/part2/results/06_late_events.csv`*

- **Raw events count**: `3,030,197`
  - Late > 60 seconds: **60,824** events (**2.0073%**)
  - Late > 1 hour (3600 seconds): **0** events (**0.0%**)
- **Deduplicated events count**: `3,000,000`
  - Late > 60 seconds: **60,231** events (**2.0077%**)
  - Late > 1 hour: **0** events (**0.0%**)
- **Maximum delay measured**: **600 seconds** (10 minutes). Minimum delay: **0 seconds**.

---

## 4. Performance & Cost Comparison: JSON vs Parquet
*Athena standard pricing: $5.00 per TB scanned ($0.000004768 per MB).*

| Query | Format | Data Scanned (Bytes) | Data Scanned (MB) | Run Time (ms) | Estimated Cost (USD) | Ratio Cheaper (Bytes) |
|---|---|---|---|---|---|---|
| **Query 3: Turnover** | JSON (via Dedup View) | 1,260,692,423 | 1,202.29 MB | 3,718 ms | $0.005733 | Baseline |
| **Query 3: Turnover** | Parquet (Curated Table) | 6,386,002 | 6.09 MB | 1,675 ms | $0.000029 | **197.4x cheaper** |
| **Query 4: Failure Rate** | JSON (via Dedup View) | 1,260,692,423 | 1,202.29 MB | 3,430 ms | $0.005733 | Baseline |
| **Query 4: Failure Rate** | Parquet (Curated Table) | 667,613 | 0.64 MB | 1,200 ms | $0.000003 | **1,888.4x cheaper** |
| **Query 5: Hourly Dist** | JSON (via Dedup View) | 1,260,692,423 | 1,202.29 MB | 3,848 ms | $0.005733 | Baseline |
| **Query 5: Hourly Dist** | Parquet (Curated Table) | 6,544,596 | 6.24 MB | 1,357 ms | $0.000030 | **192.6x cheaper** |

### Key Takeaways:
1. **Columnar Projection Pruning**: In Query 4 (Failure Rate), only `paymentMethod`, `device`, and `status` columns were accessed. Parquet's columnar format allowed Athena to read only 667 KB instead of scanning all 1.2 GB of JSON records, resulting in an astounding **1,888x cost reduction**.
2. **Compression Efficiency**: Snappy column compression reduced dataset footprint from 1.2 GB to 82.5 MB.
3. **Execution Latency**: Parquet queries ran in ~1.0 - 1.6s compared to ~3.4 - 3.8s for the JSON view, saving both cost and compute cycles.

---

## 5. Way B: Glue Crawler Schema Analysis
*(Source file: `lab8/part2/results/glue_schema.json`)*

The AWS Glue Crawler `lab8-payments-crawler` discovered table `payments` in database `lab8_crawled`:

1. **Types Chosen by Crawler**:
   - `amount` and `finalamount`: Inferred as `int` (32-bit signed integer).
     - *Evaluation*: While 32-bit `int` happens to fit the sample amounts in this dataset, financial payment minor units in high-turnover systems easily overflow `2,147,483,647` minor units (~21.4 million UAH/USD). Our hand-written schema explicitly chose `bigint`, preventing silent overflow bugs.
   - `ccy` and `mcc`: Inferred as `int`.
   - Date fields (`createddate`, `modifieddate`, `receivedat`): Inferred as `string`. Glue JSON classifier does not automatically parse ISO 8601 strings into Hive `timestamp` types unless a custom classifier is defined.
2. **Partition Recognition (`dt`)**:
   - Yes, Glue recognized `dt` as a partition key (`PartitionKeys: [{"Name": "dt", "Type": "string"}]`) because the S3 folder hierarchy follows the Hive standard partition convention (`payments/dt=YYYY-MM-DD/`).
3. **Handling of `failureReason`**:
   - Even though `failureReason` only exists on failed payments (~6% of events), Glue sampled enough lines across the dataset to discover `failureReason` and added it as a nullable `string` column. For events without this key, the SerDe returns SQL `NULL`.
4. **Convenience for Queries & Why Hand-Written Schemas are Still Common**:
   - **Casing & Consistency**: The Glue crawler forces column names to lowercase (`invoiceid`, `merchantid`, `finalamount`), which can disrupt case-sensitive application schemas and ORM mappings.
   - **Semantic Typing**: Automated crawlers infer based on observed values (e.g., choosing `int` for `amount` instead of `bigint`, or `string` instead of proper timestamps). A human engineer understands business domains and designs schemas that guard against future data growth and schema drift.
   - **Cost & Speed**: Running a Glue crawler costs $0.44/DPU-Hour and takes 1–3 minutes per run. Hand-written DDL runs in milliseconds on Athena at practically zero cost.
   - **Production Standard**: Hand-crafted DDL (or Infrastructure-as-Code via Terraform/dbt) provides deterministic version control, avoiding surprise schema alterations caused by rogue crawler runs.
