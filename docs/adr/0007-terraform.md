# ADR 0007: Terraform and HCP Terraform for the infrastructure

- Status: accepted (Lab 7)
- Date: 2026-10-31

## Context

Until Lab 6 the infrastructure of Spry lived in three CloudFormation templates (infra/auth.yml, infra/reports.yml, infra/ai.yml), deployed by hand with `aws cloudformation deploy` from a laptop. Nobody could see what a change would do before it ran, the Google client secret was a template parameter, and the real infrastructure had already drifted: the report builder got DATABASE_URL by hand in the console, and the mailer sender was changed by hand.

## Decision

One Terraform root module in infra/ (versions.tf, variables.tf, auth.tf, reports.tf, ai.tf, outputs.tf), one HCP Terraform workspace (spry-dev) in Remote execution mode, with dynamic AWS credentials (an OIDC role, no stored access keys). The workspace is connected to the GitHub repository with infra as its working directory:

- A pull request that touches infra/ runs a speculative plan, shown in the check.
- A merge to main runs plan and apply in HCP Terraform.
- The Makefile has `infra-plan` and reads `terraform output -raw ...`. It has no `terraform apply`.

The existing resources were adopted, not re-created: the stacks were given DeletionPolicy Retain, deleted, and the surviving resources were imported with `import` blocks (31 resources in total: 4 Cognito, 19 in the reports stack, 8 in the AI stack). Nothing was replaced or destroyed, so the 5 user accounts in the user pool and the reports bucket were never touched. The import blocks and the CloudFormation templates have been deleted.

## Alternatives considered

- **CloudFormation (stay).** Works, but there is no plan step that shows a diff in review, no import of existing resources into a template without a console workflow, and a circular dependency (bucket, permission, notification) that needed a naming trick. Rejected because the review of changes is the point of this lab.
- **AWS CDK.** It generates CloudFormation, so it keeps its limits (stack states, replacement behaviour) and adds a programming-language toolchain and a bootstrap stack for a project with about 31 resources. Rejected as more machinery than the project needs.
- **OpenTofu.** Technically close to Terraform, but the course uses HCP Terraform for remote runs, state and VCS integration, and OpenTofu has no equivalent hosted workflow. Rejected for this project; switching later is possible because the HCL is the same.

## Who can change the infrastructure, and how

Anyone with write access to the repository can propose a change by opening a pull request. The plan is posted in the check, so the reviewer reads the diff before merging. The apply runs only in HCP Terraform, after a merge to main, using short-lived credentials from the OIDC role. Nobody applies from a laptop: with a VCS-connected workspace, CLI applies are blocked. The IAM role used by HCP Terraform currently has AdministratorAccess and trusts the organization; narrowing it to one workspace and the services in use is a follow-up.

## Secrets and state

- The Google client secret is a sensitive Terraform variable in the workspace. It is never in the repository, in terraform.tfvars or in a .tfvars.json file. The identity provider uses `ignore_changes = [provider_details]`, because Cognito never returns the secret. Rotation is done with `aws cognito-idp update-identity-provider`, and the workspace variable is updated at the same time.
- DATABASE_URL of the report builder is set by hand on the Lambda and ignored by Terraform (`ignore_changes = [environment]`), so it is not in any Terraform file or variable.
- The state is stored in HCP Terraform, encrypted at rest, with access limited to the organization. Be clear about one thing: sensitive values are hidden in plan output, but resources that Terraform has read are stored in the state, so values such as the Lambda environment variables and the Google provider details are in the state. Whoever can read the state can read them. A plan log from before this ADR printed the database URL in plain text; the database password has to be rotated.
- A later improvement is to move the secrets to AWS Secrets Manager and let the Lambdas read them at runtime.

## If HCP Terraform is down

The running system does not depend on it: Cognito, the Lambdas, the queue, the schedule and the bucket keep working. What stops is changing the infrastructure. For an emergency, a fix can be made in the AWS console and then written back into the HCP-managed code, so that the next plan shows no drift. State can be exported from HCP Terraform when it is available again, and the code can be run with another Terraform backend in the worst case.

## Consequences

- Every change is reviewed as a plan before it is applied, and drift shows up in the next run.
- Environment variables set by hand (DATABASE_URL) are a known gap and are ignored on purpose until they move to a secret store.
- Two roads now deploy the project: GitHub Actions deploys the application (images, frontend), HCP Terraform deploys the infrastructure. A change that needs both (for example a new Lambda environment variable) is merged in the infrastructure first, then the application.
