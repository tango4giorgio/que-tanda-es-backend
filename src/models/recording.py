from pydantic import BaseModel, ConfigDict


class Recording(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    artist_id: str
    title: str
    mbid_known: bool = False
