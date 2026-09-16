import json

from aws_lambda_powertools import Logger

logger = Logger(service="recording-provider-registry")


def error_response(error: Exception) -> dict[str, object]:
    logger.exception(
        "Provider registry dependency failed",
        extra={"error_type": type(error).__name__},
    )
    return {
        "statusCode": 503,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
        },
        "body": json.dumps({"message": "Provider registry is temporarily unavailable"}),
    }
