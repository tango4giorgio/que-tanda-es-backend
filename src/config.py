import os
from functools import lru_cache

from aws_lambda_powertools.utilities.parameters import get_parameter


class ConfigurationError(RuntimeError):
    pass


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return value


@lru_cache(maxsize=1)
def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    parameter_name = os.getenv("DATABASE_URL_PARAMETER_NAME")
    if not value and parameter_name:
        # SSM Parameter Store Standard tier (SecureString, AWS-managed KMS key)
        # is free; this avoids the flat per-secret charge Secrets Manager bills.
        value = get_parameter(parameter_name, max_age=300, decrypt=True)
    if not value:
        raise ConfigurationError("DATABASE_URL or DATABASE_URL_PARAMETER_NAME is required")
    return value


def database_connect_timeout_seconds() -> int:
    return _positive_int("DATABASE_CONNECT_TIMEOUT_SECONDS", 5)


def database_statement_timeout_ms() -> int:
    return _positive_int("DATABASE_STATEMENT_TIMEOUT_MS", 5_000)


def log_level() -> str:
    return os.getenv("LOG_LEVEL", "INFO")


def musicbrainz_base_url() -> str:
    return os.getenv("MUSICBRAINZ_BASE_URL", "https://musicbrainz.org")


def musicbrainz_user_agent() -> str:
    application = os.getenv("MUSICBRAINZ_APPLICATION", "tango-music-game")
    version = os.getenv("MUSICBRAINZ_VERSION", "0.1.0")
    maintainer = os.getenv("MUSICBRAINZ_MAINTAINER", "maintainer@example.invalid")
    if not all(value.strip() for value in (application, version, maintainer)):
        raise ConfigurationError(
            "MUSICBRAINZ_APPLICATION, MUSICBRAINZ_VERSION, and MUSICBRAINZ_MAINTAINER "
            "must not be blank"
        )
    return f"{application}/{version} ({maintainer})"


def musicbrainz_cache_freshness_seconds() -> int:
    return _positive_int("MUSICBRAINZ_CACHE_FRESHNESS_SECONDS", 86_400)


def musicbrainz_timeout_seconds() -> float:
    raw_value = os.getenv("MUSICBRAINZ_TIMEOUT_SECONDS", "10")
    try:
        value = float(raw_value)
    except ValueError as error:
        raise ConfigurationError("MUSICBRAINZ_TIMEOUT_SECONDS must be a number") from error
    if value <= 0:
        raise ConfigurationError("MUSICBRAINZ_TIMEOUT_SECONDS must be greater than zero")
    return value


def deployed_environment() -> bool:
    return os.getenv("DEPLOYED_ENVIRONMENT", "").strip().lower() in {
        "preview",
        "staging",
        "production",
        "prod",
    }
