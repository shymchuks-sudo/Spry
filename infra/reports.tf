data "aws_caller_identity" "current" {}

# ---------------- S3 reports bucket ----------------
resource "aws_s3_bucket" "reports" {
  bucket = "${var.project_name}-reports-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    id     = "DeleteOldReports"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket_notification" "reports" {
  bucket = aws_s3_bucket.reports.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.mailer.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "reports/"
    filter_suffix       = ".csv"
  }

  depends_on = [aws_lambda_permission.mailer_s3]
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.route_table_ids
}

# ---------------- SQS ----------------
resource "aws_sqs_queue" "dlq" {
  name             = "${var.project_name}-report-requests-dlq"
  max_message_size = 1048576
}

resource "aws_sqs_queue" "reports" {
  name                       = "${var.project_name}-report-requests"
  visibility_timeout_seconds = 360
  max_message_size           = 1048576

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })
}

# ---------------- Report builder (in the VPC) ----------------
resource "aws_iam_role" "builder" {
  name = "spry-reports-ReportBuilderRole-akJdMxZdFxF5"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "builder_vpc" {
  role       = aws_iam_role.builder.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "builder" {
  name = "BuilderPermissions"
  role = aws_iam_role.builder.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.reports.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.reports.arn
      }
    ]
  })
}

resource "aws_lambda_function" "builder" {
  function_name = "${var.project_name}-report-builder"
  package_type  = "Image"
  image_uri     = var.backend_image_uri
  role          = aws_iam_role.builder.arn
  timeout       = 60
  memory_size   = 512

  image_config {
    command = ["app.reports.lambda_handler.handler"]
  }

  lifecycle {
    ignore_changes = [environment]
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.security_group_id]
  }
}

resource "aws_lambda_event_source_mapping" "builder_sqs" {
  event_source_arn = aws_sqs_queue.reports.arn
  function_name    = aws_lambda_function.builder.arn
  batch_size       = 1
}

# ---------------- Weekly schedule ----------------
resource "aws_iam_role" "scheduler" {
  name = "spry-reports-SchedulerRole-GJaeeAgyfckL"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  name = "SendToSQS"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sqs:SendMessage"
      Resource = aws_sqs_queue.reports.arn
    }]
  })
}

resource "aws_scheduler_schedule" "weekly" {
  name                         = "${var.project_name}-weekly-report-schedule"
  schedule_expression          = "cron(0 7 ? * MON *)"
  schedule_expression_timezone = "Europe/Kyiv"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sqs_queue.reports.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = "{\"week\": null, \"source\": \"schedule\"}"
  }
}

# ---------------- Report mailer (outside the VPC) ----------------
resource "aws_iam_role" "mailer" {
  name = "spry-reports-ReportMailerRole-RpX6KJRYseVH"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "mailer_logs" {
  role       = aws_iam_role.mailer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "mailer" {
  name = "MailerPermissions"
  role = aws_iam_role.mailer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.reports.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "ses:SendRawEmail"
        Resource = "*"
      }
    ]
  })
}

data "archive_file" "mailer" {
  type        = "zip"
  source_file = "${path.module}/mailer/index.py"
  output_path = "${path.module}/.build/mailer.zip"
}

resource "aws_lambda_function" "mailer" {
  function_name    = "${var.project_name}-report-mailer"
  runtime          = "python3.11"
  handler          = "index.handler"
  role             = aws_iam_role.mailer.arn
  timeout          = 30
  filename         = data.archive_file.mailer.output_path
  source_code_hash = data.archive_file.mailer.output_base64sha256

  environment {
    variables = {
      RECIPIENT_EMAIL = var.recipient_email
      SENDER_EMAIL    = var.recipient_email
    }
  }
}

resource "aws_lambda_permission" "mailer_s3" {
  statement_id   = "spry-reports-MailerLambdaPermission-CIJda8rfC94Z"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.mailer.function_name
  principal      = "s3.amazonaws.com"
  source_account = data.aws_caller_identity.current.account_id
  source_arn     = aws_s3_bucket.reports.arn
}


