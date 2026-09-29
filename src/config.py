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


def deployed_environment() -> bool:
    return os.getenv("DEPLOYED_ENVIRONMENT", "").strip().lower() in {
        "preview",
        "staging",
        "production",
        "prod",
    }
