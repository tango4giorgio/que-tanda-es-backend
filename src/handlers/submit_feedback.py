import json

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.event_handler.api_gateway import Response
from pydantic import ValidationError

from src.models.feedback import FeedbackSubmission
from src.repositories.db import connection
from src.repositories.feedback_repository import FeedbackRejectedError, FeedbackRepository
from src.repositories.session_repository import SessionRepository
from src.services.feedback_service import FeedbackService
from src.services.session_service import InvalidSessionError, SessionService

logger = Logger(service="tango-music-game-feedback")
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


@app.post("/feedback")
def submit_feedback() -> Response:
    try:
        submission = FeedbackSubmission.model_validate(app.current_event.json_body)
    except ValidationError:
        # No player-identifying detail (or raw payload) is logged here, matching FR-006.
        logger.warning("Invalid feedback submission rejected")
        return _error(
            400,
            "INVALID_FEEDBACK",
            "The submitted feedback failed validation",
        )
    try:
        with connection() as conn:
            session_service = SessionService(SessionRepository(conn))
            try:
                session = session_service.require_active_session(
                    app.current_event.headers.get("X-Session-Id")
                )
            except InvalidSessionError:
                return _error(
                    401,
                    "SESSION_INVALID",
                    "A valid session is required for this request",
                )
            FeedbackService(FeedbackRepository(conn)).record_attempt(submission, session.id)
            session_service.touch(session.id)
    except FeedbackRejectedError:
        # Covers both a duplicate submission for the same question (FR-007) and an
        # unrecognised questionId (contracts/submit-feedback.md).
        logger.warning("Feedback submission rejected")
        return _error(
            400,
            "INVALID_FEEDBACK",
            "The submitted feedback failed validation",
        )
    return Response(
        status_code=202,
        content_type="application/json",
        headers={"cache-control": "no-store"},
        body=json.dumps({"status": "recorded"}),
    )


def lambda_handler(event: dict, context: object) -> dict:
    try:
        return app.resolve(event, context)
    except (ValidationError, ValueError):
        logger.warning("Invalid feedback request")
        return _error_dict(
            400,
            "INVALID_FEEDBACK",
            "The submitted feedback failed validation",
        )
    except Exception:
        logger.exception("Feedback dependency failed")
        return _error_dict(
            503,
            "FEEDBACK_SERVICE_UNAVAILABLE",
            "The feedback record could not be saved",
        )
