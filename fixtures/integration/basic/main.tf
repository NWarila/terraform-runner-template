module "framework" {
  source = "./modules/framework"

  environment_prefix = var.environment_prefix
  global_tag         = var.global_tag
  all_environments   = var.all_environments
}

output "environments" {
  description = "Framework environment output exposed through the runner integration harness."
  value       = module.framework.environments
}

output "framework_summary" {
  description = "Framework summary output exposed through the runner integration harness."
  value       = module.framework.framework_summary
}
