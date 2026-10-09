import json
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID

from src.handlers.get_previews import lambda_handler
from src.models.round import PreviewResponse, TrackPreview, TrackPreviewNotFoundError
from src.models.session import Session
from src.services.provider_url_resolver import ProviderResolutionError
from src.services.session_service import InvalidSessionError

TRACK_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SESSION_ID = "66666666-6666-6666-6666-666666666666"


def event(body: object, headers: dict | None = None) -> dict:
    return {
        "version": "2.0",
        "routeKey": "POST /previews",
        "rawPath": "/previews",
        "rawQueryString": "",
        "headers": {"X-Session-Id": SESSION_ID} if headers is None else headers,
        "requestContext": {
            "stage": "$default",
            "http": {"method": "POST", "path": "/previews"},
        },
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }


def sample_session() -> Session:
    now = datetime.now(UTC)
    return Session(id=UUID(SESSION_ID), started_at=now, last_interaction_at=now, created_at=now, updated_at=now)


def test_get_previews_contract() -> None:
    response = PreviewResponse(
        previews=[
            TrackPreview(
                track_id=UUID(TRACK_ID),
                provider="deezer",
                preview_url="https://cdn.example/previews/123.mp3",
                duration_ms=30_000,
            )
        ]
    )
    with (
        patch("src.handlers.get_previews.connection"),
        patch(
            "src.handlers.get_previews.SessionService.require_active_session",
            return_value=sample_session(),
        ),
        patch("src.handlers.get_previews.SessionService.touch"),
        patch("src.handlers.get_previews.PreviewService.get_previews", return_value=response),
    ):
        result = lambda_handler(event({"trackIds": [TRACK_ID]}), None)

    payload = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert payload == {
        "previews": [
            {
                "trackId": TRACK_ID,
                "provider": "deezer",
                "previewUrl": "https://cdn.example/previews/123.mp3",
                "durationMs": 30000,
            }
        ]
    }


def test_get_previews_deduplicates_track_ids_before_resolution() -> None:
    response = PreviewResponse(
        previews=[
            TrackPreview(
                track_id=UUID(TRACK_ID),
                provider="deezer",
                preview_url="https://cdn.example/previews/123.mp3",
                duration_ms=30_000,
            )
        ]
    )
    with (
        patch("src.handlers.get_previews.connection"),
        patch(
            "src.handlers.get_previews.SessionService.require_active_session",
            return_value=sample_session(),
        ),
        patch("src.handlers.get_previews.SessionService.touch"),
        patch(
            "src.handlers.get_previews.PreviewService.get_previews", return_value=response
        ) as mock_get_previews,
    ):
        lambda_handler(event({"trackIds": [TRACK_ID, TRACK_ID]}), None)

    assert mock_get_previews.call_args.args[0] == [UUID(TRACK_ID)]


def test_get_previews_rejects_empty_track_list() -> None:
    result = lambda_handler(event({"trackIds": []}), None)

    assert result["statusCode"] == 400
    assert json.loads(result["body"])["error"]["code"] == "INVALID_TRACK_IDS"


def test_get_previews_rejects_missing_session() -> None:
    with patch("src.handlers.get_previews.connection"):
        result = lambda_handler(event({"trackIds": [TRACK_ID]}, headers={}), None)

    assert result["statusCode"] == 401
    assert json.loads(result["body"])["error"]["code"] == "SESSION_INVALID"


def test_get_previews_rejects_unknown_or_expired_session() -> None:
    with (
        patch("src.handlers.get_previews.connection"),
        patch(
            "src.handlers.get_previews.SessionService.require_active_session",
            side_effect=InvalidSessionError,
        ),
    ):
        result = lambda_handler(event({"trackIds": [TRACK_ID]}), None)

    assert result["statusCode"] == 401
    assert json.loads(result["body"])["error"]["code"] == "SESSION_INVALID"


def test_get_previews_returns_not_found_when_any_track_is_unplayable() -> None:
    with (
        patch("src.handlers.get_previews.connection"),
        patch(
            "src.handlers.get_previews.SessionService.require_active_session",
            return_value=sample_session(),
        ),
        patch("src.handlers.get_previews.SessionService.touch"),
        patch(
            "src.handlers.get_previews.PreviewService.get_previews",
            side_effect=TrackPreviewNotFoundError([UUID(TRACK_ID)]),
        ),
    ):
        result = lambda_handler(event({"trackIds": [TRACK_ID]}), None)

    assert result["statusCode"] == 404
    assert json.loads(result["body"])["error"]["code"] == "TRACK_PREVIEW_NOT_FOUND"


def test_get_previews_returns_service_unavailable_for_a_provider_failure() -> None:
    with (
        patch("src.handlers.get_previews.connection"),
        patch(
            "src.handlers.get_previews.SessionService.require_active_session",
            return_value=sample_session(),
        ),
        patch("src.handlers.get_previews.SessionService.touch"),
        patch(
            "src.handlers.get_previews.PreviewService.get_previews",
            side_effect=ProviderResolutionError("Deezer track lookup failed"),
        ),
    ):
        result = lambda_handler(event({"trackIds": [TRACK_ID]}), None)

    assert result["statusCode"] == 503
    assert json.loads(result["body"])["error"]["code"] == "PREVIEW_SERVICE_UNAVAILABLE"
