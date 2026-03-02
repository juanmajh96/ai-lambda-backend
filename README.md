# ai-lambda-backend

A production-ready, serverless AI backend built on AWS Lambda that exposes an
OpenAI Chat Completions API through a managed HTTP endpoint. Clone it, deploy
it in one command, and have a live AI API running in your own AWS account in
under 15 minutes.

**License:** MIT — free to use, fork, and modify for any purpose.

---

## What you get

| Feature | Detail |
|---------|--------|
| `POST /chat` | OpenAI Chat Completions (model, tokens, temperature all configurable) |
| `GET /health` | Liveness probe for uptime monitoring |
| **Serverless** | AWS Lambda — pay only for requests made, scales to zero |
| **x86_64** | Runs on standard Lambda infrastructure, broadest compatibility |
| **Secrets management** | API key stored in AWS Secrets Manager, never in env vars or code |
| **Observability** | Structured JSON logs, X-Ray distributed tracing, CloudWatch metrics |
| **Alarms** | Error rate > 5%, any throttles, P99 duration > 48 s |
| **Dashboard** | 8-widget CloudWatch dashboard out of the box |
| **IaC** | 100% AWS SAM — reproducible, version-controlled infrastructure |

---

## Architecture

```
Client
  │
  ▼
API Gateway HTTP API v2  ──── throttle: 50 req/s burst 100
  │                │
  GET /health      POST /chat
  │                │
  ▼                ▼
HealthFunction   ChatFunction  (512 MB, 60 s timeout, x86_64)
  │                │
  │                ├── AWS Secrets Manager  (OpenAI API key)
  │                └── OpenAI API  (Chat Completions)
  │
  ├── CloudWatch Logs  (structured JSON via Powertools)
  ├── AWS X-Ray        (distributed tracing)
  └── CloudWatch       (metrics, 3 alarms, 1 dashboard)
```

---

## Prerequisites

You need the following installed and configured before deploying.

### 1. AWS account

Sign up at <https://aws.amazon.com> if you don't have one. The free tier covers
a large number of Lambda invocations per month.

### 2. AWS CLI

```bash
# macOS (Homebrew)
brew install awscli

# Windows (winget)
winget install Amazon.AWSCLI

# Linux
pip install awscli
```

Configure with your credentials:

```bash
aws configure
# AWS Access Key ID:     <your key>
# AWS Secret Access Key: <your secret>
# Default region name:   ap-southeast-2      # or any region you prefer
# Default output format: json
```

Verify it works:

```bash
aws sts get-caller-identity
```

### 3. AWS SAM CLI

SAM (Serverless Application Model) is the deployment tool.

```bash
# macOS (Homebrew)
brew tap aws/tap
brew install aws-sam-cli

# Windows — download the MSI installer:
# https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

# Linux
pip install aws-sam-cli
```

Verify:

```bash
sam --version   # should print SAM CLI, version 1.x.x
```

### 4. Docker

SAM uses Docker to build the Lambda layer in a Linux container that matches
the Lambda runtime, ensuring native dependencies compile correctly.

Download Docker Desktop from <https://www.docker.com/products/docker-desktop/>.

Make sure Docker is **running** before you build.

Verify:

```bash
docker --version
```

### 5. OpenAI API key

Create one at <https://platform.openai.com/api-keys>. You will paste it into
Secrets Manager after the first deploy — it is never stored in source code.

### 6. Python 3.12 (for local testing only)

```bash
# macOS
brew install python@3.12

# Windows
winget install Python.Python.3.12

# Linux
sudo apt install python3.12
```

---

## A note on commands — Windows vs macOS/Linux

The `Makefile` in this project provides short aliases like `make build` and
`make deploy`. On **macOS and Linux** these work out of the box.

On **Windows**, `make` is not installed by default. Every `make` command in
this guide has a direct equivalent shown alongside it. Use whichever fits your
setup:

| Platform | Use |
|----------|-----|
| macOS / Linux | `make <target>` |
| Windows (PowerShell / CMD) | The `sam` / `python` command shown below each `make` line |

To install `make` on Windows if you prefer it:
```powershell
winget install GnuWin32.Make
# then restart your terminal
```

---

## Quick start

### Step 1 — Clone the repository

```bash
git clone https://github.com/<your-org>/ai-lambda-backend.git
cd ai-lambda-backend
```

### Step 2 — Build

The project builds and deploys as **x86_64**, which works on all developer
machines and all AWS regions without any special configuration.

**macOS / Linux:**
```bash
make build-local
```

**Windows:**
```powershell
sam build --use-container --parallel --cached --parameter-overrides "Architecture=x86_64 AlarmEmail="
```

