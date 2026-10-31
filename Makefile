AWS_REGION ?= eu-north-1
ECR_REGISTRY ?= 594559484590.dkr.ecr.$(AWS_REGION).amazonaws.com
S3_BUCKET ?= spry-frontend-shymchuks-sudo
CLOUDFRONT_DIST_ID ?= E28WXS7KZKWV0G

# LLM settings (Bedrock, us-east-1). Change the model here, nowhere else.
PARSER_MODEL ?= us.anthropic.claude-haiku-4-5-20251001-v1:0
PYTHON ?= python

# Infrastructure is Terraform in infra/. State and applies live in HCP Terraform.
# This Makefile only reads it. There is no apply target on purpose.
TF = terraform -chdir=infra
tfout = $(shell $(TF) output -raw $(1))

.PHONY: up-local infra-plan deploy-frontend deploy-backend report-now llm-hello parse

up-local:
	docker compose up --build

infra-plan:
	$(TF) init -input=false
	$(TF) plan

deploy-frontend:
	cd frontend && npm ci && VITE_USER_POOL_ID=$(call tfout,user_pool_id) VITE_APP_CLIENT_ID=$(call tfout,user_pool_client_id) VITE_COGNITO_DOMAIN=$(call tfout,cognito_auth_domain) VITE_PARSER_URL=$(call tfout,parser_function_url) npm run build
	aws s3 sync frontend/dist/ s3://$(S3_BUCKET)/ --delete
	aws cloudfront create-invalidation --distribution-id $(CLOUDFRONT_DIST_ID) --paths "/*"

deploy-backend:
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker build -t $(ECR_REGISTRY)/spry-backend:latest ./backend
	docker push $(ECR_REGISTRY)/spry-backend:latest
	aws ecs update-service --cluster spry-cluster --service spry-backend-service --force-new-deployment

report-now:
	@WEEK=$${WEEK:-$$(date +%G-W%V)} ; \
	QUEUE_URL="$(call tfout,reports_queue_url)" ; \
	echo "Sending report request for week: $${WEEK}" ; \
	aws sqs send-message \
		--queue-url "$${QUEUE_URL}" \
		--message-body "{\"week\": \"$${WEEK}\", \"source\": \"make-command\"}"

llm-hello:
	cd backend && PARSER_MODEL="$(PARSER_MODEL)" $(PYTHON) scripts/llm_hello.py

parse:
	cd backend && PARSER_MODEL="$(PARSER_MODEL)" PYTHONPATH=. TEXT="$(TEXT)" $(PYTHON) scripts/parse_agenda.py