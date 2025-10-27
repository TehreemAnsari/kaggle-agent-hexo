output "api_base_url" {
  value       = "${aws_apigatewayv2_api.http.api_endpoint}/${aws_apigatewayv2_stage.prod.name}"
  description = "HTTP API base URL"
}

output "state_machine_arn" {
  value       = aws_sfn_state_machine.kagent.arn
  description = "Step Functions state machine ARN"
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "dynamodb_table" {
  value = aws_dynamodb_table.runs.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.runner.repository_url
}
