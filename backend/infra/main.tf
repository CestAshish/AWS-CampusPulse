terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  backend "s3" {
    bucket = "campuspulse-tfstate-2026" # Ensure this matches Rayyan's bucket name
    key    = "state/terraform.tfstate"
    region = "eu-north-1"
  }
}

provider "aws" {
  region = "eu-north-1"
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

data "aws_security_group" "default" {
  vpc_id = data.aws_vpc.campuspulse.id
  name   = "default"
}
