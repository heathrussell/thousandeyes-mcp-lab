.PHONY: build deploy site smoke wipe destroy
AWS_REGION ?= ap-southeast-2
API_STACK ?= te-lab-api
SITE_STACK ?= te-lab-site
export AWS_REGION API_STACK SITE_STACK

build:
	python3 src/build.py

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

destroy:
	@BUCKET=$$(aws cloudformation describe-stacks --region $(AWS_REGION) --stack-name $(SITE_STACK) --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text 2>/dev/null); \
	if [ -n "$$BUCKET" ]; then aws s3 rm s3://$$BUCKET/ --recursive --region $(AWS_REGION) --only-show-errors; fi; \
	aws cloudformation delete-stack --region $(AWS_REGION) --stack-name $(SITE_STACK); \
	aws cloudformation delete-stack --region $(AWS_REGION) --stack-name $(API_STACK); \
	echo "Deleting $(SITE_STACK) and $(API_STACK) in $(AWS_REGION). The certificate stack (us-east-1), if any, is separate."
