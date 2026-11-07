-- Query 7: Create Parquet table via CTAS from deduplicated payments view
CREATE TABLE payments_curated
WITH (
    format = 'PARQUET',
    parquet_compression = 'SNAPPY',
    external_location = 's3://lab8-payments-594559484590/curated/payments/',
    partitioned_by = ARRAY['dt']
) AS
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
FROM payments;
