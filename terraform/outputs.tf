output "ecr_repository_url" {
  description = "ECR repository URL for the QQ algorithm image"
  value       = aws_ecr_repository.qq.repository_url
}

output "batch_job_definition_arn" {
  description = "ARN of the AWS Batch job definition"
  value       = aws_batch_job_definition.qq.arn
}
