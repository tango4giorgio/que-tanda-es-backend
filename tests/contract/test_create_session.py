import json
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID

from src.handlers.create_session import lambda_handler
from src.models.session import SessionCreated

SESSION_ID = "66666666-6666-6666-6666-666666666666"


def event() -> dict:
    return {
        "version": "2.0",
        "routeKey": "POST /session",
        "rawPath": "/session",
        "rawQueryString": "",
        "headers": {},
        "requestContext": {
            "stage": "$default",
            "http": {"method": "POST", "path": "/session"},
        },
        "body": None,
        "isBase64Encoded": False,
    }


def test_create_session_contract() -> None:
    started_at = datetime.now(UTC)
    created = SessionCreated(session_id=UUID(SESSION_ID), started_at=started_at)
    with (
        patch("src.handlers.create_session.connection"),
        patch(
            "src.handlers.create_session.SessionService.create_session",
            return_value=created,
        ),
    ):
        result = lambda_handler(event(), None)

    payload = json.loads(result["body"])
    assert result["statusCode"] == 201
    assert result["headers"]["cache-control"] == "no-store"
    assert payload == {
        "sessionId": SESSION_ID,
        "startedAt": started_at.isoformat().replace("+00:00", "Z"),
    }


def test_create_session_returns_503_on_dependency_failure() -> None:
    with (
        patch("src.handlers.create_session.connection"),
        patch(
            "src.handlers.create_session.SessionService.create_session",
            side_effect=RuntimeError("db unavailable"),
        ),
    ):
        result = lambda_handler(event(), None)

    assert result["statusCode"] == 503
    assert json.loads(result["body"]) == {
        "error": {
            "code": "SESSION_SERVICE_UNAVAILABLE",
            "message": "A session could not be created",
        }
    }
