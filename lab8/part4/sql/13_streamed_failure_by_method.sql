SELECT paymentMethod,
       count_if(status IN ('success', 'failure')) AS final_events,
       count_if(status = 'failure') AS failures,
       round(100.0 * count_if(status = 'failure') / count_if(status IN ('success', 'failure')), 1) AS failure_pct
FROM streamed_events
GROUP BY paymentMethod
ORDER BY failure_pct DESC
