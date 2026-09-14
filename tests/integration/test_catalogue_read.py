import os

import pytest

from src.repositories.catalogue_repository import CatalogueRepository
from src.repositories.db import connection

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for Postgres integration tests",
)


def test_catalogue_repository_reads_only_usable_rows() -> None:
    with connection() as conn:
        repository = CatalogueRepository(conn)
        orchestras, tracks = repository.get_usable_catalogue()

    assert orchestras
    assert tracks
    assert all(track.is_usable for track in tracks)
