# Invariants

Non-negotiable rules for this template. Violating one of these is a
breaking change at minimum.

- **Universal-layer files are NOT modified locally.** Every file listed
  in `sync/canonical-baseline.yaml` is byte-identical with its canonical
  source. Local edits are reverted on the next canonical-baseline-sync run.
- **The `runner` type is the only supported `repo_type`.** Adding a
  framework or other type to this template is out of scope; it would
  belong in a different per-type template (e.g.
  `terraform-template-template` for framework-shape).
- **The `runner-mode` reusable-pr-validation requires a pinned
  `framework_ref`.** Floating refs (`main`, branch names) defeat the
  end-to-end validation guarantee.
- **`docs/decision-records/org/` mirrors are byte-identical with the
  upstream `<owner>/.github`.** The universal `org-adr-sync` workflow
  enforces this on every PR.
- **All `uses:` references are SHA-pinned to 40-character commit hashes**
  (or local `./...` references, or digest-pinned docker images). Tag/
  branch references are rejected by the contract validator.
