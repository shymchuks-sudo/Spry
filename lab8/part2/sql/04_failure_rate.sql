-- Query 4: Failure rate per payment method and device
-- Definition:
-- Finished payments = payments with final status 'success' or 'failure'.
-- Unfinished payments = payments with final status 'created' or 'processing'.
-- Failure rate (%) = failed_count / finished_count * 100.
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
FROM payments
GROUP BY
    paymentMethod,
    device
ORDER BY
    failure_rate_pct DESC,
    paymentMethod,
    device;
