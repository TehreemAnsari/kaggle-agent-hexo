# Lambda assume role policy
data "aws_iam_policy_document" "assume_lambda" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# Step Functions assume role policy
data "aws_iam_policy_document" "assume_states" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

# ECS Tasks assume role policy
data "aws_iam_policy_document" "assume_ecs_tasks" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Lambda basic logging permissions
data "aws_iam_policy_document" "lambda_logs" {
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["*"]
  }
}

# StartRun Lambda permissions (write to DDB + trigger Step Functions)
data "aws_iam_policy_document" "lambda_start_permissions" {
  statement {
    actions   = ["dynamodb:PutItem"]
    resources = [aws_dynamodb_table.runs.arn]
  }
  statement {
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.kagent.arn]
  }
}

# Plan Lambda permissions
data "aws_iam_policy_document" "lambda_plan_permissions" {
  statement {
    actions   = ["dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.runs.arn]
  }
}

# ValidateOutput Lambda permissions
data "aws_iam_policy_document" "lambda_validate_permissions" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/runs/*"]
  }
}

# MarkSucceeded Lambda permissions
data "aws_iam_policy_document" "lambda_mark_permissions" {
  statement {
    actions   = ["dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.runs.arn]
  }

  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/runs/*"]
  }

  statement {
    actions   = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = ["*"]
  }
}

# Step Functions permissions (invoke Lambdas, run ECS task, pass roles)
data "aws_iam_policy_document" "sfn_permissions" {
  # Allow invoking Lambdas
  statement {
    actions = ["lambda:InvokeFunction"]
    resources = [
      aws_lambda_function.plan.arn,
      aws_lambda_function.validate_output.arn,
      aws_lambda_function.mark_succeeded.arn
    ]
  }

  # Allow running ECS Tasks
  statement {
    actions   = ["ecs:RunTask", "ecs:DescribeTasks"]
    resources = [aws_ecs_task_definition.runner.arn]
  }

  # Allow passing roles to ECS
  statement {
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.ecs_task_execution_role.arn,
      aws_iam_role.ecs_task_role.arn
    ]
  }

  # Allow Step Functions to create CloudWatch Logs and managed rules
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "events:PutRule",
      "events:PutTargets",
      "events:DescribeRule"
    ]
    resources = ["*"]
  }
}


# ECS Task Role permissions (S3 put, DDB update, SSM params, CloudWatch logs)
data "aws_iam_policy_document" "ecs_task_role_permissions" {
  statement {
    actions   = ["s3:PutObject", "s3:PutObjectAcl"]
    resources = ["${aws_s3_bucket.artifacts.arn}/runs/*"]
  }

  statement {
    actions   = ["dynamodb:UpdateItem", "dynamodb:GetItem"]
    resources = [aws_dynamodb_table.runs.arn]
  }

  statement {
    actions = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParameterHistory"]
    resources = [
      aws_ssm_parameter.kaggle_username.arn,
      aws_ssm_parameter.kaggle_key.arn,
      data.aws_ssm_parameter.openai_api_key.arn
    ]
  }

  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["*"]
  }
}

# ECS Execution Role needs to pull SSM parameters (Kaggle creds)
resource "aws_iam_role_policy" "ecs_exec_ssm" {
  name = "${local.name}-ecs-exec-ssm"
  role = aws_iam_role.ecs_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParameterHistory"
        ]
        Resource = [
          aws_ssm_parameter.kaggle_username.arn,
          aws_ssm_parameter.kaggle_key.arn,
          data.aws_ssm_parameter.openai_api_key.arn
        ]
      }
    ]
  })
}

