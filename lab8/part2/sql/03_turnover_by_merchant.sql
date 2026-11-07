-- Query 3: Turnover by merchant and currency, successful payments only
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
FROM payments
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
