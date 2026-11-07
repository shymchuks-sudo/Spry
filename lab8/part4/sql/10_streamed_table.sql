CREATE EXTERNAL TABLE IF NOT EXISTS lab8.streamed_events (
  invoiceId string,
  status string,
  failureReason string,
  amount bigint,
  finalAmount bigint,
  ccy string,
  reference string,
  createdDate string,
  modifiedDate string,
  receivedAt string,
  merchantId string,
  merchantName string,
  mcc string,
  customerId string,
  paymentMethod string,
  device string
)
PARTITIONED BY (dt string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://lab8-payments-594559484590/streamed/'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.dt.type' = 'date',
  'projection.dt.format' = 'yyyy-MM-dd',
  'projection.dt.range' = '2026-11-01,NOW',
  'projection.dt.interval' = '1',
  'projection.dt.interval.unit' = 'DAYS',
  'storage.location.template' = 's3://lab8-payments-594559484590/streamed/dt=${dt}/'
)
