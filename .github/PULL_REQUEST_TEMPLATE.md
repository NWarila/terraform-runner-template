## Summary

<!-- 1-3 bullets describing what this PR changes and why. -->

## Risk

<!-- What could break? What automated evidence should the reviewer trust? -->

## Automated evidence

- [ ] PR validation passes in GitHub
- [ ] Drift Gate passes in GitHub (`org-baseline / verify` and `runner-template / verify`)
- [ ] Security workflow passes, or advisory findings are reviewed and documented
- [ ] Deploy plan evidence is present when Terraform inventory or deploy inputs change
- [ ] Documentation reflects the change (when applicable)

## Runner review notes

- [ ] Template pin changes move workflow `uses`, `template_ref`, and drift `source-ref` together
- [ ] Framework pin changes move PR validation `framework_ref`, deploy workflow SHA, and deploy `framework_ref` together
- [ ] Private fixture changes explain the production private inventory shape represented
- [ ] The diff keeps this repo data-only and does not add template-maintainer tooling
