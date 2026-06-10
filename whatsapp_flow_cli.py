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
import sys
import textwrap
import traceback

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    NoRegionError,
    ParamValidationError,
)

# Типы для type hints (Python 3.10+)
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------
SERVICE_NAME = "socialmessaging"
DEFAULT_META_API_VERSION = "v22.0"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1

# Таймауты для boto3-клиента (сек)
BOTO_TIMEOUT_CONFIG = BotoConfig(
    connect_timeout=10,
    read_timeout=30,
    retries={"max_attempts": 3},
)

# ---------------------------------------------------------------------------
# Форматирование ошибок
# ---------------------------------------------------------------------------

def _friendly_error(msg: str, detail: str = "") -> str:
    """Обёртка: человекочитаемая ошибка с деталями."""
    parts = [f"[ОШИБКА] {msg}"]
    if detail:
        parts.append(detail)
    return "\n".join(parts)


def _handle_boto3_error(e: Exception) -> str:
    """Превращает boto3-исключение в человекочитаемое сообщение."""

    if isinstance(e, NoCredentialsError):
        return _friendly_error(
            "Учётные данные AWS не найдены.",
            "Проверьте ~/.aws/credentials или переменные AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY.",
        )
    if isinstance(e, NoRegionError):
        return _friendly_error(
            "Регион AWS не указан.",
            "Передайте --region или установите AWS_DEFAULT_REGION.",
        )
    if isinstance(e, ParamValidationError):
        return _friendly_error(
            "Ошибка валидации параметров запроса.",
            str(e),
        )
    if isinstance(e, ClientError):
        code = e.response["Error"]["Code"]
        message = e.response["Error"]["Message"]
        http_status = e.response["ResponseMetadata"]["HTTPStatusCode"]

        # Карта типичных AWS-кодов → человекочитаемые подсказки
        known_codes = {
            "AccessDeniedException": (
                "Доступ запрещён. У IAM-пользователя/роли нет прав на эту операцию."
            ),
            "ResourceNotFoundException": (
                "Указанный ресурс не найден. Проверьте ID аккаунта/номера телефона."
            ),
            "ValidationException": (
                "Ошибка валидации входных данных. Проверьте формат параметров."
            ),
            "ThrottlingException": (
                "Превышен лимит запросов. Подождите и повторите."
            ),
            "InternalServerException": (
                "Внутренняя ошибка AWS. Повторите запрос позже."
            ),
            "TooManyRequestsException": (
                "Слишком много запросов. Используйте экспоненциальную задержку."
            ),
        }

        hint = known_codes.get(code, f"Код ошибки AWS: {code}")
        return _friendly_error(
            f"AWS вернул ошибку (HTTP {http_status})",
            f"{hint}\nДетали: {message}",
        )
    if isinstance(e, BotoCoreError):
        return _friendly_error(
            "Внутренняя ошибка boto3/AWS SDK.",
            str(e),
        )

    # Любая другая неожиданная ошибка
    return _friendly_error(
        f"Неизвестная ошибка ({type(e).__name__})",
        str(e) if str(e) else traceback.format_exc(),
    )


# ---------------------------------------------------------------------------
# Функции-действия (actions)
# ---------------------------------------------------------------------------


def _is_empty_listing(result: Any, action: str) -> bool:
    """Проверяет, вернул ли API пустой список для операций листинга.

    Проверяет ключи: Sessions, KnowledgeBaseSummaries, Flows, Ids.
    Возвращает True, если такой ключ есть и значение — пустой список.
    """
    if action not in ("list-sessions", "list-kbs", "list-flows"):
        return False
    if not isinstance(result, dict):
        return False
    for key in ("Sessions", "KnowledgeBaseSummaries", "Flows", "Ids"):
        if key in result and isinstance(result[key], list) and len(result[key]) == 0:
            return True
    return False


def action_send_message(client: boto3.client, args: argparse.Namespace) -> dict:
    """Отправить WhatsApp-сообщение."""
    kwargs = {
        "originationPhoneNumberId": args.origination_phone_number_id,
        "message": args.message,
        "metaApiVersion": args.meta_api_version,
    }

    # message можно передать как JSON-строку → boto3 ждёт bytes
    if isinstance(kwargs["message"], str):
        kwargs["message"] = kwargs["message"].encode("utf-8")

    return client.send_whatsapp_message(**kwargs)


