terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.5"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name      = var.project_name
  full_name = "${var.project_name}-${var.aws_region}"
}

# ---------- S3 bucket for artifacts ----------
resource "aws_s3_bucket" "artifacts" {
  bucket = var.s3_bucket_name
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------- DynamoDB table ----------
resource "aws_dynamodb_table" "runs" {
  name         = "Runs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_id"

  attribute {
    name = "run_id"
    type = "S"
  }
}

# ---------- ECR repo ----------
resource "aws_ecr_repository" "runner" {
  name                 = var.ecr_repo_name
  image_tag_mutability = "MUTABLE"
}

# Image URL the ECS task will use (push your image separately)
locals {
  runner_image_url = "${aws_ecr_repository.runner.repository_url}:${var.runner_image_tag}"
}

# ---------- SSM parameters for Kaggle creds ----------
resource "aws_ssm_parameter" "kaggle_username" {
  name        = "/kaggle/username"
  description = "Kaggle username"
  type        = "SecureString"
  value       = var.kaggle_username
}

resource "aws_ssm_parameter" "kaggle_key" {
  name        = "/kaggle/key"
  description = "Kaggle API key"
  type        = "SecureString"
  value       = var.kaggle_key
}

# ---------- SSM parameter for OpenAI ----------
data "aws_ssm_parameter" "openai_api_key" {
  name = "/openai/api_key"
}

# ---------- CloudWatch log groups ----------
resource "aws_cloudwatch_log_group" "lambdas" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/aws/ecs/${local.name}"
  retention_in_days = 14
}

# ---------- Networking (default VPC + subnets) ----------
data "aws_vpc" "default" { default = true }

data "aws_subnets" "default_vpc_subnets" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ---------- IAM Roles ----------
# Lambda roles
resource "aws_iam_role" "lambda_start_role" {
  name               = "${local.name}-lambda-start-role"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
}

resource "aws_iam_role_policy" "lambda_start_logs" {
  name   = "${local.name}-lambda-start-logs"
  role   = aws_iam_role.lambda_start_role.id
  policy = data.aws_iam_policy_document.lambda_logs.json
}

resource "aws_iam_role_policy" "lambda_start_perm" {
  name   = "${local.name}-lambda-start-perm"
  role   = aws_iam_role.lambda_start_role.id
  policy = data.aws_iam_policy_document.lambda_start_permissions.json
}

resource "aws_iam_role" "lambda_plan_role" {
  name               = "${local.name}-lambda-plan-role"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
}
resource "aws_iam_role_policy" "lambda_plan_logs" {
  name   = "${local.name}-lambda-plan-logs"
  role   = aws_iam_role.lambda_plan_role.id
  policy = data.aws_iam_policy_document.lambda_logs.json
}
resource "aws_iam_role_policy" "lambda_plan_perm" {
  name   = "${local.name}-lambda-plan-perm"
  role   = aws_iam_role.lambda_plan_role.id
  policy = data.aws_iam_policy_document.lambda_plan_permissions.json
}

resource "aws_iam_role" "lambda_validate_role" {
  name               = "${local.name}-lambda-validate-role"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
}
resource "aws_iam_role_policy" "lambda_validate_logs" {
  name   = "${local.name}-lambda-validate-logs"
  role   = aws_iam_role.lambda_validate_role.id
  policy = data.aws_iam_policy_document.lambda_logs.json
}
resource "aws_iam_role_policy" "lambda_validate_perm" {
  name   = "${local.name}-lambda-validate-perm"
  role   = aws_iam_role.lambda_validate_role.id
  policy = data.aws_iam_policy_document.lambda_validate_permissions.json
}

resource "aws_iam_role" "lambda_mark_role" {
  name               = "${local.name}-lambda-mark-role"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
}
resource "aws_iam_role_policy" "lambda_mark_logs" {
  name   = "${local.name}-lambda-mark-logs"
  role   = aws_iam_role.lambda_mark_role.id
  policy = data.aws_iam_policy_document.lambda_logs.json
}
resource "aws_iam_role_policy" "lambda_mark_perm" {
  name   = "${local.name}-lambda-mark-perm"
  role   = aws_iam_role.lambda_mark_role.id
  policy = data.aws_iam_policy_document.lambda_mark_permissions.json
}

# Step Functions role
resource "aws_iam_role" "sfn_role" {
  name               = "${local.name}-sfn-role"
  assume_role_policy = data.aws_iam_policy_document.assume_states.json
}
resource "aws_iam_role_policy" "sfn_perm" {
  name   = "${local.name}-sfn-perm"
  role   = aws_iam_role.sfn_role.id
  policy = data.aws_iam_policy_document.sfn_permissions.json
}

# ECS roles
resource "aws_iam_role" "ecs_task_execution_role" {
  name               = "${local.name}-ecs-execution-role"
  assume_role_policy = data.aws_iam_policy_document.assume_ecs_tasks.json
}
resource "aws_iam_role_policy_attachment" "ecs_exec_attach" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name               = "${local.name}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.assume_ecs_tasks.json
}
resource "aws_iam_role_policy" "ecs_task_role_perm" {
  name   = "${local.name}-ecs-task-role-perm"
  role   = aws_iam_role.ecs_task_role.id
  policy = data.aws_iam_policy_document.ecs_task_role_permissions.json
}

