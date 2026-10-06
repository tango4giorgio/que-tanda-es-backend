import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from time import monotonic
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from pydantic import ValidationError

from src.models.routing import (
    MAX_REQUEST_BODY_BYTES,
    ForwardedRequest,
    ForwardingOutcome,
    ForwardingOutcomeStatus,
    RoutingConfig,
    RoutingEntry,
)

logger = Logger(service="tango-music-game-gateway")

_REQUIRED_TARGET_RESPONSE_KEYS = ("statusCode", "headers", "body")


class GatewayConfigurationError(RuntimeError):
    """Raised when the routing configuration is missing, empty, or invalid."""


def load_routing_config(config_path: Path) -> RoutingConfig:
    """Load and validate the static routing configuration file.

    Raises GatewayConfigurationError for any missing, unparsable, or
    otherwise invalid configuration so callers can fail closed (FR-012).
    """
    try:
        raw_text = config_path.read_text()
    except OSError as error:
        raise GatewayConfigurationError(
            f"routing configuration not found: {config_path}"
        ) from error
    try:
        raw_data = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise GatewayConfigurationError("routing configuration is not valid JSON") from error
    try:
        return RoutingConfig.model_validate(raw_data)
    except ValidationError as error:
        raise GatewayConfigurationError(f"routing configuration is invalid: {error}") from error


