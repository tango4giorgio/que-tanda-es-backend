"""Resolves a playable preview URL from a track_provider's own stable identifier at serving
time, rather than persisting a URL that could expire (research.md §7)."""

_PROVIDER_URL_TEMPLATES: dict[str, str] = {
    "archive.org": "https://archive.org/download/{provider_track_id}/track.mp3",
    "deezer": "https://www.deezer.com/track/{provider_track_id}",
}


class UnknownProviderError(RuntimeError):
    """Raised when a track_provider's provider key has no known URL resolution rule."""


def resolve_preview_url(provider: str, provider_track_id: str) -> str:
    template = _PROVIDER_URL_TEMPLATES.get(provider)
    if template is None:
        raise UnknownProviderError(f"No URL resolution rule for provider {provider!r}")
    return template.format(provider_track_id=provider_track_id)


def supports_preview_provider(provider: str) -> bool:
    return provider in _PROVIDER_URL_TEMPLATES
