from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_DURATION_MS = 60_000
MAX_DURATION_MS = 900_000


def is_usable_track(preview_url: str, duration_ms: int) -> bool:
    return bool(preview_url.strip()) and MIN_DURATION_MS <= duration_ms <= MAX_DURATION_MS


class CatalogueTrackEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    orchestra_id: str
    recording_id: str | None = None
    title: str
    preview_url: str
    duration_ms: int = Field(gt=0)
    is_usable: bool | None = None

    @field_validator("preview_url")
    @classmethod
    def preview_url_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("preview_url must not be blank")
        return value

    def model_post_init(self, __context: object) -> None:
        self.is_usable = is_usable_track(self.preview_url, self.duration_ms)
