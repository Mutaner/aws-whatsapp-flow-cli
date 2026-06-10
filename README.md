# WhatsApp Flow CLI

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![AWS](https://img.shields.io/badge/aws-socialmessaging-orange.svg)

**Bridge the gap between AWS End User Messaging Social and your terminal.**

> ⚡ **June 2026**: AWS just shipped the `socialmessaging` service with WhatsApp Flow APIs.
> The SDK is brand new — community tooling, examples, and best practices don't exist yet.
> This CLI fills that gap.

## Description

`whatsapp-flow-cli` is a production-ready command-line tool for managing WhatsApp Business
Flows through the **AWS End User Messaging Social API** (`socialmessaging`). It wraps `boto3`
with sane defaults, human-readable error messages, and zero-traceback output.

### Features

- **send-message** — Send WhatsApp messages (text, media, interactive) through AWS
- **create-flow** — Create interactive WhatsApp Flows (lead gen, booking, surveys, etc.)
- **list-flows** — List all Flows for a WhatsApp Business Account with pagination
- **Zero-Traceback** — Every AWS error is parsed into clean structured output
- **Network-safe** — 10s connect timeout, 30s read timeout, 3 retries on all API calls

## Installation

```bash
pip install -r requirements.txt
```

Python 3.10+ required.

## Quick Start

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

### List all Flows

```bash
python3 whatsapp_flow_cli.py \
    --region us-east-1 \
    list-flows \
    --id waba-012345678901234 \
    --max-results 10
```

### Pipe through `jq` (pretty-print JSON)

```bash
python3 whatsapp_flow_cli.py \
    --region us-east-1 \
    list-flows --id waba-xxx --max-results 5 \
    | jq '.Flows[] | {id: .FlowId, name: .Name, status: .Status}'
```

### Example JSON output

```json
{
  "Flows": [
    {
      "FlowId": "1234567890",
      "Name": "Customer Support",
      "Status": "PUBLISHED",
      "Categories": ["CUSTOMER_SUPPORT"],
      "CreatedAt": "2026-06-10T12:00:00Z"
    }
  ],
  "NextToken": null
}
```

## Authentication

Credentials follow the standard AWS credential chain:

1. `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` environment variables
2. `~/.aws/credentials` (default or `--profile` flag)
3. IAM role on EC2/ECS/Lambda

```bash
# Named profile
python3 whatsapp_flow_cli.py --profile prod --region eu-west-1 list-flows --id waba-xxx
```

## CLI Options

| Flag | Description |
|------|-------------|
| `--region` | AWS region (e.g., us-east-1) |
| `--profile` | AWS credential profile name |
| `--endpoint-url` | Custom API endpoint (debugging) |
| `--debug` | Enable boto3 debug logging |

## Error Handling

This tool never prints Python tracebacks. All errors are parsed to clean output:

```text
[ОШИБКА] Access denied. Check IAM policy.
Details: User: arn:aws:iam::123... is not authorized to perform: socialmessaging:SendWhatsAppMessage
```

| AWS Error | User-friendly message |
|-----------|----------------------|
| `AccessDeniedException` | Permission denied — check IAM policy |
| `ResourceNotFoundException` | Resource not found — verify IDs |
| `ValidationException` | Invalid input — check parameter format |
| `ThrottlingException` | Rate limit exceeded — retry with backoff |
| `TooManyRequestsException` | Too many requests — use exponential backoff |
| `InternalServerException` | AWS internal error — retry later |

Empty results print `[INFO] No resources found.` before the JSON.

## Contact & Support

Questions, feature requests, or enterprise integrations?

📧 **alex.o.europe@gmail.com**

---

*Part of the AWS New-API Gap Filler collection — June 2026.*