# Template ADRs

Template ADRs apply to all Terraform runner repositories derived from this
template.

ADR-template/0002 is runner-specific and intentionally differs from the
credential-free reference-framework decision in the framework templates: real
runner consumers must use the S3 backend contract described in that ADR.

ADR-template/0003 was withdrawn before release and is intentionally absent.

- [0001: Pin Terraform and Provider Versions Exactly](0001-pin-terraform-and-provider-versions-exactly.md)
- [0002: Mandate S3 as the State Backend](0002-mandate-s3-state-backend.md)
- [0004: Isolate Pull Request Target Triggers](0004-isolate-pull-request-target-triggers.md)
- [0005: Enforce Thin Runner Deployer Shape](0005-enforce-thin-runner-deployer-shape.md)
