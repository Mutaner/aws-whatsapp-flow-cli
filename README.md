# WhatsApp Flow CLI

**Bridge the gap between AWS End User Messaging Social and your terminal.**

> ⚡ **June 2026**: AWS just shipped the `socialmessaging` service with WhatsApp Flow APIs. The SDK is brand new — community tooling, examples, and best practices don't exist yet. This CLI fills that gap.

## Description

`whatsapp-flow-cli` is a production-ready command-line tool for managing WhatsApp Business Flows through the **AWS End User Messaging Social API** (`socialmessaging`). It wraps `boto3` with sane defaults, human-readable error messages, and zero-traceback output.

**Why this exists:** The `socialmessaging` service was released in mid-2026. While `boto3 >= 1.43.25` has the methods, there are no third-party CLI wrappers, no StackOverflow examples, and no pre-built workflows. This tool gives you day-zero access to the API without reading raw AWS docs.

### Features

- **send-message** — Send WhatsApp messages (text, media, interactive) through AWS
- **create-flow** — Create interactive WhatsApp Flows (lead gen, booking, surveys, etc.)
- **list-flows** — List all Flows for a WhatsApp Business Account with pagination
- **Zero-Traceback** — Every AWS error is parsed into a clean `[ОШИБКА]` message (or English-equivalent JSON)
- **Network-safe** — 10s connect timeout, 30s read timeout, 3 retries on all API calls

## Installation

```bash
pip install "boto3>=1.43.25"
```

Python 3.10+ required.

## Authentication

Credentials are resolved via the standard AWS credential chain:

1. `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` environment variables
2. `~/.aws/credentials` (default profile or `--profile` flag)
3. IAM role (if running on EC2/ECS/Lambda)

```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1

# Option 2: Named profile
python3 whatsapp_flow_cli.py --profile prod ...
```

## Usage

### Send a WhatsApp message

```bash
python3 whatsapp_flow_cli.py \
    --region us-east-1 \
    send-message \
    --origination-phone-number-id phone-number-id-01234567890123456789012345678901 \
    --message '{"text":{"body":"Hello from AWS!"}}' \
    --meta-api-version v22.0
```

### Create a WhatsApp Flow

```bash
python3 whatsapp_flow_cli.py \
    --region us-east-1 \
    create-flow \
    --id waba-012345678901234 \
    --flow-name "Customer Support" \
    --categories CUSTOMER_SUPPORT \
    --publish
```

### List all Flows (with pagination)

```bash
python3 whatsapp_flow_cli.py \
    --region us-east-1 \
    list-flows \
    --id waba-012345678901234 \
    --max-results 10
```

### Additional options

| Flag | Description |
|------|-------------|
| `--profile` | AWS credential profile name |
| `--endpoint-url` | Custom API endpoint (debugging) |
| `--debug` | Enable boto3 debug logging |

## Error Handling

This tool never prints Python tracebacks. All errors are caught, parsed, and displayed as structured messages:

```
[ОШИБКА] Доступ запрещён. У IAM-пользователя/роли нет прав на эту операцию.
Детали: User: arn:aws:iam::123456789012:user/bot is not authorized to perform: socialmessaging:SendWhatsAppMessage
```

Error types handled explicitly:

| AWS Error | User-friendly message |
|-----------|---------------------|
| `AccessDeniedException` | Permission denied — check IAM policy |
| `ResourceNotFoundException` | Resource not found — verify IDs |
| `ValidationException` | Invalid input — check parameter format |
| `ThrottlingException` | Rate limit exceeded — retry with backoff |
| `TooManyRequestsException` | Too many requests — use exponential backoff |
| `InternalServerException` | AWS internal error — retry later |

For list commands, empty results show `[INFO] Ресурсы не найдены. API вернул пустой список.` before the JSON output.

## Commercial Support

Need a custom integration, multi-account deployment, or CI/CD pipeline for your WhatsApp business?

📧 **Email**: [alex.o.europe@gmail.com]  
🔧 **One-time setup**: $200–$500 per script  
📋 **Enterprise consulting**: Custom integrations, IAM policies, monitoring dashboards

This tool is part of the **AWS New-API Gap Filler** collection — bridging the gap between AWS API releases and community tooling since June 2026.

---

*Made for the AWS End User Messaging Social API (June 2026 release)*
