variable "prefix" {
  description = "Resource name prefix (e.g. confluence-dev)"
  type        = string
}

variable "registry" {
  description = "AWS ECR registry URI"
  type        = string
}

variable "repository" {
  description = "ECR repository name"
  type        = string
  default     = "swot-confluence-qq"
}

variable "profile" {
  description = "AWS CLI profile"
  type        = string
  default     = "default"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "memory" {
  description = "Memory in MiB for the Batch job"
  type        = number
  default     = 8192
}

variable "vcpus" {
  description = "vCPUs for the Batch job"
  type        = number
  default     = 2
}
