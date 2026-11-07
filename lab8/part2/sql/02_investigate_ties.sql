SELECT
    invoiceId,
    modifiedDate,
    count(*) AS distinct_events_same_moddate,
    count(distinct status) AS distinct_statuses
FROM (
    SELECT DISTINCT invoiceId, status, modifiedDate, receivedAt
    FROM payment_events
)
GROUP BY invoiceId, modifiedDate
HAVING count(*) > 1
LIMIT 20;
