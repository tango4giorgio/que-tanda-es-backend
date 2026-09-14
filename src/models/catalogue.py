from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.track_entry import CatalogueTrackEntry


class CatalogueResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: str
    generated_at: datetime = Field(alias="generatedAt")
    orchestras: list[dict[str, str]]
    tracks: list[dict[str, str | int]]

    @classmethod
    def from_entries(
        cls,
        orchestras: list[tuple[str, str]],
        tracks: list[CatalogueTrackEntry],
        version: str,
    ) -> "CatalogueResponse":
        return cls(
            version=version,
            generatedAt=datetime.now(UTC),
            orchestras=[
                {"id": orchestra_id, "displayName": display_name}
                for orchestra_id, display_name in orchestras
            ],
            tracks=[
                {
                    "id": track.id,
                    "orchestraId": track.orchestra_id,
                    "title": track.title,
                    "previewUrl": track.preview_url,
                    "durationMs": track.duration_ms,
                }
                for track in tracks
            ],
        )
