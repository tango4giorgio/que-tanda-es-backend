import json
from unittest.mock import MagicMock

import src.handlers.gateway as gateway_module
from src.handlers.gateway import lambda_handler
from src.models.routing import RoutingConfig
from src.services.gateway_service import GatewayService


def event(method: str = "GET", path: str = "/game", body: str | None = None) -> dict:
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {},
        "body": body,
        "isBase64Encoded": False,
        "requestContext": {"http": {"method": method, "path": path}},
    }


def _stub_lambda_client(payload: dict, function_error: str | None = None) -> MagicMock:
    client = MagicMock()
    response = {"Payload": MagicMock(read=lambda: json.dumps(payload).encode("utf-8"))}
    if function_error:
        response["FunctionError"] = function_error
    client.invoke.return_value = response
    return client


def _install_gateway(monkeypatch, entries: list[dict], lambda_client: MagicMock) -> None:
    config = RoutingConfig(entries=entries)
    monkeypatch.setattr(
        gateway_module, "_gateway_service", GatewayService(config, lambda_client=lambda_client)
    )
    monkeypatch.setattr(gateway_module, "_cold_start_error", None)


def test_matched_route_relays_target_response_unchanged(monkeypatch) -> None:
    target_response = {
        "statusCode": 422,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"error": {"code": "ROUND_UNAVAILABLE", "message": "no rounds"}}),
        "isBase64Encoded": False,
    }
    _install_gateway(
        monkeypatch,
        [{"method": "GET", "path": "/game", "target_function_name": "tango-music-game-get-game"}],
        _stub_lambda_client(target_response),
    )

    result = lambda_handler(event("GET", "/game"), None)

    assert result == target_response


def test_matched_post_route_relays_target_response_unchanged(monkeypatch) -> None:
    target_response = {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"previews": []}),
        "isBase64Encoded": False,
    }
    _install_gateway(
        monkeypatch,
        [
            {
                "method": "POST",
                "path": "/previews",
                "target_function_name": "tango-music-game-get-previews",
            }
        ],
        _stub_lambda_client(target_response),
    )

    result = lambda_handler(event("POST", "/previews", body='{"trackIds": []}'), None)

    assert result == target_response


def test_unmatched_path_returns_404_without_invoking_target(monkeypatch) -> None:
    client = _stub_lambda_client({"statusCode": 200, "headers": {}, "body": "{}"})
    _install_gateway(
        monkeypatch,
        [{"method": "GET", "path": "/game", "target_function_name": "tango-music-game-get-game"}],
        client,
    )

    result = lambda_handler(event("GET", "/unknown"), None)

    assert result["statusCode"] == 404
    assert json.loads(result["body"])["error"]["code"] == "NOT_FOUND"
    client.invoke.assert_not_called()


def test_matched_path_with_wrong_method_returns_405(monkeypatch) -> None:
    client = _stub_lambda_client({"statusCode": 200, "headers": {}, "body": "{}"})
    _install_gateway(
        monkeypatch,
        [{"method": "GET", "path": "/game", "target_function_name": "tango-music-game-get-game"}],
        client,
    )

    result = lambda_handler(event("POST", "/game"), None)

    assert result["statusCode"] == 405
    assert json.loads(result["body"])["error"]["code"] == "METHOD_NOT_ALLOWED"
    client.invoke.assert_not_called()


def test_oversized_body_returns_413_without_invoking_target(monkeypatch) -> None:
    client = _stub_lambda_client({"statusCode": 200, "headers": {}, "body": "{}"})
    _install_gateway(
        monkeypatch,
        [{"method": "GET", "path": "/game", "target_function_name": "tango-music-game-get-game"}],
        client,
    )

    result = lambda_handler(event("GET", "/game", body="a" * 1_048_577), None)

    assert result["statusCode"] == 413
    assert json.loads(result["body"])["error"]["code"] == "PAYLOAD_TOO_LARGE"
    client.invoke.assert_not_called()


def test_target_timeout_returns_504(monkeypatch) -> None:
    import time

    def slow_invoke(FunctionName: str, InvocationType: str, Payload: bytes) -> dict:
        time.sleep(0.2)
        return {"Payload": MagicMock(read=lambda: b"{}")}

    client = MagicMock()
    client.invoke.side_effect = slow_invoke
    _install_gateway(
        monkeypatch,
        [
            {
                "method": "GET",
                "path": "/game",
                "target_function_name": "tango-music-game-get-game",
                "timeout_seconds": 0.05,
            }
        ],
        client,
    )

    result = lambda_handler(event("GET", "/game"), None)

    assert result["statusCode"] == 504
    assert json.loads(result["body"])["error"]["code"] == "GATEWAY_TIMEOUT"


def test_target_function_error_returns_502(monkeypatch) -> None:
    client = _stub_lambda_client({}, function_error="Unhandled")
    _install_gateway(
        monkeypatch,
        [{"method": "GET", "path": "/game", "target_function_name": "tango-music-game-get-game"}],
        client,
    )

    result = lambda_handler(event("GET", "/game"), None)

    assert result["statusCode"] == 502
    assert json.loads(result["body"])["error"]["code"] == "BAD_GATEWAY"


def test_malformed_target_payload_returns_502(monkeypatch) -> None:
    client = _stub_lambda_client({"statusCode": 200})  # missing headers/body
    _install_gateway(
        monkeypatch,
        [{"method": "GET", "path": "/game", "target_function_name": "tango-music-game-get-game"}],
        client,
    )

    result = lambda_handler(event("GET", "/game"), None)

    assert result["statusCode"] == 502
    assert json.loads(result["body"])["error"]["code"] == "BAD_GATEWAY"


def test_cold_start_invalid_configuration_returns_502_for_every_request(monkeypatch) -> None:
    monkeypatch.setattr(gateway_module, "_gateway_service", None)

    first = lambda_handler(event("GET", "/game"), None)
    second = lambda_handler(event("GET", "/anything-else"), None)

    assert first["statusCode"] == 502
    assert second["statusCode"] == 502
    assert json.loads(first["body"])["error"]["code"] == "BAD_GATEWAY"


def test_unpermitted_target_function_returns_502_and_logs_offending_route(
    monkeypatch, caplog
) -> None:
    import logging

    client = MagicMock()
    client.invoke.side_effect = Exception("AccessDeniedException: not authorized")
    config = RoutingConfig(
        entries=[
            {
                "method": "GET",
                "path": "/game",
                "target_function_name": "tango-music-game-unpermitted-function",
            }
        ]
    )

    class RaisingGatewayService(GatewayService):
        def _invoke(self, function_name: str, payload: dict) -> dict:
            raise Exception("AccessDeniedException: not authorized")

    monkeypatch.setattr(
        gateway_module, "_gateway_service", RaisingGatewayService(config, lambda_client=client)
    )
    monkeypatch.setattr(gateway_module, "_cold_start_error", None)

    with caplog.at_level(logging.WARNING, logger="tango-music-game-gateway"):
        result = lambda_handler(event("GET", "/game"), None)

    assert result["statusCode"] == 502
    assert any(
        getattr(record, "target_function_name", None) == "tango-music-game-unpermitted-function"
        for record in caplog.records
    )
