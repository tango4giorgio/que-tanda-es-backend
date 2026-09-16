from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

MIN_DURATION_MS = 60_000
MAX_DURATION_MS = 900_000


def is_usable_source(provider_url: str, duration_ms: int | None) -> bool:
    return bool(provider_url.strip()) and (
        duration_ms is None or MIN_DURATION_MS <= duration_ms <= MAX_DURATION_MS
    )


class ProviderSource(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    musicbrainz_recording_id: UUID
    provider: str = Field(min_length=1)
    provider_url: HttpUrl
    duration_ms: int | None = Field(default=None, gt=0)
    is_usable: bool | None = None

    @field_validator("provider")
    @classmethod
    def provider_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("provider must not be blank")
        return value.strip()

    def model_post_init(self, __context: object) -> None:
        self.is_usable = is_usable_source(str(self.provider_url), self.duration_ms)
