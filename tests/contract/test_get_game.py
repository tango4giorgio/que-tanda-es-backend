import json
from unittest.mock import patch
from uuid import UUID

from src.handlers.get_game import lambda_handler
from src.models.round import GameResponse

GAME_ID = "99999999-9999-9999-9999-999999999999"


def event(query: str = "") -> dict:
    return {
        "version": "2.0",
        "routeKey": "GET /game",
        "rawPath": "/game",
        "rawQueryString": query,
        "requestContext": {
            "stage": "$default",
            "http": {"method": "GET", "path": "/game"},
        },
    }


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
    with patch("src.handlers.get_game.connection"), patch(
        "src.handlers.get_game.GameService.create_game", return_value=sample_response()
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
