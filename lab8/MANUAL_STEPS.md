# Manual Steps & Screenshots Guide

This document lists the exact actions and screenshots needed from you in the AWS Console and Redpanda Console.

---

## 1. Athena Console Screenshots (Part 2)

Go to **AWS Console -> Amazon Athena -> Query editor**. Ensure your Workgroup is active and Database is set to `lab8`.

In the **Recent queries** tab (bottom panel), you can see all query history along with their exact **Run time** and **Data scanned**.

### Recommended Screenshots:
1. **Query 3 (Turnover) Comparison**:
   - Open query history for `03_turnover_by_merchant_json` (Query ID: `15753b82-58bf-4b1d-86b9-bf76aae8778c`)
     - Data scanned: **1.20 GB**, Run time: **~3.7 s**
   - Open query history for `03_turnover_by_merchant_parquet` (Query ID: `0d363dfa-7061-4cd1-b422-2795a341c51f`)
     - Data scanned: **6.09 MB**, Run time: **~1.7 s**
   - *Take a screenshot showing the query editor and the execution metrics box.*

2. **Query 4 (Failure Rate) Comparison**:
   - Query ID JSON: `1aadfe83-e761-47cd-814b-aa1b6a91c469` (Data scanned: **1.20 GB**)
   - Query ID Parquet: `1ddd1604-306b-46cb-a105-c091d20ed3c8` (Data scanned: **0.64 MB**)
   - *Take a screenshot highlighting the 1888x reduction in data scanned.*

3. **Query 5 (Hourly Distribution) Comparison**:
   - Query ID JSON: `64c3f3fb-47c4-4fff-a72a-e495fb5e7555` (Data scanned: **1.20 GB**)
   - Query ID Parquet: `fe725e9f-570b-41bd-b8dc-a0b083ce10a1` (Data scanned: **6.24 MB**)

---

## 2. Redpanda Console Screenshots (Part 3)

Open your web browser and navigate to the Redpanda Console at:
👉 **[http://localhost:8080](http://localhost:8080)**

### Required Screenshots:
1. **Topic Overview (`payments`)**:
   - Go to **Topics** in the left sidebar -> Click on **`payments`**.
   - URL: `http://localhost:8080/topics/payments`
   - Verify that **3 Partitions** are displayed (Partitions 0, 1, 2).
   - Click on the **Messages** tab to view sample replayed JSON records with `invoiceId` partition keys.
   - *Take a screenshot of the topic overview showing the 3 partitions and message count.*

2. **Consumer Group Overview (`payments-cg`)**:
   - Go to **Consumers** in the left sidebar -> Click on **`payments-cg`**.
   - URL: `http://localhost:8080/groups/payments-cg`
   - View the active group members, partition assignments, and committed log offsets / lag (0 lag).
   - *Take a screenshot showing the consumer group state.*

---

## 3. Streaming Query Screenshot (Part 4)
*(To be completed during Part 4: Athena query over streamed_events)*

---

## 4. Confirming SNS Email Subscription (Part 4)
*(To be completed during Part 4: check your email inbox and click Confirm Subscription)*

---

## 5. Final Packaging & Submission
*(Upload lab8_part2.md, lab8_part3.md, lab8_part4.md, lab8_code.zip, lab8_screenshots.zip, and paste ONLINE_TEXT.md)*

---

## 6. Post-Lab Cost Check
- Navigate to **AWS Console -> Billing and Cost Management -> Bills**.
- Review current day charges to verify all streaming resources stopped incurring costs.
