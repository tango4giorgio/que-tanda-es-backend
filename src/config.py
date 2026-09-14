import os


def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value and os.getenv("DATABASE_URL_SECRET_ARN"):
        import boto3

        response = boto3.client("secretsmanager").get_secret_value(
            SecretId=os.environ["DATABASE_URL_SECRET_ARN"]
        )
        value = response.get("SecretString")
    if not value:
        raise RuntimeError("DATABASE_URL or DATABASE_URL_SECRET_ARN is required")
    return value


def log_level() -> str:
    return os.getenv("LOG_LEVEL", "INFO")
