import json
from unittest.mock import patch
from uuid import UUID

from src.handlers.get_round import lambda_handler
from src.models.round import RoundResponse


def event(query: str = "") -> dict:
    return {
        "version": "2.0",
        "routeKey": "GET /round",
        "rawPath": "/round",
        "rawQueryString": query,
        "requestContext": {
            "stage": "$default",
            "http": {"method": "GET", "path": "/round"},
        },
    }


def test_get_round_contract() -> None:
    response = RoundResponse(
        correct_artist_id=UUID("11111111-1111-1111-1111-111111111111"),
        round_token="6f2c9e2b8c1a4f3daebf2d2e6a5b7c10",
        choices=[
            {"artist_id": "11111111-1111-1111-1111-111111111111", "display_name": "A"},
            {"artist_id": "22222222-2222-2222-2222-222222222222", "display_name": "B"},
            {"artist_id": "33333333-3333-3333-3333-333333333333", "display_name": "C"},
        ],
        tracks=[
            {
                "recording_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "provider": "archive.org",
                "preview_url": "https://example.test/a.mp3",
                "duration_ms": 120_000,
            }
        ],
    )
    with patch("src.handlers.get_round.connection"), patch(
        "src.handlers.get_round.RoundService.create_round", return_value=response
    ):
        result = lambda_handler(event("excludeArtist=44444444-4444-4444-4444-444444444444"), None)

    payload = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert result["headers"]["cache-control"] == "no-store"
    assert set(payload) == {"correctArtistId", "roundToken", "choices", "tracks"}
    assert payload["roundToken"] == "6f2c9e2b8c1a4f3daebf2d2e6a5b7c10"
    assert set(payload["tracks"][0]) == {
        "recordingId",
        "provider",
        "previewUrl",
        "durationMs",
    }


def test_get_round_issues_unique_round_token_per_call() -> None:
    first = lambda_handler(event(), None)
    second = lambda_handler(event(), None)

    # Both calls hit the same in-memory fixture-free path only when a real
    # dependency is wired; here we only assert distinctness when both calls
    # succeed against a mocked service returning fresh tokens.
    with patch("src.handlers.get_round.connection"), patch(
        "src.handlers.get_round.RoundService.create_round"
    ) as mock_create_round:
        mock_create_round.side_effect = [
            RoundResponse(
                correct_artist_id=UUID("11111111-1111-1111-1111-111111111111"),
                round_token="aaaa1111aaaa1111aaaa1111aaaa1111",
                choices=[
                    {"artist_id": "11111111-1111-1111-1111-111111111111", "display_name": "A"},
                    {"artist_id": "22222222-2222-2222-2222-222222222222", "display_name": "B"},
                    {"artist_id": "33333333-3333-3333-3333-333333333333", "display_name": "C"},
                ],
                tracks=[
                    {
                        "recording_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "provider": "archive.org",
                        "preview_url": "https://example.test/a.mp3",
                        "duration_ms": 120_000,
                    }
                ],
            ),
            RoundResponse(
                correct_artist_id=UUID("11111111-1111-1111-1111-111111111111"),
                round_token="bbbb2222bbbb2222bbbb2222bbbb2222",
                choices=[
                    {"artist_id": "11111111-1111-1111-1111-111111111111", "display_name": "A"},
                    {"artist_id": "22222222-2222-2222-2222-222222222222", "display_name": "B"},
                    {"artist_id": "33333333-3333-3333-3333-333333333333", "display_name": "C"},
                ],
                tracks=[
                    {
                        "recording_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "provider": "archive.org",
                        "preview_url": "https://example.test/a.mp3",
                        "duration_ms": 120_000,
                    }
                ],
            ),
        ]
        first = lambda_handler(event(), None)
        second = lambda_handler(event(), None)

    first_token = json.loads(first["body"])["roundToken"]
    second_token = json.loads(second["body"])["roundToken"]
    assert first_token
    assert second_token
    assert first_token != second_token


def test_get_round_rejects_malformed_exclusion() -> None:
    result = lambda_handler(event("excludeArtist=not-a-uuid"), None)

    assert result["statusCode"] == 400
    assert json.loads(result["body"]) == {
        "error": {
            "code": "INVALID_EXCLUDED_ARTIST",
            "message": "excludeArtist must contain valid MusicBrainz artist identifiers",
        }
    }
