import json
from pathlib import Path
from typing import Any

from aws_lambda_powertools import Logger

from src.services.gateway_service import (
    GatewayConfigurationError,
    GatewayService,
    load_routing_config,
)

logger = Logger(service="tango-music-game-gateway")

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "gateway_config" / "routes.json"

_gateway_service: GatewayService | None = None
_cold_start_error: GatewayConfigurationError | None = None

try:
    _gateway_service = GatewayService(load_routing_config(_DEFAULT_CONFIG_PATH))
except GatewayConfigurationError as error:
    _cold_start_error = error
    logger.exception("Gateway routing configuration failed to load at cold start")


def _error_response(status_code: int, code: str, message: str) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
        },
        "body": json.dumps({"error": {"code": code, "message": message}}),
        "isBase64Encoded": False,
    }


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    if _gateway_service is None:
        logger.error(
            "Gateway request rejected due to invalid routing configuration",
            extra={"error_type": type(_cold_start_error).__name__ if _cold_start_error else None},
        )
        return _error_response(502, "BAD_GATEWAY", "Gateway routing configuration is invalid")

    forwarded = _gateway_service.build_forwarded_request(event)

    if not _gateway_service.guard_body_size(forwarded.body, forwarded.is_base64_encoded):
        return _error_response(413, "PAYLOAD_TOO_LARGE", "Request body exceeds the 1 MB limit")

    entry, method_matches_other_path = _gateway_service.match_route(
        forwarded.method, forwarded.path
    )
    if entry is None:
        if method_matches_other_path:
            return _error_response(
                405, "METHOD_NOT_ALLOWED", "The request method is not registered for this path"
            )
        return _error_response(404, "NOT_FOUND", "No route matches this request")

    outcome, target_response = _gateway_service.invoke_target(entry, forwarded)
    if target_response is not None:
        return target_response

    if outcome.http_status_code == 504:
        return _error_response(
            504, "GATEWAY_TIMEOUT", "The target function did not respond in time"
        )
    return _error_response(502, "BAD_GATEWAY", "The target function invocation failed")