SAM pulls a Python 3.12 container and installs the dependencies into a Lambda
layer. This takes a few minutes on the first run; subsequent builds use the
cache and complete in seconds.

You should see `Build Succeeded` at the end.

### Step 3 — Deploy (first time)

**macOS / Linux / Windows:**
```bash
sam deploy --guided
```

You will be asked a series of questions. Use these answers:

```
Stack Name [ai-lambda-backend]:          ai-lambda-backend
AWS Region [ap-southeast-2]:                  ap-southeast-2          # or your preferred region
Parameter AlarmEmail []:                 you@example.com    # optional, press Enter to skip
Parameter Architecture [x86_64]:         x86_64             # press Enter
Confirm changes before deploy [Y/n]:     y
Allow SAM CLI IAM role creation [Y/n]:   y
Disable rollback [y/N]:                  N
Save arguments to configuration file:    Y
SAM configuration file [samconfig.toml]: samconfig.toml
SAM configuration environment [default]: default
```

SAM creates an S3 bucket automatically, packages the code, and deploys the
CloudFormation stack. After 2–3 minutes you will see:

```
CloudFormation outputs from deployed stack
------------------------------------------
Key   ApiBaseUrl
Value https://xxxxxxxxxx.execute-api.ap-southeast-2.amazonaws.com

Key   OpenAISecretArn
Value arn:aws:secretsmanager:ap-southeast-2:123456789012:secret:ai-lambda-backend/openai-api-key-XXXXXX
```

**Save the `ApiBaseUrl` and `OpenAISecretArn` values.** You will need them in
the next steps.

### Step 4 — Store your OpenAI API key

The stack created a Secrets Manager secret with a placeholder value. Replace
it with your real key.

**macOS / Linux / Windows:**
```bash
aws secretsmanager put-secret-value \
  --secret-id "PASTE_YOUR_OpenAISecretArn_HERE" \
  --secret-string "{\"openai_api_key\": \"sk-proj-YOUR_KEY_HERE\"}"
```

Replace `PASTE_YOUR_OpenAISecretArn_HERE` with the ARN from step 3, and
`sk-proj-YOUR_KEY_HERE` with your actual OpenAI API key.

**macOS / Linux only** (interactive helper):
```bash
make update-secret
# prompts for the key and updates the secret automatically
```

### Step 5 — Test your endpoints

Replace the URL with your actual `ApiBaseUrl` from step 3.

**Health check:**
```bash
curl "https://xxxxxxxxxx.execute-api.ap-southeast-2.amazonaws.com/health"
# {"status": "healthy", "service": "ai-lambda-backend", "version": "1.0.0"}
```

**Chat:**
```bash
curl -X POST "https://xxxxxxxxxx.execute-api.ap-southeast-2.amazonaws.com/chat" \
  -H "Content-Type: application/json" \
  -d "{\"messages\": [{\"role\": \"user\", \"content\": \"Hello! What can you do?\"}]}"
# {"message": "I can help you with...", "usage": {...}, "model": "gpt-4o-mini"}
```

That's it — your AI backend is live.

---

## Configuration

All configuration is done through environment variables defined in
`template.yaml`. You can override any of them at deploy time.

### ChatFunction environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY_SECRET_ARN` | *(set by SAM)* | ARN of the Secrets Manager secret. Do not change. |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use. E.g. `gpt-4o`, `gpt-4-turbo`. |
| `OPENAI_MAX_TOKENS` | `2048` | Maximum tokens in the completion response. |
| `OPENAI_TEMPERATURE` | `0.7` | Sampling temperature (0.0 – 2.0). |

To change a default, edit the `Environment` block under `ChatFunction` in
`template.yaml`, then redeploy.

### Powertools (global)

| Variable | Value |
|----------|-------|
| `POWERTOOLS_SERVICE_NAME` | `ai-lambda-backend` |
| `POWERTOOLS_LOG_LEVEL` | `INFO` |
| `POWERTOOLS_METRICS_NAMESPACE` | `AILambdaBackend` |

### Overriding per-request

Clients can override `model`, `max_tokens`, and `temperature` in the request
body:

```json
{
  "messages": [{"role": "user", "content": "Summarise this text..."}],
  "model": "gpt-4o",
  "max_tokens": 512,
  "temperature": 0.3
}
```

---

## Request & response format

### `POST /chat`

**Request body**

```json
{
  "messages": [
    {"role": "system",    "content": "You are a helpful assistant."},
    {"role": "user",      "content": "What is the capital of France?"},
    {"role": "assistant", "content": "Paris."},
    {"role": "user",      "content": "And of Germany?"}
  ],
  "model":       "gpt-4o-mini",
  "max_tokens":  256,
  "temperature": 0.5
}
```

