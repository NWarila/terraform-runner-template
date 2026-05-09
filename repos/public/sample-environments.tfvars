# Sample tfvars file demonstrating the data shape a Terraform-runner
# consumer carries in repos/public/. Each entry in `all_environments`
# describes one synthetic environment the consumed framework
# (NWarila/terraform-framework-template) will produce on apply.
#
# A real runner would have one or more of these files per environment,
# named to match the deploy target (e.g., dev.tfvars, staging.tfvars,
# prod.tfvars). Multi-env runners typically iterate over them in CI.
#
# This is a TEMPLATE-OWNED sample. Derivative runners replace it with
# their own per-env data files. Renovate keeps the framework-tier
# dependencies (pinned via `framework_ref` in terraform-deploy.yaml)
# current; consumer data here is hand-edited.

environment_prefix = "sample-runner"
global_tag         = "terraform-runner-template-sample"

all_environments = [
  {
    name  = "demo"
    owner = "team-platform"
    tier  = "dev"
    tags  = ["sample", "runner-template", "dev"]
    manifests = [
      {
        filename = "demo-config.yaml"
        content  = "service: demo\nenv: dev\nsource: terraform-runner-template/sample\n"
      },
    ]
    lifecycle_hooks = [
      { name = "demo-pre-deploy" },
    ]
  },
]
