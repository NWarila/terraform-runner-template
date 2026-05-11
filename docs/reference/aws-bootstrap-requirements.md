# AWS Bootstrap Requirements

This runner template does not own AWS bootstrap resources directly. A runner is
data-only and must not add a top-level `terraform/` directory just to provision
its own credentials or backend.

Put concrete IAM, S3, KMS, and backend bootstrap resources in one of these
places:

1. A dedicated account or runner bootstrap repository, recommended for shared
   state buckets and reusable OIDC roles.
2. A framework repository, when the role and state backend are specific to that
   framework.
3. Repo-local documentation under `docs/how-to/`, when resources are manually
   provisioned outside Terraform.

This page is the template-level checklist for what those bootstrap resources
must provide before a real runner enables `apply: true`.

## Required AWS Resources

### GitHub OIDC provider

Create one IAM OpenID Connect provider per AWS account if the account does not
already have it:

- Provider URL: `https://token.actions.githubusercontent.com`
- Audience/client ID: `sts.amazonaws.com`

GitHub's AWS OIDC documentation requires an `id-token: write` workflow
permission and recommends constraining the role trust policy with a `sub`
condition. The official `aws-actions/configure-aws-credentials` documentation
uses the same provider URL and audience.

References:

- <https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services>
- <https://github.com/aws-actions/configure-aws-credentials>

### Deploy role

Create an IAM role for the runner's deploy workflow. The role trust policy must:

- Trust the GitHub OIDC provider for the AWS account.
- Allow only `sts:AssumeRoleWithWebIdentity`.
- Require `token.actions.githubusercontent.com:aud = sts.amazonaws.com`.
- Scope `token.actions.githubusercontent.com:sub` to the exact repository and
  branch or environment that may apply.

Example branch-scoped trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:repository_id": "<numeric-repo-id>",
          "token.actions.githubusercontent.com:sub": "repo:<owner>/<runner-repo>:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

Include `token.actions.githubusercontent.com:repository_id` whenever the AWS
account hosts roles for portfolio repositories that might be renamed,
transferred, or recreated. The numeric repository ID is immutable across
renames; the textual `sub` claim is not. Pinning both closes a rename-squatting
window where a deleted repo's name could be reclaimed by an attacker who then
re-establishes the original `sub` value. Retrieve the ID once with
`gh api repos/<owner>/<repo> --jq .id` and write it into the trust policy.

If the runner uses GitHub Environments for deployment approval, scope `sub` to
the environment instead:

```json
{
  "token.actions.githubusercontent.com:sub": "repo:<owner>/<runner-repo>:environment:<environment-name>"
}
```

### State backend permissions

If the framework uses the S3 backend required by
`ADR-template/0002`, the deploy role needs access to the specific state bucket
and key prefix for that runner.