`messages` is required; the rest are optional.
Valid roles: `system`, `user`, `assistant`.

**Success response — 200**

```json
{
  "message": "The capital of Germany is Berlin.",
  "usage": {
    "prompt_tokens":     42,
    "completion_tokens": 10,
    "total_tokens":      52
  },
  "model": "gpt-4o-mini"
}
```

**Error responses**

| Status | Cause |
|--------|-------|
| 400 | `messages` missing, empty, wrong roles, or empty content |
| 503 | OpenAI rate limit, connection error, or API error |

### `GET /health`

**Response — 200**

```json
{
  "status":  "healthy",
  "service": "ai-lambda-backend",
  "version": "1.0.0"
}
```

---

## Local development

### Install dev dependencies

```bash
pip install -r requirements-dev.txt
```

### Run unit tests

All tests run offline with mocked AWS and OpenAI clients — no credentials or
Docker required.

**macOS / Linux:**
```bash
make test
```

**Windows:**
```powershell
python -m pytest tests/ -v --tb=short
```

### Run tests with coverage

**macOS / Linux:**
```bash
make test-cov
```

**Windows:**
```powershell
python -m pytest tests/ -v --tb=short --cov=src --cov-report=term-missing --cov-report=html
```

### Lint and format

**macOS / Linux:**
```bash
make lint         # flake8
make format       # black (modifies files)
make format-check # black dry-run (CI-safe)
```

**Windows:**
```powershell
python -m flake8 src/ tests/ --max-line-length=120
python -m black src/ tests/ --line-length=120
python -m black src/ tests/ --line-length=120 --check
```

### Local invoke with SAM (requires Docker + real AWS secret)

Copy the example env file and fill in your real Secrets Manager ARN:

**macOS / Linux:**
```bash
cp env.json.example env.json
```

**Windows:**
```powershell
copy env.json.example env.json
```

Then edit `env.json` and replace the placeholder ARN with your real one from
the deploy output.

**Invoke functions locally:**

**macOS / Linux:**
```bash
make invoke-health
make invoke-chat
```

**Windows:**
```powershell
sam local invoke HealthFunction --event events/health_request.json --env-vars env.json --config-env local
sam local invoke ChatFunction --event events/chat_request.json --env-vars env.json --config-env local
```

**Start a full local HTTP server:**

**macOS / Linux:**
```bash
make local-api
```

**Windows:**
```powershell
sam local start-api --env-vars env.json --port 3000 --config-env local
```

Then test it:
```bash
curl http://localhost:3000/health
curl -X POST http://localhost:3000/chat -H "Content-Type: application/json" -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}]}"
```

> **Note:** `env.json` is listed in `.gitignore` — it will never be committed.
> The `env.json.example` file shows the expected shape.

---

## Redeploying after changes

After the first guided deploy, `samconfig.toml` stores your settings. All
future deployments are:

**macOS / Linux:**
```bash
make build-local && sam deploy
```

**Windows:**
```powershell
sam build --use-container --parallel --cached --parameter-overrides "Architecture=x86_64 AlarmEmail="
sam deploy
```

> Both build and deploy use x86_64 — no architecture mismatch, no emulation needed.

---

## Monitoring

### CloudWatch Dashboard

AWS Console → CloudWatch → Dashboards → `ai-lambda-backend-dashboard`

The dashboard shows:
- **Invocations** — both functions, 1-minute resolution
- **Errors** — both functions
- **Throttles** — ChatFunction
- **Duration P50 / P99** — ChatFunction
- **Error rate %** — metric math expression
- **Cold starts** — via EMF (Embedded Metrics Format)
- **API Gateway latency** — P50 and P99
- **Tokens used** — custom EMF metric

### CloudWatch Alarms

Three alarms are created automatically. They publish to the `AlarmTopic` SNS
topic. If you provided an `AlarmEmail` at deploy time, you will receive email
notifications.

| Alarm | Threshold |
|-------|-----------|
| `ai-lambda-backend-error-rate-high` | Error rate > 5% over 5 minutes |
| `ai-lambda-backend-throttles` | Any throttle events in 5 minutes |
| `ai-lambda-backend-p99-duration-high` | P99 duration > 48 000 ms |

### X-Ray traces

AWS Console → X-Ray → Traces — filter by service name `ai-lambda-backend`.

Each `POST /chat` trace includes:
- Total Lambda duration (including cold start)
- Secrets Manager call (cold start only)
- OpenAI API call duration
- Annotations: `model`, `message_count`

### Tailing logs in real time

**macOS / Linux:**
```bash
make logs-chat
make logs-health
```