def action_create_flow(client: boto3.client, args: argparse.Namespace) -> dict:
    """Создать новый WhatsApp Flow."""
    kwargs: dict = {
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


def action_list_flows(client: boto3.client, args: argparse.Namespace) -> dict:
    """Список всех WhatsApp Flows для WABA."""
    kwargs: dict = {"id": args.id}

    if args.starting_token:
        kwargs["nextToken"] = args.starting_token

    if args.max_results:
        kwargs["maxResults"] = args.max_results

    return client.list_whatsapp_flows(**kwargs)


# ---------------------------------------------------------------------------
# Разбор аргументов (argparse)
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Формирует дерево argparse."""
    parser = argparse.ArgumentParser(
        prog="whatsapp_flow_cli",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""\
            CLI-инструмент для AWS End User Messaging Social (WhatsApp Flow).

            Требуется Python ≥ 3.10 и boto3 ≥ 1.43.25.
            Установка зависимостей:
              pip install boto3>=1.43.25

            Учётные данные AWS берутся из ~/.aws/credentials или переменных
            окружения AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY.
        """),
        epilog=textwrap.dedent("""\
            Примеры:
              # Отправить текстовое сообщение
              python3 whatsapp_flow_cli.py --region us-east-1 send-message \\
                  --origination-phone-number-id phone-number-id-xxx \\
                  --message '{"text":{"body":"Hello from AWS!"}}' \\
                  --meta-api-version v22.0

              # Создать Flow и сразу опубликовать
              python3 whatsapp_flow_cli.py --region us-east-1 create-flow \\
                  --id waba-xxx --flow-name "Booking" \\
                  --categories APPOINTMENT_BOOKING --publish

              # Список всех Flow (с пагинацией)
              python3 whatsapp_flow_cli.py --region us-east-1 list-flows \\
                  --id waba-xxx --max-results 10
        """),
    )

    # ---- Глобальные параметры (доступны всем командам) ----
    parser.add_argument("--region", default=None, help="AWS-регион (например, us-east-1)")
    parser.add_argument("--profile", default=None, help="Профиль из ~/.aws/credentials")
    parser.add_argument("--endpoint-url", default=None, help="Кастомный endpoint URL (для отладки)")
    parser.add_argument("--debug", action="store_true", help="Включить debug-логирование boto3")

    # ---- Сабпарсеры (действия) ----
    subparsers = parser.add_subparsers(dest="action", required=True, help="Доступные действия")

    # --- send-message ---
    send_parser = subparsers.add_parser(
        "send-message", help="Отправить WhatsApp-сообщение"
    )
    send_parser.add_argument(
        "--origination-phone-number-id", required=True,
        help="ID исходящего номера (phone-number-id-... или ARN)",
    )
    send_parser.add_argument(
        "--message", required=True,
        help="JSON-тело сообщения (формат WhatsApp Cloud API)",
    )
    send_parser.add_argument(
        "--meta-api-version", default=DEFAULT_META_API_VERSION,
        help=f"Версия Meta API (по умолчанию: {DEFAULT_META_API_VERSION})",
    )

    # --- create-flow ---
    create_parser = subparsers.add_parser(
        "create-flow", help="Создать новый WhatsApp Flow"
    )
    create_parser.add_argument("--id", required=True, help="WhatsApp Business Account ID (waba-...)")
    create_parser.add_argument("--flow-name", required=True, help="Название Flow (уникальное в рамках WABA)")
    create_parser.add_argument(
        "--categories", required=True, nargs="+",
        choices=[
            "SIGN_UP", "SIGN_IN", "APPOINTMENT_BOOKING", "LEAD_GENERATION",
            "SHOPPING", "CONTACT_US", "CUSTOMER_SUPPORT", "SURVEY", "OTHER",
        ],
        help="Категории Flow (можно указать несколько)",
    )
    create_parser.add_argument("--flow-json", default=None, help="JSON-определение Flow (опционально)")
    create_parser.add_argument("--publish", action="store_true", help="Опубликовать Flow после создания")
    create_parser.add_argument("--clone-flow-id", default=None, help="ID существующего Flow для клонирования")

    # --- list-flows ---
    list_parser = subparsers.add_parser(
        "list-flows", help="Список WhatsApp Flows"
    )
    list_parser.add_argument("--id", required=True, help="WhatsApp Business Account ID (waba-...)")
    list_parser.add_argument("--starting-token", default=None, help="Токен пагинации (nextToken)")
    list_parser.add_argument("--max-results", type=int, default=None, help="Макс. результатов (1-1000)")

    return parser


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def _setup_debug_logging() -> None:
    """Включает debug-логирование boto3 через современный API.

    ВНИМАНИЕ: debug-режим может вывести AWS credentials в stdout.
    Используйте только в изолированных средах.
    """
    logging.basicConfig(level=logging.DEBUG)
    for logger_name in ("boto3", "botocore", "s3transfer", "urllib3"):
        logging.getLogger(logger_name).setLevel(logging.DEBUG)
        logging.getLogger(logger_name).propagate = True


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # ---- Сессия boto3 ----
    session_kwargs: dict = {}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    if args.region:
        session_kwargs["region_name"] = args.region

    try:
        session = boto3.Session(**session_kwargs)
    except Exception as e:
        print(_friendly_error("Не удалось создать AWS-сессию.", str(e)), file=sys.stderr)
        return EXIT_FAILURE

    # ---- Клиент socialmessaging ----
    client_kwargs: dict = {
        "service_name": SERVICE_NAME,
        "config": BOTO_TIMEOUT_CONFIG,
    }
    if args.endpoint_url:
        client_kwargs["endpoint_url"] = args.endpoint_url
    if args.debug:
        import logging
        _setup_debug_logging()

    try:
        client = session.client(**client_kwargs)
    except Exception as e:
        print(_friendly_error("Не удалось создать boto3-клиент.", str(e)), file=sys.stderr)
        return EXIT_FAILURE

    # ---- Диспетчер действий ----
    action_map = {
        "send-message": action_send_message,
        "create-flow": action_create_flow,
        "list-flows": action_list_flows,
    }

    handler = action_map.get(args.action)
    if handler is None:
        print(_friendly_error(f"Неизвестное действие: {args.action}"), file=sys.stderr)
        return EXIT_FAILURE

    try:
        result = handler(client, args)
    except Exception as e:
        print(_handle_boto3_error(e), file=sys.stderr)
        return EXIT_FAILURE

    # ---- Вывод JSON ----
    if isinstance(result, str):
        print(result, file=sys.stderr)
        return EXIT_FAILURE

    preview = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    if _is_empty_listing(result, args.action):
        print("[INFO] Ресурсы не найдены. API вернул пустой список.", file=sys.stderr)
    print(preview)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())