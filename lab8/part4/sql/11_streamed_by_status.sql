SELECT dt, status, count(*) AS events
FROM streamed_events
GROUP BY dt, status
ORDER BY dt, status
