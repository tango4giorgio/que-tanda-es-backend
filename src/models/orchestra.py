from pydantic import BaseModel, ConfigDict, Field


class Artist(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    mbid_known: bool = False


class Orchestra(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str = Field(alias="displayName")
    artist_id: str | None = None
