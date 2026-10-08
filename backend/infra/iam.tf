resource "aws_iam_role" "lambda_exec" {
  name = "campuspulse_lambda_exec_role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

# Least privilege: write logs to the two function log groups, put/query one
# table, and manage the ENIs needed to run inside the VPC. No Scan, no Delete.
resource "aws_iam_role_policy" "lambda_policy" {
  name = "campuspulse_lambda_policy"
  role = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid    = "WriteOwnLogs",
        Effect = "Allow",
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"],
        Resource = [
          "${aws_cloudwatch_log_group.ingest.arn}:*",
          "${aws_cloudwatch_log_group.stats.arn}:*"
        ]
      },
      {
        Sid      = "EventsTable",
        Effect   = "Allow",
        Action   = ["dynamodb:PutItem", "dynamodb:Query"],
        Resource = [aws_dynamodb_table.events.arn, "${aws_dynamodb_table.events.arn}/index/*"]
      },
      {
        Sid    = "VpcNetworkInterfaces",
        Effect = "Allow",
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeSubnets",
          "ec2:DeleteNetworkInterface",
          "ec2:AssignPrivateIpAddresses",
          "ec2:UnassignPrivateIpAddresses"
        ],
        Resource = "*"
      }
    ]
  })
}