class GatewayService:
    """Matches, translates, invokes, and relays requests to target Lambda functions."""

    def __init__(self, routing_config: RoutingConfig, lambda_client: Any | None = None):
        self.routing_config = routing_config
        self.route_index = routing_config.build_index()
        self._lambda_client = lambda_client
        self._executor = ThreadPoolExecutor(max_workers=8)

    @property
    def lambda_client(self) -> Any:
        # Constructed lazily (rather than at cold start) so importing the
        # handler module never requires AWS region configuration to be
        # present unless a target invocation is actually attempted.
        if self._lambda_client is None:
            self._lambda_client = boto3.client("lambda")
        return self._lambda_client

    def match_route(self, method: str, path: str) -> tuple[RoutingEntry | None, bool]:
        """Return the matched entry, and whether the path matched with a different method."""
        entry = self.route_index.get((method.upper(), path))
        if entry is not None:
            return entry, False
        method_matches_other_path = any(
            candidate_path == path for _, candidate_path in self.route_index
        )
        return None, method_matches_other_path

    @staticmethod
    def guard_body_size(body: str | None, is_base64_encoded: bool) -> bool:
        """Return True if the body is within the 1 MB limit (FR-010)."""
        if body is None:
            return True
        raw_length = len(body.encode("utf-8"))
        # Base64 encodes 3 bytes as 4 characters; approximate the decoded size.
        effective_length = int(raw_length * 3 / 4) if is_base64_encoded else raw_length
        return effective_length <= MAX_REQUEST_BODY_BYTES

    @staticmethod
    def build_forwarded_request(event: dict[str, Any]) -> ForwardedRequest:
        request_context = event.get("requestContext", {}) or {}
        http_context = request_context.get("http", {}) or {}
        return ForwardedRequest(
            method=(http_context.get("method") or event.get("httpMethod") or "GET").upper(),
            path=http_context.get("path") or event.get("rawPath") or "/",
            raw_query_string=event.get("rawQueryString") or "",
            query_string_parameters=event.get("queryStringParameters"),
            headers=event.get("headers") or {},
            body=event.get("body"),
            is_base64_encoded=bool(event.get("isBase64Encoded", False)),
        )

    @staticmethod
    def to_target_event(forwarded: ForwardedRequest) -> dict[str, Any]:
        """Reconstruct an API Gateway HTTP API v2.0 proxy event for the target Lambda."""
        return {
            "version": "2.0",
            "routeKey": f"{forwarded.method} {forwarded.path}",
            "rawPath": forwarded.path,
            "rawQueryString": forwarded.raw_query_string,
            "queryStringParameters": forwarded.query_string_parameters,
            "headers": forwarded.headers,
            "body": forwarded.body,
            "isBase64Encoded": forwarded.is_base64_encoded,
            "requestContext": {
                "stage": "$default",
                "http": {"method": forwarded.method, "path": forwarded.path},
            },
        }

    def _invoke(self, function_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode("utf-8"),
        )
        raw_payload = response["Payload"].read()
        function_error = response.get("FunctionError")
        if function_error:
            raise GatewayInvocationError(f"target function error: {function_error}")
        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError as error:
            raise GatewayMalformedResponseError(
                "target response payload is not valid JSON"
            ) from error

    def invoke_target(
        self, entry: RoutingEntry, forwarded: ForwardedRequest
    ) -> tuple[ForwardingOutcome, dict[str, Any] | None]:
        """Invoke the matched target function, enforcing its forwarding timeout."""
        started = monotonic()
        timeout_seconds = entry.resolved_timeout_seconds(
            self.routing_config.default_timeout_seconds
        )
        target_event = self.to_target_event(forwarded)
        future = self._executor.submit(self._invoke, entry.target_function_name, target_event)
        try:
            target_response = future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            duration_ms = (monotonic() - started) * 1_000
            logger.warning(
                "Target invocation timed out",
                extra={
                    "matched_route": f"{entry.method} {entry.path}",
                    "target_function_name": entry.target_function_name,
                    "outcome_status": ForwardingOutcomeStatus.TIMEOUT.value,
                    "duration_ms": duration_ms,
                },
            )
            return (
                ForwardingOutcome(
                    status=ForwardingOutcomeStatus.TIMEOUT,
                    matched_route=entry,
                    http_status_code=504,
                    duration_ms=duration_ms,
                ),
                None,
            )
        except GatewayMalformedResponseError as error:
            duration_ms = (monotonic() - started) * 1_000
            status = ForwardingOutcomeStatus.MALFORMED_RESPONSE
            logger.warning(
                "Target invocation failed",
                extra={
                    "matched_route": f"{entry.method} {entry.path}",
                    "target_function_name": entry.target_function_name,
                    "outcome_status": status.value,
                    "duration_ms": duration_ms,
                    "error_type": type(error).__name__,
                },
            )
            return (
                ForwardingOutcome(
                    status=status,
                    matched_route=entry,
                    http_status_code=502,
                    duration_ms=duration_ms,
                ),
                None,
            )
        except Exception as error:  # noqa: BLE001
            # Any other invocation failure (e.g. an AWS ClientError such as
            # AccessDeniedException for an unpermitted/missing target
            # function) is treated as a 502, attributed to the offending
            # route in the log entry (FR-009, User Story 3).
            duration_ms = (monotonic() - started) * 1_000
            logger.warning(
                "Target invocation failed",
                extra={
                    "matched_route": f"{entry.method} {entry.path}",
                    "target_function_name": entry.target_function_name,
                    "outcome_status": ForwardingOutcomeStatus.INVOCATION_ERROR.value,
                    "duration_ms": duration_ms,
                    "error_type": type(error).__name__,
                },
            )
            return (
                ForwardingOutcome(
                    status=ForwardingOutcomeStatus.INVOCATION_ERROR,
                    matched_route=entry,
                    http_status_code=502,
                    duration_ms=duration_ms,
                ),
                None,
            )

        duration_ms = (monotonic() - started) * 1_000
        if not isinstance(target_response, dict) or not all(
            key in target_response for key in _REQUIRED_TARGET_RESPONSE_KEYS
        ):
            logger.warning(
                "Target response missing required fields",
                extra={
                    "matched_route": f"{entry.method} {entry.path}",
                    "target_function_name": entry.target_function_name,
                    "outcome_status": ForwardingOutcomeStatus.MALFORMED_RESPONSE.value,
                    "duration_ms": duration_ms,
                },
            )
            return (
                ForwardingOutcome(
                    status=ForwardingOutcomeStatus.MALFORMED_RESPONSE,
                    matched_route=entry,
                    http_status_code=502,
                    duration_ms=duration_ms,
                ),
                None,
            )

        logger.info(
            "Request forwarded",
            extra={
                "matched_route": f"{entry.method} {entry.path}",
                "target_function_name": entry.target_function_name,
                "outcome_status": ForwardingOutcomeStatus.SUCCESS.value,
                "http_status_code": target_response["statusCode"],
                "duration_ms": duration_ms,
            },
        )
        return (
            ForwardingOutcome(
                status=ForwardingOutcomeStatus.SUCCESS,
                matched_route=entry,
                http_status_code=target_response["statusCode"],
                duration_ms=duration_ms,
            ),
            target_response,
        )


class GatewayInvocationError(RuntimeError):
    """Raised when a target Lambda invocation fails or errors."""


class GatewayMalformedResponseError(RuntimeError):
    """Raised when a target Lambda response cannot be parsed as JSON."""
