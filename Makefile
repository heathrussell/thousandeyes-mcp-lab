.PHONY: build test dev deploy site smoke wipe wipe-onboarding destroy
AWS_REGION ?= ap-southeast-2
API_STACK ?= te-lab-api
SITE_STACK ?= te-lab-site
export AWS_REGION API_STACK SITE_STACK

build:
	python3 src/build.py

# Offline API checks: every route, with DynamoDB, SSM and ThousandEyes stubbed (needs api/answers.json)
test:
	python3 api/tests/test_api.py

# The whole lab on http://127.0.0.1:8787 with no AWS and a fake ThousandEyes (proctor key proctor-secret-123, TE token good-token)
dev: build
	python3 api/tests/devserver.py

deploy:
	scripts/deploy.sh

# Upload the site files only (after editing site/config.js or rebuilding the page)
site:
	@BUCKET=$$(aws cloudformation describe-stacks --region $(AWS_REGION) --stack-name $(SITE_STACK) --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text); \
	DIST=$$(aws cloudformation describe-stacks --region $(AWS_REGION) --stack-name $(SITE_STACK) --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" --output text); \
	aws s3 sync site/ s3://$$BUCKET/ --delete --region $(AWS_REGION) --only-show-errors; \
	aws s3 cp site/config.js s3://$$BUCKET/config.js --region $(AWS_REGION) --cache-control no-cache --content-type application/javascript --only-show-errors; \
	aws cloudfront create-invalidation --distribution-id $$DIST --paths "/*" --query Invalidation.Id --output text

smoke:
	scripts/smoke.sh

wipe:
	scripts/wipe-board.sh

# Clear the lab's onboarding records (ThousandEyes account groups and users are left alone)
wipe-onboarding:
	scripts/wipe-onboarding.sh

destroy:
	@BUCKET=$$(aws cloudformation describe-stacks --region $(AWS_REGION) --stack-name $(SITE_STACK) --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text 2>/dev/null); \
	if [ -n "$$BUCKET" ]; then aws s3 rm s3://$$BUCKET/ --recursive --region $(AWS_REGION) --only-show-errors; fi; \
	aws ssm delete-parameter --region $(AWS_REGION) --name /te-lab/$(API_STACK)/te-token 2>/dev/null || true; \
	aws cloudformation delete-stack --region $(AWS_REGION) --stack-name $(SITE_STACK); \
	aws cloudformation delete-stack --region $(AWS_REGION) --stack-name $(API_STACK); \
	echo "Deleting $(SITE_STACK) and $(API_STACK) in $(AWS_REGION) and the ThousandEyes token parameter. The certificate stack (us-east-1), if any, is separate."
