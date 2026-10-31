output "user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.app.id
}

output "cognito_auth_domain" {
  value = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com"
}

output "parser_function_url" {
  value = aws_lambda_function_url.parser.function_url
}

output "reports_bucket" {
  value = aws_s3_bucket.reports.bucket
}

output "reports_queue_url" {
  value = aws_sqs_queue.reports.url
}
