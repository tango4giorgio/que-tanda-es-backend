from uuid import UUID

from src.models.entities import TimestampedEntity


class Game(TimestampedEntity):
    """A played session: purely a grouping of rounds, with no status field (2026-09-24
    clarification; data-model.md `game`)."""

    id: UUID


class Round(TimestampedEntity):
    """A reusable round linked to games and questions through association records."""

    id: UUID


class GameRoundLink(TimestampedEntity):
    """An ordered association between a game and a round."""

    id: UUID
    game_id: UUID
    round_id: UUID
    sequence_number: int


class RoundQuestionLink(TimestampedEntity):
    """An ordered association between a round and a question."""

    id: UUID
    round_id: UUID
    question_id: UUID
    sequence_number: int
