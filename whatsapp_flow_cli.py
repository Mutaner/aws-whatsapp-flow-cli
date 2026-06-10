#!/usr/bin/env python3
"""
whatsapp_flow_cli.py — AWS WhatsApp Flow API CLI

CLI tool for AWS End User Messaging Social API (WhatsApp Business Platform).

Commands:
  send-message   — Send a WhatsApp message
  create-flow    — Create a new WhatsApp Flow
  list-flows     — List all WhatsApp Flows for a WABA

Dependencies: boto3>=1.43.25 (pip install -r requirements.txt)

Examples:
  python3 whatsapp_flow_cli.py --region us-east-1 send-message \\
      --origination-phone-number-id phone-number-id-xxx \\
      --message '{"text":{"body":"Hello!"}}' \\
      --meta-api-version v22.0

  python3 whatsapp_flow_cli.py --region us-east-1 create-flow \\
      --id waba-xxx --flow-name "Booking" \\
      --categories APPOINTMENT_BOOKING --publish

  python3 whatsapp_flow_cli.py --region us-east-1 list-flows --id waba-xxx
"""

import argparse
import json
import logging
import sys
import textwrap
import traceback
from typing import Any, Dict

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    NoRegionError,
    ParamValidationError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SERVICE_NAME = "socialmessaging"
DEFAULT_META_API_VERSION = "v22.0"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1

BOTO_TIMEOUT_CONFIG = BotoConfig(
    connect_timeout=10,
    read_timeout=30,
    retries={"max_attempts": 3},
)

# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------


def _friendly_error(msg: str, detail: str = "") -> str:
    parts = [f"[ERROR] {msg}"]
    if detail:
        parts.append(detail)
    return "\n".join(parts)


