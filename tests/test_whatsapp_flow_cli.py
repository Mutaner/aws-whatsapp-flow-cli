"""Tests for aws-whatsapp-flow-cli."""

import argparse
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure the module can be imported from the parent directory
sys.path.insert(0, "..")

from whatsapp_flow_cli import (
    EXIT_FAILURE,
    EXIT_SUCCESS,
    _friendly_error,
    _is_empty_listing,
    _setup_debug_logging,
    build_parser,
    cmd_create_flow,
    cmd_list_flows,
    cmd_send_message,
    main,
)


# ---------------------------------------------------------------------------
# _friendly_error
# ---------------------------------------------------------------------------

class TestFriendlyError:
    def test_with_msg_only(self):
        result = _friendly_error("Something went wrong.")
        assert result == "[ERROR] Something went wrong."

    def test_with_msg_and_detail(self):
        result = _friendly_error("Failed.", "Check your input.")
        assert result == "[ERROR] Failed.\nCheck your input."

    def test_empty_detail(self):
        result = _friendly_error("Error", "")
        assert result == "[ERROR] Error"


# ---------------------------------------------------------------------------
# _is_empty_listing
# ---------------------------------------------------------------------------

class TestIsEmptyListing:
    def test_empty_flows_list_returns_true(self):
        assert _is_empty_listing({"Flows": []}, "list-flows") is True

    def test_non_empty_flows_list_returns_false(self):
        assert _is_empty_listing({"Flows": [{"FlowId": "1"}]}, "list-flows") is False

    def test_wrong_action_returns_false(self):
        assert _is_empty_listing({"Flows": []}, "send-message") is False

    def test_not_a_dict_returns_false(self):
        assert _is_empty_listing("not a dict", "list-flows") is False
        assert _is_empty_listing(None, "list-flows") is False

    def test_missing_key_returns_false(self):
        assert _is_empty_listing({"Sessions": []}, "list-flows") is False

    def test_flows_is_none_returns_false(self):
        assert _is_empty_listing({"Flows": None}, "list-flows") is False

    def test_non_whatsapp_action_name_returns_false(self):
        assert _is_empty_listing({"Flows": []}, "list-sessions") is False
        assert _is_empty_listing({"Flows": []}, "list-kbs") is False


# ---------------------------------------------------------------------------
# build_parser
# ---------------------------------------------------------------------------

class TestBuildParser:
    def test_parser_created(self):
        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_help_exits_ok(self):
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--help"])
        assert exc.value.code == 0

    def test_missing_action_raises_system_exit(self):
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--region", "us-east-1"])
        assert exc.value.code == 2  # argparse error code

    def test_send_message_minimal_args(self):
        parser = build_parser()
        args = parser.parse_args([
            "send-message",
            "--origination-phone-number-id", "phone-number-id-xxx",
            "--message", '{"text":{"body":"Hi"}}',
        ])
        assert args.action == "send-message"
        assert args.origination_phone_number_id == "phone-number-id-xxx"
        assert args.message == '{"text":{"body":"Hi"}}'

    def test_create_flow_minimal_args(self):
        parser = build_parser()
        args = parser.parse_args([
            "create-flow",
            "--id", "waba-xxx",
            "--flow-name", "Test Flow",
            "--categories", "SURVEY",
        ])
        assert args.action == "create-flow"
        assert args.id == "waba-xxx"
        assert args.flow_name == "Test Flow"
        assert args.categories == ["SURVEY"]

    def test_list_flows_minimal_args(self):
        parser = build_parser()
        args = parser.parse_args([
            "list-flows",
            "--id", "waba-xxx",
        ])
        assert args.action == "list-flows"
        assert args.id == "waba-xxx"

    def test_invalid_category_raises_system_exit(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "create-flow",
                "--id", "waba-xxx",
                "--flow-name", "Bad",
                "--categories", "INVALID_CAT",
            ])

    def test_non_int_max_results_raises_system_exit(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "list-flows",
                "--id", "waba-xxx",
                "--max-results", "not-a-number",
            ])

    def test_debug_flag_default_false(self):
        parser = build_parser()
        args = parser.parse_args(["list-flows", "--id", "waba-xxx"])
        assert args.debug is False

    def test_debug_flag_true(self):
        parser = build_parser()
        args = parser.parse_args(["--debug", "list-flows", "--id", "waba-xxx"])
        assert args.debug is True


