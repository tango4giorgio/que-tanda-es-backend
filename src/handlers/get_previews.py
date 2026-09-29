import json

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.event_handler.api_gateway import Response
from pydantic import ValidationError

from src.models.round import PreviewRequest, TrackPreviewNotFoundError
from src.repositories.catalogue_repository import CatalogueRepository
from src.repositories.db import connection
from src.services.preview_service import PreviewService

logger = Logger(service="tango-music-game-previews")
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


@app.post("/previews")
def get_previews() -> Response:
    try:
        request = PreviewRequest.model_validate(app.current_event.json_body)
    except ValidationError:
        return _error(
            400,
            "INVALID_TRACK_IDS",
            "trackIds must contain between 1 and 50 valid track identifiers",
        )
    try:
        with connection() as conn:
            response = PreviewService(CatalogueRepository(conn)).get_previews(
                request.track_ids
            )
    except TrackPreviewNotFoundError:
        return _error(
            404,
            "TRACK_PREVIEW_NOT_FOUND",
            "No playable preview exists for one or more requested tracks",
        )
    return Response(
        status_code=200,
        content_type="application/json",
        headers={"cache-control": "no-store"},
        body=response.model_dump_json(by_alias=True),
    )


def lambda_handler(event: dict, context: object) -> dict:
    try:
        return app.resolve(event, context)
    except (ValidationError, ValueError):
        return _error_dict(
            400,
            "INVALID_TRACK_IDS",
            "trackIds must contain between 1 and 50 valid track identifiers",
        )
    except Exception:
        logger.exception("Preview dependency failed")
        return _error_dict(
            503,
            "PREVIEW_SERVICE_UNAVAILABLE",
            "Track previews could not be resolved",
        )