# ---------- ECS Cluster ----------
resource "aws_ecs_cluster" "this" {
  name = "${local.name}-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ---------- ECS Task Definition (runner) ----------
resource "aws_ecs_task_definition" "runner" {
  family                   = "${local.name}-runner"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  # Explicit runtime platform to match Fargate default
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  # Create before destroy ensures Terraform re-registers safely
  lifecycle {
    create_before_destroy = true
  }

  # Always keep the latest revision automatically
  track_latest = true

  container_definitions = jsonencode([
    {
      name      = "runner"
      image     = local.runner_image_url
      essential = true
      command   = ["python", "/app/runner_main.py"]

      environment = [
        { name = "S3_BUCKET", value = aws_s3_bucket.artifacts.bucket },
        { name = "DDB_TABLE", value = aws_dynamodb_table.runs.name }
      ]

      secrets = [
        { name = "KAGGLE_USERNAME", valueFrom = aws_ssm_parameter.kaggle_username.arn },
        { name = "KAGGLE_KEY",      valueFrom = aws_ssm_parameter.kaggle_key.arn },
        { name = "OPENAI_API_KEY",  valueFrom = data.aws_ssm_parameter.openai_api_key.arn }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "runner"
        }
      }
    }
  ])
}


# ---------- Lambda Packaging (archive_file) ----------
data "archive_file" "start_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/lambda_start_run.py"
  output_path = "${path.module}/build/start_run.zip"
}
data "archive_file" "plan_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/lambda_plan.py"
  output_path = "${path.module}/build/plan.zip"
}
data "archive_file" "validate_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/lambda_validate_output.py"
  output_path = "${path.module}/build/validate_output.zip"
}
data "archive_file" "mark_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/lambda_mark_succeeded.py"
  output_path = "${path.module}/build/mark_succeeded.zip"
}

# ---------- Lambda Functions ----------
resource "aws_lambda_function" "start_run" {
  function_name = "${local.name}-StartRun"
  role          = aws_iam_role.lambda_start_role.arn
  runtime       = "python3.11"
  handler       = "lambda_start_run.handler"
  filename      = data.archive_file.start_zip.output_path
  environment {
    variables = {
      SFN_ARN   = aws_sfn_state_machine.kagent.arn
      DDB_TABLE = aws_dynamodb_table.runs.name
    }
  }
}

resource "aws_lambda_function" "plan" {
  function_name = "${local.name}-Plan"
  role          = aws_iam_role.lambda_plan_role.arn
  runtime       = "python3.11"
  handler       = "lambda_plan.handler"
  filename      = data.archive_file.plan_zip.output_path
  environment {
    variables = {
      DDB_TABLE = aws_dynamodb_table.runs.name
    }
  }
}

resource "aws_lambda_function" "validate_output" {
  function_name = "${local.name}-ValidateOutput"
  role          = aws_iam_role.lambda_validate_role.arn
  runtime       = "python3.11"
  handler       = "lambda_validate_output.handler"
  filename      = data.archive_file.validate_zip.output_path
  environment {
    variables = {
      S3_BUCKET = aws_s3_bucket.artifacts.bucket
    }
  }
}

resource "aws_lambda_function" "mark_succeeded" {
  function_name = "${local.name}-MarkSucceeded"
  role          = aws_iam_role.lambda_mark_role.arn
  runtime       = "python3.11"
  handler       = "lambda_mark_succeeded.handler"
  filename      = data.archive_file.mark_zip.output_path
  environment {
    variables = {
      DDB_TABLE  = aws_dynamodb_table.runs.name
      S3_BUCKET  = aws_s3_bucket.artifacts.bucket
      SES_FROM   = var.ses_from_email
      SES_REGION = var.aws_region
    }
  }
}

# ---------- Step Functions State Machine ----------
resource "aws_sfn_state_machine" "kagent" {
  name     = "${local.name}-workflow"
  role_arn = aws_iam_role.sfn_role.arn

  definition = jsonencode({
    Comment = "Kaggle Agent Orchestration"
    StartAt = "Plan"
    States = {
      Plan = {
        Type       = "Task"
        Resource   = aws_lambda_function.plan.arn
        ResultPath = "$"
        Next       = "RunTraining"
      }
      RunTraining = {
        Type     = "Task"
        Resource = "arn:aws:states:::ecs:runTask.sync"
        Parameters = {
          LaunchType = "FARGATE"
          Cluster    = aws_ecs_cluster.this.arn
          TaskDefinition = aws_ecs_task_definition.runner.arn
          NetworkConfiguration = {
            AwsvpcConfiguration = {
              Subnets        = data.aws_subnets.default_vpc_subnets.ids
              AssignPublicIp = "ENABLED"
            }
          }
          Overrides = {
            ContainerOverrides = [{
              Name = "runner"
              Environment = [
                { Name = "RUN_ID",  "Value.$" = "$.run_id" },
                { Name = "URL",     "Value.$" = "$.url" },
                { Name = "EMAIL",   "Value.$" = "$.email" }
              ]
            }]
          }
        }
        ResultPath = "$.ecs_result"
        Next = "ValidateOutput"
      },
      ValidateOutput = {
        Type       = "Task"
        Resource   = aws_lambda_function.validate_output.arn
        InputPath  = "$"
        ResultPath = "$.validation"
        Next       = "MarkSucceeded"
      }

      ValidateOutput = {
        Type       = "Task"
        Resource   = aws_lambda_function.validate_output.arn
        ResultPath = "$"
        Next       = "MarkSucceeded"
      }
      MarkSucceeded = {
        Type     = "Task"
        Resource = aws_lambda_function.mark_succeeded.arn
        End      = true
      }
    }
  })
}


# ---------- API Gateway (HTTP API) ----------
resource "aws_apigatewayv2_api" "http" {
  name          = "${local.name}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "start_integration" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.start_run.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "run_route" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /run"
  target    = "integrations/${aws_apigatewayv2_integration.start_integration.id}"
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "prod"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw_invoke_start" {
  statement_id  = "AllowAPIGWInvokeStart"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.start_run.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*/run"
}
