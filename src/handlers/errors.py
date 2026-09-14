import json
import logging

logger = logging.getLogger(__name__)


def error_response(error: Exception) -> dict[str, object]:
    logger.exception("Unhandled catalogue request error")
    return {
        "statusCode": 500,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"message": "Unable to load catalogue"}),
    }