**Windows:**
```powershell
sam logs -n ChatFunction --stack-name ai-lambda-backend --region ap-southeast-2 --tail
sam logs -n HealthFunction --stack-name ai-lambda-backend --region ap-southeast-2 --tail
```

---

## Cost estimate

The following is an **approximate** estimate for moderate traffic. Actual costs
depend on your region, traffic pattern, and OpenAI usage.

| Service | Free tier | After free tier |
|---------|-----------|-----------------|
| Lambda | 1M requests/month | ~$0.20 per 1M requests |
| API Gateway HTTP API | 1M requests/month | ~$1.00 per 1M requests |
| Secrets Manager | 10 000 API calls/month free | $0.05 per 10 000 calls after |
| CloudWatch Logs | 5 GB/month | $0.50 per GB |
| X-Ray | 100 000 traces/month | $5.00 per 1M traces |
| OpenAI | — | Varies by model & tokens |

For low-traffic personal or hobby projects the AWS costs are effectively zero
within the free tier.

---

## Project structure

```
ai-lambda-backend/
├── LICENSE                         # MIT
├── README.md                       # This file
├── template.yaml                   # SAM — all AWS resources
├── samconfig.toml                  # SAM deploy defaults (x86_64)
├── Makefile                        # Developer shortcuts (macOS/Linux)
├── requirements-dev.txt            # Test & lint dependencies
├── env.json.example                # Template for local invoke env overrides
├── .gitignore
│
├── src/
│   ├── handlers/
│   │   ├── chat.py                 # POST /chat
│   │   └── health.py              # GET /health
│   └── shared/
│       └── openai_client.py       # OpenAI singleton (cold-start init)
│
├── layers/
│   └── dependencies/
│       └── requirements.txt       # Packaged into Lambda layer
│
├── events/
│   ├── chat_request.json          # HTTP API v2 test event for /chat
│   └── health_request.json        # HTTP API v2 test event for /health
│
└── tests/
    └── unit/
        ├── test_chat.py           # 9 tests — success, validation, OpenAI errors
        └── test_health.py         # 2 tests — status, response shape
```

---

## Customisation guide

### Change the OpenAI model

Edit `template.yaml`, find the `ChatFunction` environment variables, and
update `OPENAI_MODEL`:

```yaml
OPENAI_MODEL: gpt-4o
```

Then rebuild and redeploy.

### Add authentication

Add a Lambda authorizer or a JWT authorizer to `BackendHttpApi` in
`template.yaml`. See the
[SAM HTTP API auth docs](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-property-httpapi-httpapiauth.html).

### Restrict CORS to your domain

Change the `AllowOrigins` list in `BackendHttpApi`:

```yaml
CorsConfiguration:
  AllowOrigins:
    - "https://yourapp.com"
```

### Add a new endpoint

1. Create `src/handlers/yourhandler.py` following the same pattern as `health.py`.
2. Add a `YourFunction` resource in `template.yaml` with an `HttpApi` event.
3. Write tests in `tests/unit/test_yourhandler.py`.
4. Rebuild and redeploy.

### Cap Lambda concurrency (control OpenAI costs)

Add `ReservedConcurrentExecutions` to `ChatFunction` in `template.yaml`:

```yaml
ReservedConcurrentExecutions: 10
```

This limits simultaneous OpenAI calls to 10, bounding your maximum spend rate.

### Enable email alerts

Redeploy passing your email as a parameter:

```bash
sam deploy --parameter-overrides "Architecture=x86_64 AlarmEmail=you@example.com"
```

You will receive a confirmation email from AWS SNS. Click the confirmation
link, then alarms will start sending notifications.

---

## Tearing down

To delete all AWS resources created by this stack:

```bash
aws cloudformation delete-stack --stack-name ai-lambda-backend
```

This removes the Lambda functions, API Gateway, IAM role, SNS topic, alarms,
and dashboard. The Secrets Manager secret and SAM S3 bucket may need to be
deleted manually if they have deletion protection or retention policies.

---

## Contributing

Contributions are welcome. To contribute:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feat/your-feature`.
3. Make your changes and add tests.
4. Ensure all tests pass:
   - macOS/Linux: `make test`
   - Windows: `python -m pytest tests/ -v --tb=short`
5. Ensure code is formatted:
   - macOS/Linux: `make format-check`
   - Windows: `python -m black src/ tests/ --line-length=120 --check`
6. Open a pull request with a clear description of the change.

Please keep pull requests focused. One feature or fix per PR.

---

## License

MIT — see [LICENSE](LICENSE).

You are free to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of this software for any purpose, commercial or otherwise,
with no restrictions beyond preserving the copyright notice.
