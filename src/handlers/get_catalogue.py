import logging
from time import monotonic

from aws_lambda_powertools.event_handler import APIGatewayHttpResolver

from src.handlers.errors import error_response
from src.repositories.catalogue_repository import CatalogueRepository
from src.repositories.db import connection
from src.services.catalogue_service import CatalogueService

logger = logging.getLogger(__name__)
app = APIGatewayHttpResolver()


@app.get("/catalogue")
def get_catalogue() -> dict[str, object]:
    started = monotonic()
    with connection() as conn:
        response = CatalogueService(CatalogueRepository(conn)).get_catalogue()
    logger.info("catalogue response assembled in %.3f seconds", monotonic() - started)
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json", "cache-control": "public, max-age=60"},
        "body": response.model_dump_json(by_alias=True),
    }


def lambda_handler(event: dict, context: object) -> dict:
    try:
        return app.resolve(event, context)
    except Exception as error:
        return error_response(error)
