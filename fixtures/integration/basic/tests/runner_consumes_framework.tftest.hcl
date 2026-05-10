run "runner_consumes_framework" {
  command = apply

  assert {
    condition     = output.framework_summary.environments_total == 1
    error_message = "Expected runner fixture to produce exactly one framework environment."
  }

  assert {
    condition     = output.framework_summary.manifests_total == 1
    error_message = "Expected runner sample data to produce exactly one manifest."
  }

  assert {
    condition     = output.environments["demo"].retention_days == 7
    error_message = "Expected dev tier default retention_days=7 through the runner/framework boundary."
  }
}
