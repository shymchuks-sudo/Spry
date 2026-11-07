# Part 4 - own cloud pipeline (AWS us-east-1)

Pipeline: producer_kinesis.py -> Kinesis Data Stream lab8-payments-stream (1 shard) -> Firehose lab8-payments-firehose (60 s buffer) -> S3 streamed/dt=YYYY-MM-DD/ -> Athena table streamed_events. Alert path: Kinesis -> Lambda lab8-alert (event source mapping, batch size 500) -> SNS topic lab8-alerts -> e-mail. Diagram: part4_pipeline_diagram.png.

## What was sent
- Run A: 20,000 events from offset 0 in 46.3 s (432 records/s).
- Run B, run twice with the same offset 20000, limit 3000 and --fail-rate 0.3: 3,000 events each, 7.9 s and 8.3 s (382 and 363 records/s). Because both runs used the same offset, the same 3,000 events were sent twice, so the streamed table contains duplicates.
- Total sent: 26,000 records. Athena shows 26000 rows and 7593 distinct invoices (query 12_streamed_count.sql).
- Delivery delay: right after run A, Athena showed 17,645 of 20,000 rows; the rest arrived after Firehose flushed its last 60 s buffer.

## Alert through SNS
The Lambda counts final events (success, failure) per paymentMethod in each batch; with at least 20 final events and a failure share above 10% it publishes to SNS. After lowering MIN_EVENTS from 30 to 20 and raising the batch size from 100 to 500 (with batch size 100 only about 33 events per batch were final, so the old threshold could never be reached), the e-mails arrived at 14:43 Kyiv time, right after the second run B: "card failure share 48% (11 of 23 final events in one batch)" and "card failure share 45% (9 of 20 final events in one batch)" (screenshot part4_sns_alert_email.png). These alerts were triggered by the injected failures of run B (--fail-rate 0.3).

## Athena query over the streamed data (13_streamed_failure_by_method.sql)

| paymentMethod | final events | failures | failure % |
|---|---|---|---|
| card | 4778 | 637 | 13.3 |
| qr | 181 | 24 | 13.3 |
| apple_pay | 2211 | 256 | 11.6 |
| google_pay | 1501 | 162 | 10.8 |

The query scanned 10,839,863 bytes in 607 ms (screenshot part4_athena_query.png). The numbers include the duplicated run B and its injected failures. For comparison, at the first check (run A only, 17,645 rows) the failure share was 371 of 5,876 final events = 6.3%. The streamed table is not deduplicated; a correct count would use DISTINCT / row_number() as in Part 2.

## Comparison with Part 3
- Where the logic runs: in Part 3 my own consumer holds the state (dedup set, windows, watermark) and a checkpoint file; in Part 4 AWS runs the transport (Kinesis), the delivery to storage (Firehose) and the alert (Lambda), and I wrote only the producer and the Lambda.
- Time: Part 3 aggregates by event time (modifiedDate) in 1-minute windows with a watermark and 2 minutes of allowed lateness. The Lambda alert looks only at one batch of records (processing time): no windows and no handling of late events.
- Duplicates: Part 3 drops them (7 in 636 events); the cloud pipeline keeps them in S3 and Athena, so they must be removed in the query.
- Latency: in Part 3 a window closes as soon as the watermark passes it; in Part 4 data reaches S3 and Athena only after the 60 s Firehose buffer.
- Scaling: Part 3 parallelism is limited by the 3 partitions (2 consumers split them in Experiment 2); Part 4 has one shard (up to 1 MB/s or 1,000 records/s in); one producer reached 432 records/s.
- Cost and operation: Part 3 ran in local Docker and cost nothing; Part 4 bills per shard-hour even when idle, so the Kinesis and Firehose streams had to be deleted (99_teardown.ps1; aws kinesis list-streams and aws firehose list-delivery-streams both return empty lists).

## Cost of the cloud pipeline (estimate at list prices)

| Item | Basis | USD |
|---|---|---|
| Kinesis shard | 1 shard, created 12:12 UTC, deleted 11/07/2026 16:42:32 UTC = 4.5 h, billed per started hour: 5 h x 0.015 | 0.075 |
| Kinesis PUT | 26,000 records (each under 25 KB = 1 unit) x 0.014 per million | 0.0004 |
| Firehose | 26,000 records rounded up to 5 KB = 0.124 GB x 0.029 per GB | 0.0036 |
| Athena | about 7-11 MB scanned per query (10 MB billing minimum), 5 USD per TB | below 0.001 in total |
| Lambda, SNS, S3 | free tier / a few KB | about 0 |
| Total | | about 0.079 |

Prices are the public us-east-1 list prices as I know them; they should be checked on the AWS pricing pages. The shard-hour dominates the cost.
