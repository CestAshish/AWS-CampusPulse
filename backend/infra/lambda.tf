data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_lambda_function" "ingest" {
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  function_name    = "CampusPulse-Ingest"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "ingest_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 10

  environment {
    variables = { TABLE_NAME = aws_dynamodb_table.events.name }
  }
}

resource "aws_lambda_function" "stats" {
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  function_name    = "CampusPulse-Stats"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "stats_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 10

  environment {
    variables = { TABLE_NAME = aws_dynamodb_table.events.name }
  }
}
