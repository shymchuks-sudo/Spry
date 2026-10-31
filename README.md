# Spry
## Infrastructure (Terraform)

The Cognito user pool, the weekly report pipeline and the agenda parser are Terraform in `infra/`. The CloudFormation templates were retired in Lab 7 (see [ADR 0007](docs/adr/0007-terraform.md)).

- HCP Terraform: organization `ooad-shymchuks-sudo`, workspace `spry-dev`, connected to this repository (working directory `infra`, branch `main`).
- Pull request: HCP Terraform runs a speculative plan and shows it as a check. Nothing is applied.
- Merge to `main`: HCP Terraform plans and applies. Applies happen only there, never from a laptop and never from the Makefile.
- Preview from a laptop: `make infra-plan` (run `terraform login` once first). This is a plan only.
- Secrets are sensitive workspace variables in HCP Terraform (for example `google_client_secret`), not files in the repo. `infra/spry.auto.tfvars.json` holds only non-secret IDs.
- The report builder's `DATABASE_URL` is set by hand on the Lambda and ignored by Terraform (`ignore_changes = [environment]`).
- The Makefile reads values with `terraform output -raw` (user_pool_id, user_pool_client_id, cognito_auth_domain, parser_function_url, reports_bucket, reports_queue_url).
