-- Check if duplicates differ by receivedAt or other columns
SELECT
    invoiceId,
    status,
    modifiedDate,
    count(*) AS occurrences,
    count(distinct receivedAt) AS distinct_received_at,
    min(receivedAt) AS min_received_at,
    max(receivedAt) AS max_received_at
FROM payment_events
GROUP BY invoiceId, status, modifiedDate
HAVING count(*) > 1
LIMIT 20;
