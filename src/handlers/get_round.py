import json
from time import monotonic
from urllib.parse import parse_qs
from uuid import UUID

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.event_handler.api_gateway import Response
from pydantic import ValidationError

from src.models.round import RoundRequest, RoundUnavailableError
from src.repositories.db import connection
from src.repositories.round_repository import RoundRepository
from src.services.round_service import RoundService

logger = Logger(service="tango-music-game-round")
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


@app.get("/round")
def get_round() -> Response:
    started = monotonic()
    raw_event = app.current_event.raw_event
    raw_values = parse_qs(raw_event.get("rawQueryString", ""), keep_blank_values=True).get(
        "excludeArtist", []
    )
    if not raw_values and raw_event.get("queryStringParameters"):
        value = raw_event["queryStringParameters"].get("excludeArtist")
        raw_values = value if isinstance(value, list) else [value]
    try:
        exclusions = frozenset(UUID(value) for value in raw_values)
    except (ValueError, TypeError):
        return _error(
            400,
            "INVALID_EXCLUDED_ARTIST",
            "excludeArtist must contain valid MusicBrainz artist identifiers",
        )
    try:
        with connection() as conn:
            round_response = RoundService(
                RoundRepository(conn),
            ).create_round(RoundRequest(excluded_artist_ids=exclusions))
    except RoundUnavailableError:
        return _error(
            422,
            "ROUND_UNAVAILABLE",
            "Not enough eligible artists remain to create a round",
        )
    logger.info(
        "Round response assembled",
        extra={
            "duration_ms": round((monotonic() - started) * 1_000),
            "choice_count": len(round_response.choices),
            "track_count": len(round_response.tracks),
        },
    )
    return Response(
        status_code=200,
        content_type="application/json",
        headers={"cache-control": "no-store"},
        body=round_response.model_dump_json(by_alias=True),
    )


def lambda_handler(event: dict, context: object) -> dict:
    try:
        return app.resolve(event, context)
    except (ValidationError, ValueError) as error:
        logger.warning("Invalid round request", extra={"error_type": type(error).__name__})
        return _error_dict(
            400,
            "INVALID_EXCLUDED_ARTIST",
            "excludeArtist must contain valid MusicBrainz artist identifiers",
        )
    except Exception:
        logger.exception("Round dependency failed")
        return _error_dict(
            503,
            "ROUND_SERVICE_UNAVAILABLE",
            "A round could not be prepared",
        )
