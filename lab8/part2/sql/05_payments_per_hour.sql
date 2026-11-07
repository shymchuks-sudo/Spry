-- Query 5: Number of payments per hour of day (UTC)
SELECT
    hour(from_iso8601_timestamp(createdDate)) AS hour_utc,
    count(*) AS payment_count
FROM payments
GROUP BY
    hour(from_iso8601_timestamp(createdDate))
ORDER BY
    hour_utc;
