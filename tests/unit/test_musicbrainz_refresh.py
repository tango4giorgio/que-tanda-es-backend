import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from scripts.refresh_musicbrainz_cache import derive_cache_row


def fixture(name: str) -> dict:
    path = Path(__file__).parents[1] / "fixtures" / "musicbrainz" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_refresh_derives_only_unambiguous_artist() -> None:
    row = derive_cache_row(
        UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        fixture("eligible.json"),
        datetime.now(UTC),
    )

    assert row.metadata_status == "eligible"
    assert row.answer_artist_id == UUID("11111111-1111-1111-1111-111111111111")
    assert row.answer_artist_name == "Example Orchestra"


def test_refresh_rejects_ambiguous_credit() -> None:
    row = derive_cache_row(
        UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        fixture("ambiguous-credit.json"),
        datetime.now(UTC),
    )

    assert row.metadata_status == "ambiguous_credit"
    assert row.answer_artist_id is None
