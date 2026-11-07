-- Query 5 on Curated Parquet table
SELECT
    hour(from_iso8601_timestamp(createdDate)) AS hour_utc,
    count(*) AS payment_count
FROM payments_curated
GROUP BY
    hour(from_iso8601_timestamp(createdDate))
ORDER BY
    hour_utc;
