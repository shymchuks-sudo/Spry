# Lab 8 Code and Architecture Explanation

This document explains the producer, consumer, Athena SQL queries, and AWS streaming pipeline in simple terms, detailing every design decision.

---
## Architecture Overview
- **Batch Path (Part 2)**: S3 -> AWS Athena (JSON SerDe vs Parquet via CTAS), Glue Crawler comparison.
- **Local Streaming Path (Part 3)**: Python Producer -> Redpanda (Kafka API) -> Python Consumer (tumbling event-time windows, watermarking, state checkpointing).
- **Cloud Streaming Path (Part 4)**: Python Producer -> Amazon Kinesis Data Streams -> Amazon Data Firehose -> Amazon S3 + AWS Lambda -> Amazon SNS (Alerts).
