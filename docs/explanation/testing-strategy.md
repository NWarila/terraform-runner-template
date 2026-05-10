# Testing Strategy

## What the tests cover

This template repo's `self-ci.yaml` exercises every component:

| Layer | Job | What it proves |
|---|---|---|
| Workflow YAML | `actionlint` | Workflow files parse and follow GitHub Actions semantics. |
| Workflow security | `zizmor` | No `${{ }}` template-injection vulnerabilities, no untrusted input as code, no dangerous triggers. |
| Shell scripts | `shellcheck` | `tools/install_ci_tools.sh` shells safely. |
| YAML data | `yamllint` | Workflow + contract + sync manifests are valid YAML. |
| Python tools | `ruff` | `tools/*.py` lint clean. |
| Python tools | `audit-tools-smoke-test` | Tool entry points import, the runner-template contract validates this repo as `template`, and the template scaffold manifest loads against drift-gate's schema. |
| Markdown | `markdownlint` | Documentation lints clean. |

Consumer runners exercise this template via their own `pr-validation.yaml`,
which calls this template's runner-mode reusable; the assembled
framework-plus-runner-data tree runs `make ci` end-to-end on every PR.

## What the tests do NOT cover

- The reusable workflows themselves are not directly executed in self-CI;
  they're exercised when consumer runners' PRs run them. A break in a
  reusable surfaces in consumer CI, not here.
- Cross-template sync is not exercised by self-CI; it runs on schedule
  and surfaces drift via PRs in this repo (and in every other per-type
  template that pulls from canonical).
- Branch protection / required-status-check enforcement is configured
  per-repo in GitHub Settings; not testable from CI.
