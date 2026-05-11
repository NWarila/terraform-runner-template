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
          "token.actions.githubusercontent.com:sub": "repo:<owner>/<runner-repo>:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

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

Minimum S3 policy shape:

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
        "StringLike": {
          "s3:prefix": [
            "runners/<runner-repo>/*"
          ]
        }
      }
    },
    {
      "Sid": "ReadWriteRunnerStateObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::<state-bucket>/runners/<runner-repo>/*"
    }
  ]
}
```

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
    role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
    aws-region: ${{ vars.AWS_REGION }}
```

Use repository or environment variables for non-secret values such as:

- `AWS_DEPLOY_ROLE_ARN`
- `AWS_REGION`
- `TF_BACKEND_BUCKET`
- `TF_BACKEND_KEY_PREFIX`

Do not store static AWS access keys in repository or environment secrets.

## Implementation Checklist

- [ ] OIDC provider exists in the AWS account.
- [ ] Deploy role trust policy scopes `aud` and `sub`.
- [ ] Deploy role policy grants only the required state bucket prefix.
- [ ] KMS access is scoped to the state bucket key, if SSE-KMS is used.
- [ ] Private inventory S3 access is read-only and prefix-scoped.
- [ ] Framework-specific permissions are reviewed separately.
- [ ] GitHub workflow has `id-token: write` and `contents: read`.
- [ ] Workflow uses SHA-pinned `aws-actions/configure-aws-credentials`.
- [ ] No static AWS access keys exist in workflow YAML or repo secrets.
