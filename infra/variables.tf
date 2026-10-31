variable "project_name" {
  type    = string
  default = "spry"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "google_client_id" {
  type    = string
  default = "71169484793-tgjn6abs819ogba7afoj6mbe18odc8c5.apps.googleusercontent.com"
}

variable "google_client_secret" {
  type      = string
  sensitive = true
}

variable "cognito_domain_prefix" {
  type    = string
  default = "spry-shymchuk-auth"
}

variable "cloudfront_domain" {
  type    = string
  default = "d1ddc10h0orzy1.cloudfront.net"
}

variable "backend_image_uri" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "route_table_ids" {
  type = list(string)
}

variable "security_group_id" {
  type = string
}

variable "recipient_email" {
  type = string
}

variable "parser_image_uri" {
  type = string
}

variable "parser_model" {
  type    = string
  default = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "site_origins" {
  type = list(string)
}


