import pytest
from pydantic import ValidationError

from src.models.feedback import FeedbackSubmission

VALID_BASE = {
    "roundToken": "6f2c9e2b8c1a4f3daebf2d2e6a5b7c10",
    "trackPosition": 1,
    "recordingId": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "correctArtistId": "11111111-1111-1111-1111-111111111111",
    "guessedArtistId": "22222222-2222-2222-2222-222222222222",
    "outcome": "wrong",
    "elapsedMs": 8200,
}


def test_accepts_a_valid_wrong_guess_submission() -> None:
    submission = FeedbackSubmission.model_validate(VALID_BASE)
    assert submission.outcome == "wrong"
    assert submission.track_position == 1
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


@pytest.mark.parametrize("track_position", [0, 4, -1])
def test_rejects_track_position_out_of_range(track_position: int) -> None:
    payload = {**VALID_BASE, "trackPosition": track_position}
    with pytest.raises(ValidationError):
        FeedbackSubmission.model_validate(payload)


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


def test_rejects_missing_round_token() -> None:
    payload = {**VALID_BASE, "roundToken": ""}
    with pytest.raises(ValidationError):
        FeedbackSubmission.model_validate(payload)
