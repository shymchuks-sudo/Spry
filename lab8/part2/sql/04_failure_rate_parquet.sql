-- Query 4 on Curated Parquet table
SELECT
    paymentMethod,
    device,
    count(*) AS total_payments,
    count_if(status = 'success') AS success_count,
    count_if(status = 'failure') AS failed_count,
    count_if(status IN ('success', 'failure')) AS finished_count,
    count_if(status NOT IN ('success', 'failure')) AS unfinished_count,
    round(
        cast(count_if(status = 'failure') AS double) /
        nullif(count_if(status IN ('success', 'failure')), 0) * 100.0,
        2
    ) AS failure_rate_pct
FROM payments_curated
GROUP BY
    paymentMethod,
    device
ORDER BY
    failure_rate_pct DESC,
    paymentMethod,
    device;
