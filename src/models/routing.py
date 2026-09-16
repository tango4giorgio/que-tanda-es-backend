from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

_ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})

DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_TIMEOUT_SECONDS = 29.0
MAX_REQUEST_BODY_BYTES = 1_048_576  # 1 MB


class RoutingEntry(BaseModel):
    """A single mapping from a request pattern to a target Lambda function."""

    method: str
    path: str
    target_function_name: str = Field(min_length=1)
    timeout_seconds: float | None = Field(default=None, gt=0, lt=MAX_TIMEOUT_SECONDS)

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str) -> str:
        method = value.upper()
        if method not in _ALLOWED_METHODS:
            raise ValueError(f"method must be one of {sorted(_ALLOWED_METHODS)}")
        return method

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("path must start with '/'")
        if "{" in value or "}" in value:
            raise ValueError("path must be an exact literal path with no path parameters")
        return value

    def resolved_timeout_seconds(self, default_timeout_seconds: float) -> float:
        if self.timeout_seconds is not None:
            return self.timeout_seconds
        return default_timeout_seconds


class RoutingConfig(BaseModel):
    """The complete, versioned set of routing entries the gateway resolves requests against."""

    entries: list[RoutingEntry] = Field(min_length=1)
    default_timeout_seconds: float = Field(
        default=DEFAULT_TIMEOUT_SECONDS, gt=0, lt=MAX_TIMEOUT_SECONDS
    )

    @model_validator(mode="after")
    def validate_unique_routes(self) -> "RoutingConfig":
        seen: set[tuple[str, str]] = set()
        for entry in self.entries:
            key = (entry.method, entry.path)
            if key in seen:
                raise ValueError(f"duplicate route {entry.method} {entry.path}")
            seen.add(key)
        return self

    def build_index(self) -> dict[tuple[str, str], RoutingEntry]:
        return {(entry.method, entry.path): entry for entry in self.entries}


class ForwardedRequest(BaseModel):
    """The inbound client request as translated into a target invocation payload."""

    method: str
    path: str
    query_string_parameters: dict[str, str] | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    is_base64_encoded: bool = False


class ForwardingOutcomeStatus(StrEnum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    INVOCATION_ERROR = "invocation_error"
    MALFORMED_RESPONSE = "malformed_response"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    CONFIG_INVALID = "config_invalid"


class ForwardingOutcome(BaseModel):
    """The result of a single forwarding attempt, used for both the response and logging."""

    status: ForwardingOutcomeStatus
    matched_route: RoutingEntry | None = None
    http_status_code: int
    duration_ms: float
