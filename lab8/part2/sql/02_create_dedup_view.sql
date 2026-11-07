CREATE OR REPLACE VIEW payments AS
WITH distinct_events AS (
    -- Step 1: Remove exact duplicate events
    SELECT DISTINCT
        invoiceId,
        amount,
        ccy,
        reference,
        createdDate,
        merchantId,
        merchantName,
        mcc,
        customerId,
        paymentMethod,
        device,
        status,
        modifiedDate,
        finalAmount,
        failureReason,
        receivedAt,
        dt
    FROM payment_events
),
ranked_events AS (
    -- Step 2: Select latest event per invoiceId with status and receivedAt tie-breakers
    SELECT
        invoiceId,
        amount,
        ccy,
        reference,
        createdDate,
        merchantId,
        merchantName,
        mcc,
        customerId,
        paymentMethod,
        device,
        status,
        modifiedDate,
        finalAmount,
        failureReason,
        receivedAt,
        dt,
        ROW_NUMBER() OVER (
            PARTITION BY invoiceId
            ORDER BY
                from_iso8601_timestamp(modifiedDate) DESC,
                CASE status
                    WHEN 'success' THEN 3
                    WHEN 'failure' THEN 3
                    WHEN 'processing' THEN 2
                    WHEN 'created' THEN 1
                    ELSE 0
                END DESC,
                from_iso8601_timestamp(receivedAt) DESC
        ) AS rn
    FROM distinct_events
)
SELECT
    invoiceId,
    amount,
    ccy,
    reference,
    createdDate,
    merchantId,
    merchantName,
    mcc,
    customerId,
    paymentMethod,
    device,
    status,
    modifiedDate,
    finalAmount,
    failureReason,
    receivedAt,
    dt
FROM ranked_events
WHERE rn = 1;