def _handle_boto3_error(e: Exception) -> str:
    if isinstance(e, NoCredentialsError):
        return _friendly_error(
            "AWS credentials not found.",
            "Check ~/.aws/credentials or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY.",
        )
    if isinstance(e, NoRegionError):
        return _friendly_error(
            "AWS region not specified.",
            "Pass --region or set AWS_DEFAULT_REGION.",
        )
    if isinstance(e, ParamValidationError):
        return _friendly_error(
            "Parameter validation failed.",
            str(e),
        )
    if isinstance(e, ClientError):
        code = e.response["Error"]["Code"]
        message = e.response["Error"]["Message"]
        http_status = e.response["ResponseMetadata"]["HTTPStatusCode"]
        known_codes = {
            "AccessDeniedException": "Permission denied. Check IAM policy.",
            "ResourceNotFoundException": "Resource not found. Verify account/phone IDs.",
            "ValidationException": "Invalid input data. Check parameter format.",
            "ThrottlingException": "Rate limit exceeded. Wait and retry.",
            "InternalServerException": "AWS internal error. Retry later.",
            "TooManyRequestsException": "Too many requests. Use exponential backoff.",
        }
        hint = known_codes.get(code, f"AWS error code: {code}")
        return _friendly_error(
            f"AWS returned an error (HTTP {http_status})",
            f"{hint}\nDetails: {message}",
        )
    if isinstance(e, BotoCoreError):
        return _friendly_error(
            "Internal boto3/AWS SDK error.",
            str(e),
        )
    return _friendly_error(
        f"Unknown error ({type(e).__name__})",
        str(e) if str(e) else traceback.format_exc(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_empty_listing(result: Any, action: str) -> bool:
    """Check if API returned an empty list for listing operations."""
    if action not in ("list-flows",):
        return False
    if not isinstance(result, dict):
        return False
    for key in ("Flows",):
        if key in result and isinstance(result[key], list) and len(result[key]) == 0:
            return True
    return False


def _setup_debug_logging() -> None:
    """Enable boto3 debug logging via modern API.

    WARNING: Debug mode may print AWS credentials to stdout/stderr.
    Only use in isolated environments.
    """
    print("[WARNING] Debug mode enabled. AWS credentials may appear in logs.", file=sys.stderr)
    logging.basicConfig(level=logging.DEBUG)
    for logger_name in ("boto3", "botocore", "s3transfer", "urllib3"):
        logging.getLogger(logger_name).setLevel(logging.DEBUG)
        logging.getLogger(logger_name).propagate = True


# ---------------------------------------------------------------------------
# Command functions
# ---------------------------------------------------------------------------


def cmd_send_message(client: boto3.client, args: argparse.Namespace) -> Dict[str, Any]:
    """Send a WhatsApp message."""
    # Validate JSON before encoding
    try:
        parsed = json.loads(args.message)
    except json.JSONDecodeError:
        print(
            _friendly_error(
                "--message must be valid JSON.",
                "Example: '{\"text\":{\"body\":\"Hello\"}}'",
            ),
            file=sys.stderr,
        )
        sys.exit(EXIT_FAILURE)

    kwargs: Dict[str, Any] = {
        "originationPhoneNumberId": args.origination_phone_number_id,
        "message": json.dumps(parsed).encode("utf-8"),
        "metaApiVersion": args.meta_api_version,
    }

    return client.send_whatsapp_message(**kwargs)


def cmd_create_flow(client: boto3.client, args: argparse.Namespace) -> Dict[str, Any]:
    """Create a new WhatsApp Flow."""
    kwargs: Dict[str, Any] = {
        "id": args.id,
        "flowName": args.flow_name,
        "categories": args.categories,
    }

    if args.flow_json:
        flow_bytes = args.flow_json.encode("utf-8") if isinstance(args.flow_json, str) else args.flow_json
        kwargs["flowJson"] = flow_bytes

    if args.publish is True:
        kwargs["publish"] = True

    if args.clone_flow_id:
        kwargs["cloneFlowId"] = args.clone_flow_id

    return client.create_whatsapp_flow(**kwargs)


def cmd_list_flows(client: boto3.client, args: argparse.Namespace) -> Dict[str, Any]:
    """List all WhatsApp Flows for a WABA."""
    kwargs: Dict[str, Any] = {"id": args.id}

    if args.starting_token:
        kwargs["nextToken"] = args.starting_token

    if args.max_results:
        kwargs["maxResults"] = args.max_results

    return client.list_whatsapp_flows(**kwargs)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whatsapp_flow_cli",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""\
            CLI tool for AWS End User Messaging Social (WhatsApp Flow).

            Requires Python >= 3.10 and boto3 >= 1.43.25.
            Install: pip install -r requirements.txt

            AWS credentials are resolved from ~/.aws/credentials or
            AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars.
        """),
        epilog=textwrap.dedent("""\
            Examples:
              # Send a text message
              python3 whatsapp_flow_cli.py --region us-east-1 send-message \\
                  --origination-phone-number-id phone-number-id-xxx \\
                  --message '{"text":{"body":"Hello from AWS!"}}' \\
                  --meta-api-version v22.0

              # Create a Flow and publish immediately
              python3 whatsapp_flow_cli.py --region us-east-1 create-flow \\
                  --id waba-xxx --flow-name "Booking" \\
                  --categories APPOINTMENT_BOOKING --publish

              # List all Flows (with pagination)
              python3 whatsapp_flow_cli.py --region us-east-1 list-flows \\
                  --id waba-xxx --max-results 10
        """),
    )

    parser.add_argument("--region", default=None, help="AWS region (e.g. us-east-1)")
    parser.add_argument("--profile", default=None, help="Profile from ~/.aws/credentials")
    parser.add_argument("--endpoint-url", default=None, help="Custom endpoint URL (debugging)")
    parser.add_argument("--debug", action="store_true", help="Enable boto3 debug logging")

    subparsers = parser.add_subparsers(dest="action", required=True, help="Available actions")

    # send-message
    send_parser = subparsers.add_parser("send-message", help="Send a WhatsApp message")
    send_parser.add_argument(
        "--origination-phone-number-id", required=True,
        help="Origination phone number ID (phone-number-id-... or ARN)",
    )
    send_parser.add_argument(
        "--message", required=True,
        help="JSON message body (WhatsApp Cloud API format)",
    )
    send_parser.add_argument(
        "--meta-api-version", default=DEFAULT_META_API_VERSION,
        help=f"Meta API version (default: {DEFAULT_META_API_VERSION})",
    )

    # create-flow
    create_parser = subparsers.add_parser("create-flow", help="Create a new WhatsApp Flow")
    create_parser.add_argument("--id", required=True, help="WhatsApp Business Account ID (waba-...)")
    create_parser.add_argument("--flow-name", required=True, help="Flow name (unique within WABA)")
    create_parser.add_argument(
        "--categories", required=True, nargs="+",
        choices=[
            "SIGN_UP", "SIGN_IN", "APPOINTMENT_BOOKING", "LEAD_GENERATION",
            "SHOPPING", "CONTACT_US", "CUSTOMER_SUPPORT", "SURVEY", "OTHER",
        ],
        help="Flow categories (specify one or more)",
    )
    create_parser.add_argument("--flow-json", default=None, help="Flow JSON definition (optional)")
    create_parser.add_argument("--publish", action="store_true", help="Publish Flow after creation")
    create_parser.add_argument("--clone-flow-id", default=None, help="Existing Flow ID to clone")

    # list-flows
    list_parser = subparsers.add_parser("list-flows", help="List WhatsApp Flows")
    list_parser.add_argument("--id", required=True, help="WhatsApp Business Account ID (waba-...)")
    list_parser.add_argument("--starting-token", default=None, help="Pagination token (nextToken)")
    list_parser.add_argument("--max-results", type=int, default=None, help="Max results (1-1000)")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    session_kwargs: Dict[str, Any] = {}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    if args.region:
        session_kwargs["region_name"] = args.region

    try:
        session = boto3.Session(**session_kwargs)
    except Exception as e:
        print(_friendly_error("Failed to create AWS session.", str(e)), file=sys.stderr)
        return EXIT_FAILURE

    client_kwargs: Dict[str, Any] = {
        "service_name": SERVICE_NAME,
        "config": BOTO_TIMEOUT_CONFIG,
    }
    if args.endpoint_url:
        client_kwargs["endpoint_url"] = args.endpoint_url
    if args.debug:
        _setup_debug_logging()

    try:
        client = session.client(**client_kwargs)
    except Exception as e:
        print(_friendly_error("Failed to create boto3 client.", str(e)), file=sys.stderr)
        return EXIT_FAILURE

    action_map: Dict[str, Any] = {
        "send-message": cmd_send_message,
        "create-flow": cmd_create_flow,
        "list-flows": cmd_list_flows,
    }

    handler = action_map.get(args.action)
    if handler is None:
        print(_friendly_error(f"Unknown action: {args.action}"), file=sys.stderr)
        return EXIT_FAILURE

    try:
        result = handler(client, args)
    except SystemExit:
        return EXIT_FAILURE
    except Exception as e:
        print(_handle_boto3_error(e), file=sys.stderr)
        return EXIT_FAILURE

    if isinstance(result, str):
        print(result, file=sys.stderr)
        return EXIT_FAILURE

    preview = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    if _is_empty_listing(result, args.action):
        print("[INFO] No resources found. API returned an empty list.", file=sys.stderr)
    print(preview)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())