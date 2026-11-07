-- Comparison of metrics WITH vs WITHOUT deduplication
SELECT
    'with_dedup' AS pipeline_stage,
    count(*) AS total_rows,
    sum(cast(finalAmount AS bigint)) AS total_final_amount_minor,
    CAST(sum(finalAmount) / 100.0 AS DECIMAL(18, 2)) AS total_turnover_major
FROM payments
WHERE status = 'success'

UNION ALL

SELECT
    'without_dedup_raw_success' AS pipeline_stage,
    count(*) AS total_rows,
    sum(cast(finalAmount AS bigint)) AS total_final_amount_minor,
    CAST(sum(finalAmount) / 100.0 AS DECIMAL(18, 2)) AS total_turnover_major
FROM payment_events
WHERE status = 'success'

UNION ALL

SELECT
    'without_dedup_just_row_number_without_distinct' AS pipeline_stage,
    count(*) AS total_rows,
    sum(cast(finalAmount AS bigint)) AS total_final_amount_minor,
    CAST(sum(finalAmount) / 100.0 AS DECIMAL(18, 2)) AS total_turnover_major
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY invoiceId ORDER BY modifiedDate DESC) AS rn
    FROM payment_events
)
WHERE rn = 1 AND status = 'success';
