import json
from unittest.mock import patch

from src.handlers.submit_feedback import lambda_handler
from src.repositories.feedback_repository import DuplicateFeedbackError

VALID_BODY = {
    "questionId": "77777777-7777-7777-7777-777777777777",
    "trackPosition": 1,
    "guessedArtistId": "22222222-2222-2222-2222-222222222222",
    "outcome": "wrong",
    "elapsedMs": 8200,
}


def event(body: dict) -> dict:
    return {
        "version": "2.0",
        "routeKey": "POST /feedback",
        "rawPath": "/feedback",
        "rawQueryString": "",
        "requestContext": {
            "stage": "$default",
            "http": {"method": "POST", "path": "/feedback"},
        },
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }


def test_submit_feedback_accepts_a_valid_wrong_guess() -> None:
    with (
        patch("src.handlers.submit_feedback.connection"),
        patch("src.handlers.submit_feedback.FeedbackService.record_attempt") as mock_record,
    ):
        result = lambda_handler(event(VALID_BODY), None)

    assert result["statusCode"] == 202
    assert result["headers"]["cache-control"] == "no-store"
    assert json.loads(result["body"]) == {"status": "recorded"}
    mock_record.assert_called_once()


def test_submit_feedback_accepts_a_valid_correct_guess() -> None:
    body = {**VALID_BODY, "outcome": "correct"}
    with patch("src.handlers.submit_feedback.connection"), patch(
        "src.handlers.submit_feedback.FeedbackService.record_attempt"
    ):
        result = lambda_handler(event(body), None)

    assert result["statusCode"] == 202


def test_submit_feedback_accepts_a_valid_skip() -> None:
    body = {**VALID_BODY, "outcome": "skipped", "guessedArtistId": None, "elapsedMs": 30_000}
    with patch("src.handlers.submit_feedback.connection"), patch(
        "src.handlers.submit_feedback.FeedbackService.record_attempt"
    ):
        result = lambda_handler(event(body), None)

    assert result["statusCode"] == 202


def test_submit_feedback_rejects_missing_fields() -> None:
    body = {key: value for key, value in VALID_BODY.items() if key != "questionId"}
    result = lambda_handler(event(body), None)

    assert result["statusCode"] == 400
    assert json.loads(result["body"]) == {
        "error": {
            "code": "INVALID_FEEDBACK",
            "message": "The submitted feedback failed validation",
        }
    }


def test_submit_feedback_rejects_guessed_artist_present_on_skip() -> None:
    body = {**VALID_BODY, "outcome": "skipped", "elapsedMs": 30_000}
    result = lambda_handler(event(body), None)

    assert result["statusCode"] == 400


def test_submit_feedback_rejects_missing_guessed_artist_on_wrong() -> None:
    body = {**VALID_BODY, "guessedArtistId": None}
    result = lambda_handler(event(body), None)

    assert result["statusCode"] == 400


def test_submit_feedback_rejects_elapsed_ms_out_of_range() -> None:
    body = {**VALID_BODY, "elapsedMs": 30_001}
    result = lambda_handler(event(body), None)

    assert result["statusCode"] == 400


def test_submit_feedback_rejects_malformed_json() -> None:
    malformed_event = event(VALID_BODY)
    malformed_event["body"] = "{not-json"
    result = lambda_handler(malformed_event, None)

    assert result["statusCode"] == 400


def test_submit_feedback_rejects_duplicate_submission_for_the_same_question() -> None:
    with (
        patch("src.handlers.submit_feedback.connection"),
        patch(
            "src.handlers.submit_feedback.FeedbackService.record_attempt",
            side_effect=DuplicateFeedbackError(),
        ),
    ):
        result = lambda_handler(event(VALID_BODY), None)

    assert result["statusCode"] == 400
    assert json.loads(result["body"]) == {
        "error": {
            "code": "INVALID_FEEDBACK",
            "message": "The submitted feedback failed validation",
        }
    }


def test_submit_feedback_returns_503_on_dependency_failure() -> None:
    with (
        patch("src.handlers.submit_feedback.connection"),
        patch(
            "src.handlers.submit_feedback.FeedbackService.record_attempt",
            side_effect=RuntimeError("db unavailable"),
        ),
    ):
        result = lambda_handler(event(VALID_BODY), None)

    assert result["statusCode"] == 503
    assert json.loads(result["body"]) == {
        "error": {
            "code": "FEEDBACK_SERVICE_UNAVAILABLE",
            "message": "The feedback record could not be saved",
        }
    }
