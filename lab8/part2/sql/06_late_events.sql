-- Query 6: Late events analysis (raw events and deduplicated events)
SELECT
    'raw_events' AS dataset_type,
    count(*) AS total_events,
    count_if(date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) > 60) AS late_over_60s,
    round(cast(count_if(date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) > 60) AS double) / count(*) * 100.0, 4) AS late_over_60s_pct,
    count_if(date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) > 3600) AS late_over_1h,
    round(cast(count_if(date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) > 3600) AS double) / count(*) * 100.0, 4) AS late_over_1h_pct
FROM payment_events

UNION ALL

SELECT
    'deduplicated_events' AS dataset_type,
    count(*) AS total_events,
    count_if(date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) > 60) AS late_over_60s,
    round(cast(count_if(date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) > 60) AS double) / count(*) * 100.0, 4) AS late_over_60s_pct,
    count_if(date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) > 3600) AS late_over_1h,
    round(cast(count_if(date_diff('second', from_iso8601_timestamp(modifiedDate), from_iso8601_timestamp(receivedAt)) > 3600) AS double) / count(*) * 100.0, 4) AS late_over_1h_pct
FROM (
    SELECT DISTINCT invoiceId, status, modifiedDate, receivedAt
    FROM payment_events
);
