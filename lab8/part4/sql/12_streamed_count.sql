SELECT count(*) AS rows_in_athena, count(DISTINCT invoiceId) AS invoices
FROM streamed_events
