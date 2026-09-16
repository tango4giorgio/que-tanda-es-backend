import json
from time import monotonic

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.event_handler.api_gateway import Response

from src.handlers.errors import error_response
from src.repositories.catalogue_repository import CatalogueRepository
from src.repositories.db import connection
from src.services.catalogue_service import CatalogueService

logger = Logger(service="recording-provider-registry")
app = APIGatewayHttpResolver()


@app.get("/catalogue")
def get_catalogue() -> Response:
    started = monotonic()
    with connection() as conn:
        recordings = CatalogueService(CatalogueRepository(conn)).get_provider_links()
    logger.info(
        "Provider registry response assembled",
        extra={"duration_ms": round((monotonic() - started) * 1_000)},
    )
    return Response(
        status_code=200,
        content_type="application/json",
        headers={"cache-control": "public, max-age=60"},
        body=json.dumps({"recordings": recordings}),
    )


def lambda_handler(event: dict, context: object) -> dict:
    try:
        return app.resolve(event, context)
    except Exception as error:
        return error_response(error)
