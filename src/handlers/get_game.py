import json
from time import monotonic
from urllib.parse import parse_qs
from uuid import UUID

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.event_handler.api_gateway import Response
from pydantic import ValidationError

from src.models.round import GameRequest, GameUnavailableError
from src.repositories.catalogue_repository import CatalogueRepository
from src.repositories.db import connection
from src.repositories.game_repository import GameRepository
from src.repositories.session_repository import SessionRepository
from src.services.game_service import GameService
from src.services.session_service import InvalidSessionError, SessionService

logger = Logger(service="tango-music-game-game")
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


@app.get("/game")
def get_game() -> Response:
    started = monotonic()
    raw_event = app.current_event.raw_event
    query_params = raw_event.get("queryStringParameters") or {}
    raw_values = parse_qs(raw_event.get("rawQueryString", ""), keep_blank_values=True).get(
        "excludeArtist", []
    )
    if not raw_values and "excludeArtist" in query_params:
        value = query_params.get("excludeArtist")
        raw_values = value if isinstance(value, list) else [value]
    try:
        exclusions = frozenset(UUID(value) for value in raw_values)
    except (ValueError, TypeError):
        return _error(
            400,
            "INVALID_EXCLUDED_ARTIST",
            "excludeArtist must contain valid artist identifiers",
        )

    try:
        with connection() as conn:
            session_service = SessionService(SessionRepository(conn))
            try:
                session = session_service.require_active_session(
                    app.current_event.headers.get("X-Session-Id")
                )
            except InvalidSessionError:
                return _error(
                    401,
                    "SESSION_INVALID",
                    "A valid session is required for this request",
                )
            game_response = GameService(
                CatalogueRepository(conn),
                GameRepository(conn),
                conn,
            ).create_game(GameRequest(excluded_artist_ids=exclusions))
            session_service.touch(session.id)
    except GameUnavailableError:
        return _error(
            422,
            "GAME_UNAVAILABLE",
            "Not enough eligible artists remain to create a complete game",
        )
    logger.info(
        "Game response assembled",
        extra={
            "duration_ms": round((monotonic() - started) * 1_000),
            "round_count": len(game_response.rounds),
            "track_count": sum(
                len(round_.question.track_ids) for round_ in game_response.rounds
            ),
        },
    )
    return Response(
        status_code=200,
        content_type="application/json",
        headers={"cache-control": "no-store"},
        body=game_response.model_dump_json(by_alias=True),
    )


def lambda_handler(event: dict, context: object) -> dict:
    try:
        return app.resolve(event, context)
    except (ValidationError, ValueError):
        logger.warning("Invalid game request")
        return _error_dict(
            400,
            "INVALID_EXCLUDED_ARTIST",
            "excludeArtist must contain valid artist identifiers",
        )
    except Exception:
        logger.exception("Game dependency failed")
        return _error_dict(
            503,
            "GAME_SERVICE_UNAVAILABLE",
            "A game could not be prepared",
        )
