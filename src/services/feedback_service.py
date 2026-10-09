from uuid import UUID

from src.models.feedback import FeedbackSubmission
from src.repositories.feedback_repository import FeedbackRepository


class FeedbackService:
    def __init__(self, repository: FeedbackRepository):
        self.repository = repository

    def record_attempt(
        self, submission: FeedbackSubmission, session_id: UUID | None
    ) -> None:
        self.repository.insert_attempt(submission, session_id)
