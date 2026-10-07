AWS_REGION ?= eu-north-1
ECR_REGISTRY ?= 594559484590.dkr.ecr.$(AWS_REGION).amazonaws.com
S3_BUCKET ?= spry-frontend-shymchuks-sudo
CLOUDFRONT_DIST_ID ?= E28WXS7KZKWV0G

.PHONY: build-local up-local deploy-frontend deploy-backend

# Local Development
up-local:
	docker compose up --build

# Deployment commands
deploy-frontend:
	cd frontend && npm ci && npm run build
	aws s3 sync frontend/dist/ s3://$(S3_BUCKET)/ --delete
	aws cloudfront create-invalidation --distribution-id $(CLOUDFRONT_DIST_ID) --paths "/*"

deploy-backend:
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	docker build -t $(ECR_REGISTRY)/spry-backend:latest ./backend
	docker push $(ECR_REGISTRY)/spry-backend:latest
	aws ecs update-service --cluster spry-cluster --service spry-backend-service --force-new-deployment
