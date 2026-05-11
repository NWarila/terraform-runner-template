## Summary

<!-- 1-3 bullets describing what this PR changes and why. -->

## Risk

<!-- What could break? What did you test? Reference any incident drills. -->

## Test plan

- [ ] CI passes locally / in PR
- [ ] If touching baseline-mirrored files: confirm `baseline-manifest.json` reflects the intended source of truth, or plan the upstream change before syncing forward
- [ ] If touching contract: run `make contract-check` and update the existing consumer fixtures when expectations change
- [ ] Documentation reflects the change (when applicable)
