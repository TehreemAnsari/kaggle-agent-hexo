variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Project name/prefix"
  type        = string
  default     = "kaggle-agent"
}

variable "s3_bucket_name" {
  description = "S3 bucket for artifacts"
  type        = string
  default     = "kagent-artifacts"
}

variable "ses_from_email" {
  description = "Verified SES sender email (must be verified in SES)"
  type        = string
}

variable "ecr_repo_name" {
  description = "ECR repository name for runner image"
  type        = string
  default     = "kaggle-runner"
}

variable "runner_image_tag" {
  description = "Tag for runner image in ECR"
  type        = string
  default     = "10"
}

variable "kaggle_username" {
  description = "Kaggle username (will be stored in SSM Parameter Store)"
  type        = string
  sensitive   = true
}

variable "kaggle_key" {
  description = "Kaggle API key (will be stored in SSM Parameter Store)"
  type        = string
  sensitive   = true
}
