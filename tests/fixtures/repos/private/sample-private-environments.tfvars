# Sample fixture — what `repos/private/<env>.tfvars` would look like
# when fetched at deploy time. In production, runners fetch real
# private data from S3 (per-environment, OIDC-authenticated). In CI
# (where AWS credentials may not be available for state operations
# but are not needed for plan-only validation), this fixture stands
# in.
#
# The contract requires `repos/private/` and `tests/fixtures/repos/
# private/` to exist; the production data path is the former, the
# CI-deterministic path is the latter. A real runner's
# pr-validation.yaml typically uses `tests/fixtures/repos/private/`
# as its overlay source for private-side data and skips the S3 fetch.

environment_prefix = "sample-runner"
global_tag         = "terraform-runner-template-private-fixture"

all_environments = [
  {
    name  = "private-staging"
    owner = "team-platform"
    tier  = "staging"
    tags  = ["sample", "runner-template", "staging", "private-fixture"]
    rotation = {
      rotation_days = 30
    }
  },
]
