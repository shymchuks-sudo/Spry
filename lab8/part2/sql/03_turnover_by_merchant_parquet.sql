-- Query 3 on Curated Parquet table
SELECT
    merchantId,
    merchantName,
    CASE ccy
        WHEN 980 THEN 'UAH'
        WHEN 840 THEN 'USD'
        WHEN 978 THEN 'EUR'
        ELSE cast(ccy AS varchar)
    END AS currency,
    count(*) AS payment_count,
    CAST(sum(finalAmount) / 100.0 AS DECIMAL(18, 2)) AS total_turnover
FROM payments_curated
WHERE status = 'success'
GROUP BY
    merchantId,
    merchantName,
    CASE ccy
        WHEN 980 THEN 'UAH'
        WHEN 840 THEN 'USD'
        WHEN 978 THEN 'EUR'
        ELSE cast(ccy AS varchar)
    END
ORDER BY
    merchantId,
    currency;
