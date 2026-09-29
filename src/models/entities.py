"""Shared base model for domain entities persisted in this redesign's schema.

Every table in the new schema carries both `created_at` and `updated_at` (FR-011); this mixin
is the single place that shape is defined, rather than repeating it on every entity model.
"""

from datetime import datetime

from pydantic import BaseModel


class TimestampedEntity(BaseModel):
    """Base model for any entity row that has server-managed `created_at`/`updated_at`."""

    created_at: datetime
    updated_at: datetime
