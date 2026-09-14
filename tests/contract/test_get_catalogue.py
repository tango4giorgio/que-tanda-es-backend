from unittest.mock import patch

from src.handlers.get_catalogue import lambda_handler


def test_get_catalogue_contract() -> None:
    fake_service_response = {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": (
            '{"version":"test","generatedAt":"2026-09-14T00:00:00Z",'
            '"orchestras":[{"id":"di-sarli","displayName":"Carlos Di Sarli"}],'
            '"tracks":[{"id":"track","orchestraId":"di-sarli","title":"Track",'
            '"previewUrl":"https://example.test/track.mp3","durationMs":120000}]}'
        ),
    }
    with patch("src.handlers.get_catalogue.connection"), patch(
        "src.handlers.get_catalogue.CatalogueService.get_catalogue",
        return_value=type(
            "Response",
            (),
            {"model_dump_json": lambda self, by_alias: fake_service_response["body"]},
        )(),
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
