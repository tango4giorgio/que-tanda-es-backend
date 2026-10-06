import pytest
from pydantic import ValidationError

from src.models.feedback import FeedbackSubmission

VALID_BASE = {
    "questionId": "77777777-7777-7777-7777-777777777777",
    "trackPosition": 1,
    "guessedArtistId": "22222222-2222-2222-2222-222222222222",
    "outcome": "incorrect",
    "elapsedMs": 8200,
}


def test_accepts_a_valid_incorrect_guess_submission() -> None:
    submission = FeedbackSubmission.model_validate(VALID_BASE)
    assert submission.outcome == "incorrect"
    assert submission.elapsed_ms == 8200


def test_accepts_a_valid_correct_guess_submission() -> None:
    payload = {**VALID_BASE, "outcome": "correct"}
    submission = FeedbackSubmission.model_validate(payload)
    assert submission.outcome == "correct"


def test_accepts_a_valid_skipped_submission_with_no_guessed_artist() -> None:
    payload = {**VALID_BASE, "outcome": "skipped", "guessedArtistId": None, "elapsedMs": 30_000}
    submission = FeedbackSubmission.model_validate(payload)
    assert submission.outcome == "skipped"
    assert submission.guessed_artist_id is None


@pytest.mark.parametrize("elapsed_ms", [-1, 30_001])
def test_rejects_elapsed_ms_out_of_range(elapsed_ms: int) -> None:
    payload = {**VALID_BASE, "elapsedMs": elapsed_ms}
    with pytest.raises(ValidationError):
        FeedbackSubmission.model_validate(payload)


def test_rejects_unknown_outcome() -> None:
    payload = {**VALID_BASE, "outcome": "maybe"}
    with pytest.raises(ValidationError):
        FeedbackSubmission.model_validate(payload)


def test_rejects_guessed_artist_present_when_outcome_is_skipped() -> None:
    payload = {**VALID_BASE, "outcome": "skipped", "elapsedMs": 30_000}
    with pytest.raises(ValidationError):
        FeedbackSubmission.model_validate(payload)


def test_rejects_missing_guessed_artist_when_outcome_is_not_skipped() -> None:
    payload = {**VALID_BASE, "guessedArtistId": None}
    with pytest.raises(ValidationError):
        FeedbackSubmission.model_validate(payload)


def test_rejects_missing_question_id() -> None:
    payload = {key: value for key, value in VALID_BASE.items() if key != "questionId"}
    with pytest.raises(ValidationError):
        FeedbackSubmission.model_validate(payload)


@pytest.mark.parametrize("track_position", [0, 4])
def test_rejects_track_position_out_of_range(track_position: int) -> None:
    with pytest.raises(ValidationError):
        FeedbackSubmission.model_validate(
            {**VALID_BASE, "trackPosition": track_position}
        )
