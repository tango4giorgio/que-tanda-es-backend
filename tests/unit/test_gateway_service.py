from unittest.mock import MagicMock

from src.models.routing import (
    ForwardedRequest,
    ForwardingOutcomeStatus,
    RoutingConfig,
)
from src.services.gateway_service import GatewayService


def _config(**entry_overrides: object) -> RoutingConfig:
    entry = {
        "method": "GET",
        "path": "/round",
        "target_function_name": "tango-music-game-get-round",
    }
    entry.update(entry_overrides)
    return RoutingConfig(entries=[entry])


def _stub_client(payload: dict | None = None, function_error: str | None = None) -> MagicMock:
    client = MagicMock()
    response = {"Payload": MagicMock()}
    if function_error:
        response["FunctionError"] = function_error
    import json

    response["Payload"].read.return_value = json.dumps(payload or {}).encode("utf-8")
    client.invoke.return_value = response
    return client


def test_invoke_target_relays_successful_response() -> None:
    config = _config()
    target_response = {"statusCode": 200, "headers": {}, "body": "{}"}
    service = GatewayService(config, lambda_client=_stub_client(target_response))

    outcome, response = service.invoke_target(
        config.entries[0], ForwardedRequest(method="GET", path="/round")
    )

    assert outcome.status == ForwardingOutcomeStatus.SUCCESS
    assert outcome.http_status_code == 200
    assert response == target_response


def test_invoke_target_maps_function_error_to_invocation_error() -> None:
    config = _config()
    service = GatewayService(
        config, lambda_client=_stub_client(function_error="Unhandled")
    )

    outcome, response = service.invoke_target(
        config.entries[0], ForwardedRequest(method="GET", path="/round")
    )

    assert outcome.status == ForwardingOutcomeStatus.INVOCATION_ERROR
    assert outcome.http_status_code == 502
    assert response is None


def test_invoke_target_maps_missing_required_keys_to_malformed_response() -> None:
    config = _config()
    service = GatewayService(config, lambda_client=_stub_client({"statusCode": 200}))

    outcome, response = service.invoke_target(
        config.entries[0], ForwardedRequest(method="GET", path="/round")
    )

    assert outcome.status == ForwardingOutcomeStatus.MALFORMED_RESPONSE
    assert outcome.http_status_code == 502
    assert response is None


def test_invoke_target_times_out_when_invocation_exceeds_route_timeout() -> None:
    import time

    config = _config(timeout_seconds=0.05)

    def slow_invoke(FunctionName: str, InvocationType: str, Payload: bytes) -> dict:
        time.sleep(0.2)
        return {"Payload": MagicMock(read=lambda: b"{}")}

    client = MagicMock()
    client.invoke.side_effect = slow_invoke
    service = GatewayService(config, lambda_client=client)

    outcome, response = service.invoke_target(
        config.entries[0], ForwardedRequest(method="GET", path="/round")
    )

    assert outcome.status == ForwardingOutcomeStatus.TIMEOUT
    assert outcome.http_status_code == 504
    assert response is None


def test_guard_body_size_accepts_body_within_limit() -> None:
    assert GatewayService.guard_body_size("a" * 1000, is_base64_encoded=False) is True


def test_guard_body_size_rejects_body_over_limit() -> None:
    assert GatewayService.guard_body_size("a" * 1_048_577, is_base64_encoded=False) is False


def test_guard_body_size_accepts_missing_body() -> None:
    assert GatewayService.guard_body_size(None, is_base64_encoded=False) is True


def test_match_route_distinguishes_not_found_from_method_not_allowed() -> None:
    config = _config()
    service = GatewayService(config, lambda_client=_stub_client())

    entry, method_matches_other_path = service.match_route("POST", "/round")
    assert entry is None
    assert method_matches_other_path is True

    entry, method_matches_other_path = service.match_route("GET", "/unknown")
    assert entry is None
    assert method_matches_other_path is False


def test_successful_invocation_logs_required_fields_without_body_content(caplog) -> None:
    import logging

    config = _config()
    target_response = {"statusCode": 200, "headers": {}, "body": "super-secret-body-content"}
    service = GatewayService(config, lambda_client=_stub_client(target_response))

    with caplog.at_level(logging.INFO, logger="tango-music-game-gateway"):
        service.invoke_target(config.entries[0], ForwardedRequest(method="GET", path="/round"))

    assert len(caplog.records) >= 1
    for record in caplog.records:
        message = record.getMessage()
        assert "super-secret-body-content" not in message
