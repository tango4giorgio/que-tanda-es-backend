import json

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.event_handler.api_gateway import Response

from src.repositories.db import connection
from src.repositories.session_repository import SessionRepository
from src.services.session_service import SessionService

logger = Logger(service="tango-music-game-session")
app = APIGatewayHttpResolver()


def _error(status_code: int, code: str, message: str) -> Response:
    return Response(
        status_code=status_code,
        content_type="application/json",
        headers={"cache-control": "no-store"},
        body=json.dumps({"error": {"code": code, "message": message}}),
    )


def _error_dict(status_code: int, code: str, message: str) -> dict[str, object]:
    response = _error(status_code, code, message)
    return {
        "statusCode": response.status_code,
        "headers": response.headers,
        "body": response.body,
        "isBase64Encoded": response.base64_encoded,
    }


@app.post("/session")
def create_session() -> Response:
    with connection() as conn:
        created = SessionService(SessionRepository(conn)).create_session()
    return Response(
        status_code=201,
        content_type="application/json",
        headers={"cache-control": "no-store"},
        body=created.model_dump_json(by_alias=True),
    )


def lambda_handler(event: dict, context: object) -> dict:
    try:
        return app.resolve(event, context)
    except Exception:
        logger.exception("Session dependency failed")
        return _error_dict(
            503,
            "SESSION_SERVICE_UNAVAILABLE",
            "A session could not be created",
        )