Minimum hardened S3 policy shape:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListRunnerStatePrefix",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<state-bucket>",
      "Condition": {
        "StringEquals": {
          "s3:prefix": [
            "runners/<runner-repo>/terraform.tfstate",
            "runners/<runner-repo>/terraform.tfstate.tflock"
          ]
        }
      }
    },
    {
      "Sid": "ReadWriteRunnerStateFile",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::<state-bucket>/runners/<runner-repo>/terraform.tfstate"
    },
    {
      "Sid": "ManageRunnerStateLockfile",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::<state-bucket>/runners/<runner-repo>/terraform.tfstate.tflock"
    },
    {
      "Sid": "DenyDeleteRunnerStateFile",
      "Effect": "Deny",
      "Action": "s3:DeleteObject",
      "Resource": "arn:aws:s3:::<state-bucket>/runners/<runner-repo>/terraform.tfstate"
    },
    {
      "Sid": "DenyUnencryptedRunnerStatePuts",
      "Effect": "Deny",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::<state-bucket>/runners/<runner-repo>/*",
      "Condition": {
        "StringNotEquals": {
          "s3:x-amz-server-side-encryption": [
            "AES256",
            "aws:kms"
          ]
        }
      }
    },
    {
      "Sid": "DenyRunnerStatePutsWithoutEncryptionHeader",
      "Effect": "Deny",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::<state-bucket>/runners/<runner-repo>/*",
      "Condition": {
        "Null": {
          "s3:x-amz-server-side-encryption": "true"
        }
      }
    }
  ]
}
```

The state object and lockfile object are split intentionally. The state file can
be read and written but not deleted; the lockfile can be deleted so Terraform's
S3 native locking can release it. Keep the explicit delete deny and both
encryption deny guards even when the bucket has default encryption enabled. The
`StringNotEquals` guard above permits either SSE-S3 (`AES256`) or SSE-KMS
(`aws:kms`); narrow it to one value if the bucket policy intentionally allows
only one encryption mode.

The `s3:ListBucket` condition uses the exact state key and lockfile key because
Terraform's S3 backend checks the configured key path while refreshing state. A
folder-only prefix such as `runners/<runner-repo>/` can still produce `403`
responses during `terraform init` even when `GetObject` and `PutObject` are
correctly scoped.

If the bucket uses SSE-KMS, also grant the role the narrow KMS actions required
for that key:

```json
{
  "Sid": "UseStateBucketKmsKey",
  "Effect": "Allow",
  "Action": [
    "kms:Decrypt",
    "kms:Encrypt",
    "kms:GenerateDataKey",
    "kms:DescribeKey"
  ],
  "Resource": "arn:aws:kms:<region>:<account-id>:key/<key-id>"
}
```

The bucket itself must have versioning, encryption at rest, and access logging
or CloudTrail data events enabled. Those controls are bucket properties, not
runner workflow settings.

### Private inventory permissions

If `repos/private/` is populated from S3 before deploy, grant read access only
to that inventory object or prefix:

```json
{
  "Sid": "ReadPrivateRunnerInventory",
  "Effect": "Allow",
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::<inventory-bucket>/<runner-repo>/repos/private/*"
}
```

### Framework resource permissions

Add only the permissions required by the framework being deployed. This template
cannot define those permissions because different frameworks manage different
resource types.

Framework-specific permissions must be:

- Scoped to specific resource ARNs where AWS supports resource-level access.
- Split by capability when possible, for example read-only discovery, state
  backend access, and mutating deploy permissions.
- Reviewed with the framework's plan-aware OPA policy and threat model.
- Kept out of `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`; OIDC is the only
  supported credential path.

## Worked Example: This Template's Own State Backend

The IAM role this template itself uses to write its own Terraform state to
`s3://793496711039-terraform/nwarila-platform/terraform-runner-template/` is
included here as a concrete reference. This worked example is written for
SSE-S3 (`AES256`). If the bucket uses SSE-KMS instead, change the encryption
condition to allow `aws:kms` and add the KMS key grant shown above. Substitute
account ID, bucket name, state-key prefix, and repository ID for your own
consumer. The defensive patterns — `repository_id` constraint, explicit
`Deny` rules, per-object ACLs, dual encryption guards — are the parts worth
carrying forward.

### Trust policy (this template)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "GitHubActionsAssumeRole",
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::793496711039:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:repository_id": "1233369688",
          "token.actions.githubusercontent.com:sub": "repo:NWarila/terraform-runner-template:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

Three claims pinned together: `aud` is the standard audience, `repository_id`
locks the trust to the immutable numeric ID of `NWarila/terraform-runner-template`,
and `sub` further restricts to workflow runs originating from `refs/heads/main`.
A pull request triggered run cannot assume this role; only post-merge workflows
on `main` can.

### Permission policy (this template)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListTerraformStateKeys",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::793496711039-terraform",
      "Condition": {
        "StringEquals": {
          "s3:prefix": [
            "nwarila-platform/terraform-runner-template/terraform.tfstate",
            "nwarila-platform/terraform-runner-template/terraform.tfstate.tflock"
          ]
        }
      }
    },
    {
      "Sid": "ReadWriteStateFileOnly",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::793496711039-terraform/nwarila-platform/terraform-runner-template/terraform.tfstate"
    },
    {
      "Sid": "ManageS3LockfileOnly",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::793496711039-terraform/nwarila-platform/terraform-runner-template/terraform.tfstate.tflock"
    },
    {
      "Sid": "DenyDeleteStateFile",
      "Effect": "Deny",
      "Action": "s3:DeleteObject",
      "Resource": "arn:aws:s3:::793496711039-terraform/nwarila-platform/terraform-runner-template/terraform.tfstate"
    },
    {
      "Sid": "DenyUnencryptedPuts",
      "Effect": "Deny",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::793496711039-terraform/nwarila-platform/terraform-runner-template/*",
      "Condition": {
        "StringNotEquals": {
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    },
    {
      "Sid": "DenyPutsWithoutEncryptionHeader",
      "Effect": "Deny",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::793496711039-terraform/nwarila-platform/terraform-runner-template/*",
      "Condition": {
        "Null": {
          "s3:x-amz-server-side-encryption": "true"
        }
      }
    }
  ]
}
```

Six statements, four defensive patterns worth carrying:

1. **Per-object ACLs.** The state object (`terraform.tfstate`) can only be read
   or written — never deleted by the role. The lockfile object
   (`terraform.tfstate.tflock`) can be deleted because S3 native locking
   removes it when the lock is released. Splitting these into two `Allow`
   statements is stricter than a single prefix-wildcard `Allow`.
2. **Explicit deny on state deletion.** Even though `Effect: Allow` for
   `s3:DeleteObject` is never granted on `terraform.tfstate`, the explicit
   `Deny` (Sid `DenyDeleteStateFile`) survives any future policy edit that
   accidentally widens the `Allow` set. AWS evaluates explicit `Deny` before
   any `Allow`, so this is a backstop against drift.
3. **Dual encryption guards.** `DenyUnencryptedPuts` rejects writes with the
   wrong algorithm; `DenyPutsWithoutEncryptionHeader` rejects writes that omit
   the header entirely. A single `StringNotEquals` would only catch the first
   case; the `Null` condition catches the second. In this worked example they
   enforce that every object written under this prefix carries SSE-S3
   encryption; for SSE-KMS, allow `aws:kms` and add the scoped KMS grant.
4. **State-key-scoped `ListBucket`.** The role can list the bucket only when
   the request is constrained to the template's state object or lockfile object.
   This lets Terraform refresh the backend without granting the role permission
   to enumerate other tenants' state objects in the same bucket.

### Substituting for a consumer

For a runner repository at `<owner>/<runner-repo>` writing state at
`<state-bucket>/<runner-prefix>/`:

- Replace `793496711039` with the AWS account ID hosting the role and bucket.
- Replace `793496711039-terraform` with the state bucket name.
- Replace `nwarila-platform/terraform-runner-template/` with the runner-specific
  state-key prefix (`runners/<runner-repo>/`, an org-prefixed path, or whatever
  matches the bootstrap configuration's key convention).
- Replace `1233369688` with the consumer's numeric repository ID
  (`gh api repos/<owner>/<runner-repo> --jq .id`).
- Replace the `sub` value with `repo:<owner>/<runner-repo>:ref:refs/heads/main`,
  or the appropriate `environment:<name>` form if GitHub Environments gate
  the deploy.

The four defensive patterns are repository-agnostic and SHOULD be retained
verbatim.

## Required GitHub Workflow Wiring

Any runner workflow that assumes the AWS role needs:

```yaml
permissions:
  contents: read
  id-token: write
```

The workflow must use a SHA-pinned `aws-actions/configure-aws-credentials`
step with `role-to-assume:`:

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@<40-character-sha>
  with:
    role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
    aws-region: ${{ secrets.AWS_REGION }}
```

Use repository or environment secrets for deployment identifiers. These values
are not static credentials, but they can disclose AWS account IDs, bucket names,
regions, and state-key layout in workflow metadata:

- `AWS_DEPLOY_ROLE_ARN`
- `AWS_REGION`
- `TF_BACKEND_BUCKET`

`TF_BACKEND_BUCKET` is the bare S3 bucket name, not an ARN or `s3://` URI.
The state-key prefix is a checked-in `backend_key_prefix` workflow input so
reviewers can see which state object the runner owns. Move it to an environment
secret only for repos that intentionally provision and map that secret.

The template's `terraform-deploy.yaml` workflow uses those secrets on trusted
`main` or manual runs to call the framework deploy reusable against:

```text
s3://${TF_BACKEND_BUCKET}/<backend_key_prefix>/terraform.tfstate
```

Pull requests run plan-only validation through `pr-validation.yaml`, so fork and
PR validation stays deterministic and credential-free. Trusted deploy runs
assume AWS via OIDC, initialize the S3 backend, apply the saved plan, and verify
the state object with `aws s3api head-object`.

Do not store static AWS access keys in repository or environment secrets.

## Implementation Checklist

- [ ] OIDC provider exists in the AWS account.
- [ ] Deploy role trust policy scopes `aud`, `repository_id`, and `sub`.
- [ ] Deploy role policy grants only the required state bucket prefix.
- [ ] State-object `Allow` is limited to `GetObject` + `PutObject`; an
      explicit `Deny` on `DeleteObject` covers the state object.
- [ ] Lockfile `Allow` (`terraform.tfstate.tflock`) grants `DeleteObject` so
      native locking can release the lock.
- [ ] Dual encryption guards reject `PutObject` with wrong algorithm
      (`StringNotEquals`) and with missing header (`Null`).
- [ ] KMS access is scoped to the state bucket key, if SSE-KMS is used.
- [ ] Private inventory S3 access is read-only and prefix-scoped.
- [ ] Framework-specific permissions are reviewed separately.
- [ ] GitHub workflow has `id-token: write` and `contents: read`.
- [ ] Workflow uses SHA-pinned `aws-actions/configure-aws-credentials`.
- [ ] `terraform-deploy.yaml` succeeds on `main`, applies through the S3 backend,
      and verifies the state object with `aws s3api head-object`.
- [ ] No static AWS access keys exist in workflow YAML or repo secrets.
