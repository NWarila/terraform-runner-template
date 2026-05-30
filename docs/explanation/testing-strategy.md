# Testing Strategy

## What the tests cover

This template repo's `ci.yaml` exercises every component:

| Layer | Job | What it proves |
|---|---|---|
| Workflow YAML | `actionlint` | Workflow files parse and follow GitHub Actions semantics. |
| Workflow security | `zizmor` | No `${{ }}` template-injection vulnerabilities, no untrusted input as code, no dangerous triggers. |
| Shell scripts | `shellcheck` | `tools/install_ci_tools.sh` shells safely. |
| YAML data | `yamllint` | Workflow and contract YAML are valid. |
| Python tools | `ruff` | `tools/*.py` lint clean. |
| Python tools | `audit-tools-smoke-test` | Tool entry points import, the runner-template contract validates this repo as `template`, and the template scaffold manifest loads against drift-gate's schema. |
| Markdown | `markdownlint` | Documentation lints clean. |

Consumer runners exercise this template via their own `pr-validation.yaml`,
which calls this template's runner-mode reusable; the assembled
framework-plus-runner-data tree runs the framework quality gate end-to-end on every PR.

## What the tests do NOT cover

- The reusable workflows themselves are not directly executed in self-CI;
  they're exercised when consumer runners' PRs run them. A break in a
  reusable surfaces in consumer CI, not here.
- Cross-template drift is checked in self-CI but is not a sync: the
  `cross-template-drift` job (push/PR-gated, no schedule) diffs this
  template's shape-shared regions against the sibling
  `NWarila/packer-runner-template` via `tools/check_cross_template_drift.py`
  and fails the PR on divergence. It pulls nothing from a canonical source;
  a maintainer must change a shape-shared region in both templates in the
  same review window.
- Branch protection / required-status-check enforcement is configured
  per-repo in GitHub Settings; not testable from CI.
