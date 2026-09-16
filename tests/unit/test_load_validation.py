import json

from scripts.load_provider_links import load


def test_loader_skips_source_without_musicbrainz_recording_id(tmp_path) -> None:
    source = tmp_path / "sources.json"
    source.write_text(
        json.dumps(
            {
                "recordings": [
                    {
                        "sources": [
                            {
                                "provider": "archive.org",
                                "url": "https://archive.org/download/example/track.mp3",
                            }
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    summary = load(source, dry_run=True)

    assert summary.sources == 0
    assert summary.skipped == 1


def test_loader_skips_invalid_provider_sources_and_reports_them(tmp_path, capsys) -> None:
    source = tmp_path / "sources.json"
    source.write_text(
        json.dumps(
            {
                "recordings": [
                    {
                        "musicBrainzRecordingId": ("5a5d9d31-64a7-4a5d-87bd-1934d7efbb84"),
                        "sources": [
                            {"url": "https://example.test/missing-provider.mp3"},
                            {
                                "provider": "archive.org",
                                "url": "not-a-url",
                            },
                            {
                                "provider": "archive.org",
                                "url": "https://example.test/invalid-duration.mp3",
                                "durationMs": 0,
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    summary = load(source, dry_run=True)

    assert summary.sources == 0
    assert summary.skipped == 3
    assert capsys.readouterr().err.count("Skipped provider source:") == 3
