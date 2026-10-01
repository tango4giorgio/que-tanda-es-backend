"""Provider adaptors that resolve playable preview URLs from provider track identifiers."""

from collections.abc import Iterable
from typing import Protocol

import httpx

_DEEZER_API_URL = "https://api.deezer.com"


class ProviderResolutionError(RuntimeError):
    """Raised when a provider cannot be contacted or returns an invalid response."""


class PreviewProviderAdaptor(Protocol):
    """Resolves a provider-specific track identifier to a playable preview URL."""

    provider: str

    def resolve_preview_url(self, provider_track_id: str) -> str | None:
        """Return an HTTPS MP3 preview URL, or ``None`` when none is available."""


class DeezerPreviewAdaptor:
    """Resolves Deezer tracks through the public Deezer track-details API."""

    provider = "deezer"

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    def resolve_preview_url(self, provider_track_id: str) -> str | None:
        try:
            with httpx.Client(
                base_url=_DEEZER_API_URL,
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.get(f"/track/{provider_track_id}")
        except httpx.HTTPError as error:
            raise ProviderResolutionError("Deezer track lookup failed") from error

        if response.status_code == 404:
            return None
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPStatusError, ValueError) as error:
            raise ProviderResolutionError("Deezer returned an invalid track response") from error

        if not isinstance(payload, dict):
            raise ProviderResolutionError("Deezer returned an invalid track response")
        if "error" in payload:
            return None

        preview_url = payload.get("preview")
        if not isinstance(preview_url, str) or not preview_url.startswith("https://"):
            return None
        return preview_url


class PreviewProviderAdaptors:
    """Registry of adaptors supported by the preview service."""

    def __init__(self, adaptors: Iterable[PreviewProviderAdaptor]) -> None:
        registered_adaptors = list(adaptors)
        self._adaptors = {adaptor.provider: adaptor for adaptor in registered_adaptors}
        if len(self._adaptors) != len(registered_adaptors):
            raise ValueError("Each preview provider must have exactly one adaptor")

    def supports(self, provider: str) -> bool:
        return provider in self._adaptors

    def resolve_preview_url(self, provider: str, provider_track_id: str) -> str | None:
        adaptor = self._adaptors.get(provider)
        if adaptor is None:
            return None
        return adaptor.resolve_preview_url(provider_track_id)


def default_preview_provider_adaptors() -> PreviewProviderAdaptors:
    return PreviewProviderAdaptors([DeezerPreviewAdaptor()])