# ---------------------------------------------------------------------------
# cmd_send_message
# ---------------------------------------------------------------------------

class TestCmdSendMessage:
    def test_valid_json_message(self):
        client = MagicMock()
        client.send_whatsapp_message.return_value = {"messageId": "abc-123"}
        args = argparse.Namespace(
            origination_phone_number_id="phone-number-id-xxx",
            message='{"text":{"body":"Hello"}}',
            meta_api_version="v22.0",
        )
        result = cmd_send_message(client, args)
        assert result == {"messageId": "abc-123"}
        # Verify the message was encoded to bytes
        call_kwargs = client.send_whatsapp_message.call_args[1]
        assert isinstance(call_kwargs["message"], bytes)

    def test_invalid_json_message_exits(self):
        client = MagicMock()
        args = argparse.Namespace(
            origination_phone_number_id="phone-number-id-xxx",
            message="not valid json",
            meta_api_version="v22.0",
        )
        with pytest.raises(SystemExit) as exc:
            cmd_send_message(client, args)
        assert exc.value.code == EXIT_FAILURE


# ---------------------------------------------------------------------------
# cmd_create_flow
# ---------------------------------------------------------------------------

class TestCmdCreateFlow:
    def test_minimal_create(self):
        client = MagicMock()
        client.create_whatsapp_flow.return_value = {"flowId": "12345"}
        args = argparse.Namespace(
            id="waba-xxx",
            flow_name="Test",
            categories=["SURVEY"],
            flow_json=None,
            publish=False,
            clone_flow_id=None,
        )
        result = cmd_create_flow(client, args)
        assert result == {"flowId": "12345"}

    def test_publish_flag(self):
        client = MagicMock()
        args = argparse.Namespace(
            id="waba-xxx",
            flow_name="Test",
            categories=["SIGN_UP"],
            flow_json=None,
            publish=True,
            clone_flow_id=None,
        )
        cmd_create_flow(client, args)
        assert client.create_whatsapp_flow.call_args[1]["publish"] is True

    def test_with_flow_json(self):
        client = MagicMock()
        args = argparse.Namespace(
            id="waba-xxx",
            flow_name="Test",
            categories=["OTHER"],
            flow_json='{"version":"1.0"}',
            publish=False,
            clone_flow_id=None,
        )
        cmd_create_flow(client, args)
        call_kwargs = client.create_whatsapp_flow.call_args[1]
        assert call_kwargs["flowJson"] == b'{"version":"1.0"}'


# ---------------------------------------------------------------------------
# cmd_list_flows
# ---------------------------------------------------------------------------

class TestCmdListFlows:
    def test_minimal_list(self):
        client = MagicMock()
        client.list_whatsapp_flows.return_value = {"Flows": []}
        args = argparse.Namespace(
            id="waba-xxx",
            starting_token=None,
            max_results=None,
        )
        result = cmd_list_flows(client, args)
        assert result == {"Flows": []}

    def test_with_pagination(self):
        client = MagicMock()
        args = argparse.Namespace(
            id="waba-xxx",
            starting_token="token-abc",
            max_results=10,
        )
        cmd_list_flows(client, args)
        call_kwargs = client.list_whatsapp_flows.call_args[1]
        assert call_kwargs["nextToken"] == "token-abc"
        assert call_kwargs["maxResults"] == 10


# ---------------------------------------------------------------------------
# _setup_debug_logging (smoke test — verify it runs without error)
# ---------------------------------------------------------------------------

class TestSetupDebugLogging:
    def test_runs_without_exception(self):
        # Should not raise
        _setup_debug_logging()

    def test_warning_printed_to_stderr(self, capsys):
        _setup_debug_logging()
        captured = capsys.readouterr()
        assert "WARNING" in captured.err


# ---------------------------------------------------------------------------
# main() integration smoke test — exits 2 when no args (argparse error)
# ---------------------------------------------------------------------------

class TestMain:
    def test_no_args_exits_failure(self):
        with pytest.raises(SystemExit) as exc:
            main()
        # With no args, argparse exits with code 2
        assert exc.value.code != 0