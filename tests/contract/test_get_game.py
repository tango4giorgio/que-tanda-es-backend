import json
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID

from src.handlers.get_game import lambda_handler
from src.models.round import GameResponse
from src.models.session import Session
from src.repositories.session_repository import SessionRepository
from src.services.session_service import InvalidSessionError

GAME_ID = "99999999-9999-9999-9999-999999999999"
SESSION_ID = "66666666-6666-6666-6666-666666666666"


def event(query: str = "", headers: dict | None = None) -> dict:
    return {
        "version": "2.0",
        "routeKey": "GET /game",
        "rawPath": "/game",
        "rawQueryString": query,
        "headers": {"X-Session-Id": SESSION_ID} if headers is None else headers,
        "requestContext": {
            "stage": "$default",
            "http": {"method": "GET", "path": "/game"},
        },
    }


def sample_session() -> Session:
    now = datetime.now(UTC)
    return Session(id=UUID(SESSION_ID), started_at=now, last_interaction_at=now, created_at=now, updated_at=now)


def sample_response() -> GameResponse:
    artist_ids = [
        UUID("11111111-1111-1111-1111-111111111111"),
        UUID("22222222-2222-2222-2222-222222222222"),
        UUID("33333333-3333-3333-3333-333333333333"),
    ]
    rounds = []
    for index in range(1, 4):
        rounds.append(
            {
                "round_id": UUID(int=10 + index),
                "sequence_number": index,
                "correct_artist_id": artist_ids[index - 1],
                "choices": [
                    {"artist_id": "11111111-1111-1111-1111-111111111111", "display_name": "A"},
                    {"artist_id": "22222222-2222-2222-2222-222222222222", "display_name": "B"},
                    {"artist_id": "33333333-3333-3333-3333-333333333333", "display_name": "C"},
                ],
                "question": {
                    "question_id": UUID(int=20 + index),
                    "track_ids": [UUID(int=30 + index)],
                },
            }
        )
    return GameResponse(game_id=UUID(GAME_ID), rounds=rounds)


def test_get_game_contract_excludes_preview_details() -> None:
    with (
        patch("src.handlers.get_game.connection"),
        patch(
            "src.handlers.get_game.SessionService.require_active_session",
            return_value=sample_session(),
        ),
        patch("src.handlers.get_game.SessionService.touch"),
        patch("src.handlers.get_game.GameService.create_game", return_value=sample_response()),
    ):
        result = lambda_handler(
            event("excludeArtist=44444444-4444-4444-4444-444444444444"), None
        )

    payload = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert result["headers"]["cache-control"] == "no-store"
    assert set(payload) == {"gameId", "rounds"}
    assert len(payload["rounds"]) == 3
    assert set(payload["rounds"][0]["question"]) == {"questionId", "trackIds"}


def test_get_game_rejects_malformed_exclusion() -> None:
    result = lambda_handler(event("excludeArtist=not-a-uuid"), None)

    assert result["statusCode"] == 400
    assert json.loads(result["body"])["error"]["code"] == "INVALID_EXCLUDED_ARTIST"


def test_get_game_rejects_missing_session() -> None:
    with patch("src.handlers.get_game.connection"):
        result = lambda_handler(event(headers={}), None)

    assert result["statusCode"] == 401
    assert json.loads(result["body"])["error"]["code"] == "SESSION_INVALID"


def test_get_game_rejects_unknown_or_expired_session() -> None:
    with (
        patch("src.handlers.get_game.connection"),
        patch(
            "src.handlers.get_game.SessionService.require_active_session",
            side_effect=InvalidSessionError,
        ),
        patch("src.handlers.get_game.SessionService.touch") as mock_touch,
    ):
        result = lambda_handler(event(), None)

    assert result["statusCode"] == 401
    assert json.loads(result["body"])["error"]["code"] == "SESSION_INVALID"
    mock_touch.assert_not_called()


def test_get_game_rejects_an_artificially_expired_session_without_writing() -> None:
    with (
        patch("src.handlers.get_game.connection"),
        patch(
            "src.handlers.get_game.SessionRepository.get_active",
            return_value=None,
        ) as mock_get_active,
        patch("src.handlers.get_game.SessionRepository.touch") as mock_touch,
    ):
        result = lambda_handler(event(), None)

    assert result["statusCode"] == 401
    assert json.loads(result["body"])["error"]["code"] == "SESSION_INVALID"
    mock_get_active.assert_called_once_with(UUID(SESSION_ID))
    mock_touch.assert_not_called()


def test_get_game_touches_session_on_success() -> None:
    with (
        patch("src.handlers.get_game.connection"),
        patch(
            "src.handlers.get_game.SessionService.require_active_session",
            return_value=sample_session(),
        ),
        patch("src.handlers.get_game.SessionService.touch") as mock_touch,
        patch("src.handlers.get_game.GameService.create_game", return_value=sample_response()),
    ):
        lambda_handler(event(), None)

    mock_touch.assert_called_once_with(UUID(SESSION_ID))
