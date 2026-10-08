terraform {
  required_version = ">= 1.5"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }
  backend "s3" {
    bucket = "campuspulse-tfstate-2026" # Ensure this matches Rayyan's bucket name
    key    = "state/terraform.tfstate"
    region = "eu-north-1"
  }
}

provider "aws" {
  region = "eu-north-1"
  default_tags {
    tags = { Project = "CampusPulse", ManagedBy = "Terraform" }
  }
}

variable "alert_email" {
  description = "Email that receives CloudWatch alarm and budget notifications"
  type        = string
  default     = "ashish.singh@epita.fr"
}

variable "lambda_in_vpc" {
  description = "Run the Lambdas in the private subnets (DynamoDB reached through the VPC gateway endpoint)"
  type        = bool
  default     = true
}

variable "manage_dynamodb_endpoint" {
  description = "Create the DynamoDB gateway endpoint here instead of using the one that already exists in the VPC"
  type        = bool
  default     = false
}

variable "monthly_budget_usd" {
  description = "Monthly cost budget; alerts at 80% actual and 100% forecasted"
  type        = string
  default     = "5.0"
}

data "aws_vpc" "campuspulse" {
  filter {
    name   = "tag:Name"
    values = ["CampusPulse-VPC"]
  }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.campuspulse.id]
  }
  filter {
    name   = "tag:Name"
    values = ["*private*"]
  }
}

# High availability: the console-built VPC has one private subnet (10.0.2.0/24,
# eu-north-1a). A second private subnet in another availability zone lets the
# Lambdas keep running if eu-north-1a fails. It shares the VPC's main route
# table, which already routes DynamoDB traffic to the gateway endpoint.
resource "aws_subnet" "private_b" {
  vpc_id                  = data.aws_vpc.campuspulse.id
  cidr_block              = "10.0.3.0/24"
  availability_zone       = "eu-north-1b"
  map_public_ip_on_launch = false
  tags                    = { Name = "private-subnet-b" }
}

resource "aws_route_table_association" "private_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = one(data.aws_route_tables.main.ids)
}

# --- Private networking for the Lambdas ---------------------------------------
# The private subnets have no NAT gateway (it is not Free Tier), so the only
# outbound path is the free DynamoDB gateway endpoint. Metrics are emitted as
# structured logs (Embedded Metric Format), which the Lambda service ships to
# CloudWatch without needing a network route from the VPC.

data "aws_prefix_list" "dynamodb" {
  name = "com.amazonaws.eu-north-1.dynamodb"
}

data "aws_route_tables" "private_explicit" {
  vpc_id = data.aws_vpc.campuspulse.id
  filter {
    name   = "association.subnet-id"
    values = data.aws_subnets.private.ids
  }
}

data "aws_route_tables" "main" {
  vpc_id = data.aws_vpc.campuspulse.id
  filter {
    name   = "association.main"
    values = ["true"]
  }
}

data "aws_vpc_endpoint" "dynamodb" {
  count        = var.lambda_in_vpc && !var.manage_dynamodb_endpoint ? 1 : 0
  vpc_id       = data.aws_vpc.campuspulse.id
  service_name = "com.amazonaws.eu-north-1.dynamodb"
}

resource "aws_vpc_endpoint" "dynamodb" {
  count             = var.lambda_in_vpc && var.manage_dynamodb_endpoint ? 1 : 0
  vpc_id            = data.aws_vpc.campuspulse.id
  service_name      = "com.amazonaws.eu-north-1.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = local.private_route_table_ids
  tags              = { Name = "campuspulse-dynamodb-endpoint" }
}

locals {
  # Subnets without an explicit association use the VPC's main route table.
  private_route_table_ids = distinct(concat(
    data.aws_route_tables.private_explicit.ids,
    length(data.aws_route_tables.private_explicit.ids) < length(data.aws_subnets.private.ids) ? data.aws_route_tables.main.ids : []
  ))
  endpoint_route_table_ids = var.manage_dynamodb_endpoint ? local.private_route_table_ids : try(tolist(data.aws_vpc_endpoint.dynamodb[0].route_table_ids), [])
}

resource "aws_security_group" "lambda" {
  count       = var.lambda_in_vpc ? 1 : 0
  name        = "campuspulse-lambda-sg"
  description = "CampusPulse Lambdas: no inbound, HTTPS out to DynamoDB only"
  vpc_id      = data.aws_vpc.campuspulse.id

  egress {
    description     = "DynamoDB through the gateway endpoint"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    prefix_list_ids = [data.aws_prefix_list.dynamodb.id]
  }

  tags = { Name = "campuspulse-lambda-sg" }
}
