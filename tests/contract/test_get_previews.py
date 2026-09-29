import json
from unittest.mock import patch
from uuid import UUID

from src.handlers.get_previews import lambda_handler
from src.models.round import PreviewResponse, TrackPreview, TrackPreviewNotFoundError

TRACK_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def event(body: object) -> dict:
    return {
        "version": "2.0",
        "routeKey": "POST /previews",
        "rawPath": "/previews",
        "rawQueryString": "",
        "requestContext": {
            "stage": "$default",
            "http": {"method": "POST", "path": "/previews"},
        },
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }


def test_get_previews_contract() -> None:
    response = PreviewResponse(
        previews=[
            TrackPreview(
                track_id=UUID(TRACK_ID),
                provider="deezer",
                preview_url="https://www.deezer.com/track/123",
                duration_ms=30_000,
            )
        ]
    )
    with patch("src.handlers.get_previews.connection"), patch(
        "src.handlers.get_previews.PreviewService.get_previews", return_value=response
    ):
        result = lambda_handler(event({"trackIds": [TRACK_ID]}), None)

    payload = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert payload == {
        "previews": [
            {
                "trackId": TRACK_ID,
                "provider": "deezer",
                "previewUrl": "https://www.deezer.com/track/123",
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
                preview_url="https://www.deezer.com/track/123",
                duration_ms=30_000,
            )
        ]
    )
    with patch("src.handlers.get_previews.connection"), patch(
        "src.handlers.get_previews.PreviewService.get_previews", return_value=response
    ) as mock_get_previews:
        lambda_handler(event({"trackIds": [TRACK_ID, TRACK_ID]}), None)

    assert mock_get_previews.call_args.args[0] == [UUID(TRACK_ID)]


def test_get_previews_rejects_empty_track_list() -> None:
    result = lambda_handler(event({"trackIds": []}), None)

    assert result["statusCode"] == 400
    assert json.loads(result["body"])["error"]["code"] == "INVALID_TRACK_IDS"


def test_get_previews_returns_not_found_when_any_track_is_unplayable() -> None:
    with patch("src.handlers.get_previews.connection"), patch(
        "src.handlers.get_previews.PreviewService.get_previews",
        side_effect=TrackPreviewNotFoundError([UUID(TRACK_ID)]),
    ):
        result = lambda_handler(event({"trackIds": [TRACK_ID]}), None)

    assert result["statusCode"] == 404
    assert json.loads(result["body"])["error"]["code"] == "TRACK_PREVIEW_NOT_FOUND"
