.PHONY: build deploy deploy-guided invoke-health invoke-chat \
        logs-health logs-chat test lint format clean

STACK_NAME   ?= ai-lambda-backend
REGION       ?= ap-southeast-2
LOG_TAIL     ?= 50

# ── Build ──────────────────────────────────────────────────────────────────────
# build       → arm64  (for AWS deployment, Graviton2)
# build-local → x86_64 (for local testing on Intel/AMD machines, no QEMU needed)

build:
	sam build --config-env default

build-local:
	sam build --config-env local

# ── Deploy ─────────────────────────────────────────────────────────────────────
deploy-guided:
	sam deploy --guided

deploy:
	sam deploy --no-confirm-changeset

# ── Local invoke (requires Docker + env.json) ──────────────────────────────────
invoke-health:
	sam local invoke HealthFunction \
		--event events/health_request.json \
		--env-vars env.json \
		--config-env local

invoke-chat:
	sam local invoke ChatFunction \
		--event events/chat_request.json \
		--env-vars env.json \
		--config-env local

# ── Local API (requires Docker + env.json) ────────────────────────────────────
local-api:
	sam local start-api --env-vars env.json --port 3000 --config-env local

# ── CloudWatch Logs ────────────────────────────────────────────────────────────
logs-health:
	sam logs -n HealthFunction \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--tail

logs-chat:
	sam logs -n ChatFunction \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--tail

# ── Tests ──────────────────────────────────────────────────────────────────────
test:
	python -m pytest tests/ -v --tb=short

test-cov:
	python -m pytest tests/ -v --tb=short \
		--cov=src --cov-report=term-missing --cov-report=html

# ── Code quality ───────────────────────────────────────────────────────────────
lint:
	python -m flake8 src/ tests/ --max-line-length=120

format:
	python -m black src/ tests/ --line-length=120

format-check:
	python -m black src/ tests/ --line-length=120 --check

# ── Stack outputs ──────────────────────────────────────────────────────────────
outputs:
	aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--query 'Stacks[0].Outputs' \
		--output table

api-url:
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--query 'Stacks[0].Outputs[?OutputKey==`ApiBaseUrl`].OutputValue' \
		--output text

# ── Update OpenAI secret ───────────────────────────────────────────────────────
update-secret:
	@SECRET_ARN=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--query 'Stacks[0].Outputs[?OutputKey==`OpenAISecretArn`].OutputValue' \
		--output text); \
	read -p "Enter OpenAI API key: " OPENAI_KEY; \
	aws secretsmanager put-secret-value \
		--secret-id "$$SECRET_ARN" \
		--secret-string "{\"openai_api_key\": \"$$OPENAI_KEY\"}" \
		--region $(REGION)

# ── Clean ──────────────────────────────────────────────────────────────────────
clean:
	rm -rf .aws-sam/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
