# Tutorial: Create Your First Runner from This Template

This tutorial walks you through scaffolding a new Terraform runner repository
from `terraform-runner-template`. By the end you will have a working runner
with a pinned framework reference, a passing drift gate, and a PR validation
workflow that verifies inventory changes before they reach `main`.

**Time to complete:** approximately 30 minutes.

**Prerequisites:**

- GitHub account with permission to create repositories under the target owner.
- `gh` CLI authenticated (`gh auth login`).
- Python 3.11+, `terraform` CLI (version matching `versions.tf`), and `git`.
- A local checkout of `NWarila/terraform-framework-template` for local
  integration testing (clone it beside this repo by default, or supply
  `--framework-source <path>` to override).

---

## Step 1 — Create the repository from the template

```sh
gh repo create <owner>/<runner-name> \
  --template NWarila/terraform-runner-template \
  --private \
  --clone
cd <runner-name>
```

The `--template` flag copies the full scaffold including workflows, contract,
and documentation structure. The resulting repository is independent of the
template; it is not a fork.

---

## Step 2 — Pin the template SHA and framework SHA

Open `.github/workflows/pr-validation.yaml`. Locate the `uses:` line that
references `NWarila/terraform-runner-template`. Replace the branch reference
with the current `main` SHA of this template:

```sh
gh api repos/NWarila/terraform-runner-template/commits/main \
  --jq '.sha'
```

Do the same for `framework_ref`. Locate the input and replace it with the
current `main` SHA of your chosen framework:

```sh
gh api repos/<framework-owner>/<framework-repo>/commits/main \
  --jq '.sha'
```

A pinned `pr-validation.yaml` looks like:

```yaml
jobs:
  validate:
    uses: NWarila/terraform-runner-template/.github/workflows/reusable-terraform-validation.yaml@<40-char-template-sha>
    with:
      mode: runner
      framework_repo: <framework-owner>/<framework-repo>
      framework_ref: <40-char-framework-sha>
      overlay_paths: |
        terraform/public => terraform/repos/public
        tests/fixtures/terraform/private => terraform/repos/private
```

Similarly pin the `uses:` SHA in `terraform-deploy.yaml`.

---

## Step 3 — Configure Renovate to keep pins current

Add a `.github/renovate.json5` that extends the template's baseline:

```json5
{
  $schema: "https://docs.renovatebot.com/renovate-schema.json",
  extends: [
    "github>NWarila/terraform-runner-template//.github/renovate.json5",
  ],
}
```

This inherits exact-pin and SHA-pin rules from the template without local
duplication. Enable Renovate on your new repository via the Renovate GitHub App.

---

## Step 4 — Add your repository inventory

Replace the sample inventory that shipped from the template with your own:

```sh
# Remove sample files
rm terraform/public/sample-environments.tfvars
rm tests/fixtures/terraform/private/sample-private-environments.tfvars

# Add your own inventory files
# terraform/public/ — public-safe repository definitions
# terraform/private/ — private inputs (secrets, private repo names, etc.)
```

Keep inventory files in the formats the framework expects. Consult the
framework's documentation for the expected variable names and types.

---

## Step 5 — Run local validation

Install tooling and run the local quality gate:

```sh
make setup
make lint
python tools/verify.py ci
```

If `terraform-framework-template` is checked out beside this repo, run the
full integration check:

```sh
python tools/verify.py integration
# or
python tools/verify.py integration --framework-source ../terraform-framework-template/terraform
```

Both checks must pass before opening a PR.

---

## Step 6 — Configure repository secrets

The deploy workflow uses OIDC to assume an AWS role. Add these secrets to the
new repository (Settings → Secrets and variables → Actions):

| Secret name          | Description                                           |
| -------------------- | ----------------------------------------------------- |
| `AWS_DEPLOY_ROLE_ARN`| IAM role ARN the workflow will assume via OIDC.       |
| `AWS_REGION`         | AWS region for the S3 backend and resource operations.|
| `TF_BACKEND_BUCKET`  | S3 bucket name that holds the Terraform state file.   |

See [`docs/reference/aws-bootstrap-requirements.md`](../reference/aws-bootstrap-requirements.md)
for the IAM trust policy and bucket policy that the OIDC deploy role requires.

---

## Step 7 — Open a pull request and confirm CI passes

```sh
git checkout -b feat/initial-inventory
git add terraform/public/ terraform/private/ tests/fixtures/
git commit -m "feat: add initial repository inventory"
git push -u origin feat/initial-inventory
gh pr create --fill
```

The following checks must pass on the PR:

| Check                  | What it validates                                |
| ---------------------- | ------------------------------------------------ |
| CI / contract          | Runner shape matches `runner-template-contract.yaml` |
| CI / pr-validation     | Framework checkout + overlay + framework gate    |
| Drift Gate             | Org-baseline and template-tier scaffold files match expected content |
| Security               | CodeQL and IaC security scans                    |

When all checks are green, merge via "Squash and merge".

---

## Next steps

- Add repo-specific ADRs under `docs/decision-records/repo/` for any decisions
  that are specific to your runner (for example, the framework you chose or any
  overlay path overrides).
- Review [`docs/reference/quality-gates.md`](../reference/quality-gates.md) for
  the full gate inventory.
- Review [`docs/reference/mirroring.md`](../reference/mirroring.md) for the
  files the drift gate enforces byte-identical.
