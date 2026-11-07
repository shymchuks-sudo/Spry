CREATE EXTERNAL TABLE IF NOT EXISTS payment_events (
    invoiceId string,
    amount bigint,
    ccy int,
    reference string,
    createdDate string,
    merchantId string,
    merchantName string,
    mcc int,
    customerId string,
    paymentMethod string,
    device string,
    status string,
    modifiedDate string,
    finalAmount bigint,
    failureReason string,
    receivedAt string
)
PARTITIONED BY (
    dt string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
    'ignore.malformed.json' = 'FALSE'
)
LOCATION 's3://lab8-payments-594559484590/payments/'
TBLPROPERTIES (
    'has_encrypted_data'='false'
);
