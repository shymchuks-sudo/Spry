resource "aws_iam_role" "parser" {
  name = "spry-ai-ParserRole-7W5lBfC2gqcC"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "parser_logs" {
  role       = aws_iam_role.parser.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "parser_bedrock" {
  name = "InvokeBedrockModel"
  role = aws_iam_role.parser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["bedrock:InvokeModel"]
      Resource = "*"
    }]
  })
}

resource "aws_cloudwatch_log_group" "parser" {
  name              = "/aws/lambda/${var.project_name}-agenda-parser"
  retention_in_days = 14
  tags = { Purpose  = "agenda-parser-logs" }
}

resource "aws_lambda_function" "parser" {
  function_name = "${var.project_name}-agenda-parser"
  package_type  = "Image"
  image_uri     = var.parser_image_uri
  role          = aws_iam_role.parser.arn
  timeout       = 30
  memory_size   = 512

  image_config {
    command = ["app.ai.agenda_lambda.handler"]
  }

  environment {
    variables = {
      PARSER_MODEL   = var.parser_model
      USER_POOL_ID   = aws_cognito_user_pool.main.id
      APP_CLIENT_ID  = aws_cognito_user_pool_client.app.id
      COGNITO_REGION = var.region
    }
  }

  depends_on = [aws_cloudwatch_log_group.parser]
}

resource "aws_lambda_function_url" "parser" {
  function_name      = aws_lambda_function.parser.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = var.site_origins
    allow_methods = ["POST"]
    allow_headers = ["content-type", "authorization"]
    max_age       = 3600
  }
}

resource "aws_lambda_permission" "parser_url" {
  statement_id           = "spry-ai-ParserUrlPermission-4dZAEqo14m0H"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.parser.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "parser_invoke" {
  statement_id             = "spry-ai-ParserInvokePermission-stfWPw4cbdTo"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.parser.function_name
  principal                = "*"
  invoked_via_function_url = true
}
