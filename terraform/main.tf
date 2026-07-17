terraform {
  required_version = ">= 1.3"
  backend "s3" {}
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = var.region
  profile = var.profile
}

# -----------------------------------------------------------------------
# ECR repository
# -----------------------------------------------------------------------
resource "aws_ecr_repository" "qq" {
  name                 = "${var.prefix}-qq"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name    = "${var.prefix}-qq"
    Project = "SWOT-Confluence"
    Module  = "qq"
  }
}

# -----------------------------------------------------------------------
# AWS Batch job definition
# -----------------------------------------------------------------------
resource "aws_batch_job_definition" "qq" {
  name = "${var.prefix}-qq"
  type = "container"

  container_properties = jsonencode({
    image  = "${var.registry}/${var.repository}:latest"
    memory = var.memory
    vcpus  = var.vcpus

    command = [
      "/mnt/data/input/reaches.json",
      "--input_dir",  "/mnt/data/input",
      "--output_dir", "/mnt/data/flpe/qq",
      "--mode",       "RUN"
    ]

    environment = [
      {
        name  = "AWS_BATCH_JOB_ARRAY_INDEX"
        value = "Ref::AWS_BATCH_JOB_ARRAY_INDEX"
      }
    ]

    mountPoints = [
      {
        containerPath = "/mnt/data"
        readOnly      = false
        sourceVolume  = "data"
      }
    ]

    volumes = [
      {
        name = "data"
        efsVolumeConfiguration = {
          fileSystemId = data.aws_efs_file_system.confluence.id
        }
      }
    ]

    jobRoleArn = data.aws_iam_role.batch_execution.arn
  })

  tags = {
    Name    = "${var.prefix}-qq"
    Project = "SWOT-Confluence"
    Module  = "qq"
  }
}

# -----------------------------------------------------------------------
# Data sources — reference shared Confluence infrastructure
# -----------------------------------------------------------------------
data "aws_efs_file_system" "confluence" {
  tags = {
    Name = "${var.prefix}-efs"
  }
}

data "aws_iam_role" "batch_execution" {
  name = "${var.prefix}-batch-job-role"
}
