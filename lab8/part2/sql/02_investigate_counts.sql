SELECT
    (SELECT count(*) FROM payment_events) AS total_events,
    (SELECT count(distinct invoiceId) FROM payment_events) AS unique_invoices,
    (SELECT count(*) FROM (
        SELECT DISTINCT invoiceId, amount, ccy, reference, createdDate, merchantId, merchantName, mcc, customerId, paymentMethod, device, status, modifiedDate, finalAmount, failureReason, receivedAt, dt
        FROM payment_events
    )) AS distinct_all_columns,
    (SELECT count(*) FROM (
        SELECT DISTINCT invoiceId, status, modifiedDate
        FROM payment_events
    )) AS distinct_invoice_status_moddate,
    (SELECT count(*) FROM (
        SELECT invoiceId, status, modifiedDate
        FROM payment_events
        GROUP BY invoiceId, status, modifiedDate
        HAVING count(distinct receivedAt) > 1
    )) AS diff_received_at_count;
