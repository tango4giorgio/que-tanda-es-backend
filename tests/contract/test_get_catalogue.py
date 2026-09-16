import json
from unittest.mock import patch

from src.handlers.get_catalogue import lambda_handler


def test_get_catalogue_contract() -> None:
    with (
        patch("src.handlers.get_catalogue.connection"),
        patch(
            "src.handlers.get_catalogue.CatalogueService.get_provider_links",
            return_value=[
                {
                    "recordingId": "5a5d9d31-64a7-4a5d-87bd-1934d7efbb84",
                    "links": [
                        {
                            "provider": "archive.org",
                            "url": "https://example.test/track.mp3",
                            "durationMs": 120_000,
                        }
                    ],
                }
            ],
        ),
    ):
        response = lambda_handler(
            {
                "version": "2.0",
                "routeKey": "GET /catalogue",
                "rawPath": "/catalogue",
                "requestContext": {
                    "stage": "$default",
                    "http": {"method": "GET", "path": "/catalogue"},
                },
            },
            None,
        )
    assert response["statusCode"] == 200
    assert response["headers"]["cache-control"] == "public, max-age=60"
    payload = json.loads(response["body"])
    assert isinstance(payload["recordings"], list)
    assert payload["recordings"][0]["recordingId"] == ("5a5d9d31-64a7-4a5d-87bd-1934d7efbb84")
    assert payload["recordings"][0]["links"][0]["provider"] == "archive.org"
    assert not {"artist", "title", "release", "artistCredit"} & set(payload["recordings"][0])
