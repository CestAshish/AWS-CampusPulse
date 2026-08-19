resource "aws_iam_role" "lambda_exec" {
  name = "campuspulse_lambda_exec_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "campuspulse_lambda_policy"
  role = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      { Effect = "Allow", Action = ["logs:*"], Resource = "arn:aws:logs:*:*:*" },
      { 
        Effect = "Allow", 
        Action = ["dynamodb:PutItem", "dynamodb:Query", "dynamodb:Scan"], 
        Resource = [aws_dynamodb_table.events.arn, "${aws_dynamodb_table.events.arn}/index/*"]
      },
      { Effect = "Allow", Action = ["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DeleteNetworkInterface"], Resource = "*" }
    ]
  })
}
