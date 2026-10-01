import httpx
import pytest

from src.services.provider_url_resolver import (
    DeezerPreviewAdaptor,
    PreviewProviderAdaptors,
    ProviderResolutionError,
)


def test_deezer_adaptor_returns_the_https_mp3_preview_from_track_details() -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={"id": 123, "preview": "https://cdn.example/previews/123.mp3"},
        )

    adaptor = DeezerPreviewAdaptor(transport=httpx.MockTransport(handler))

    assert adaptor.resolve_preview_url("123") == "https://cdn.example/previews/123.mp3"
    assert str(captured["request"].url) == "https://api.deezer.com/track/123"


@pytest.mark.parametrize(
    "status_code,payload",
    [
        (404, {}),
        (200, {"error": {"message": "not found"}}),
        (200, {"id": 123}),
        (200, {"id": 123, "preview": "http://cdn.example/previews/123.mp3"}),
    ],
)
def test_deezer_adaptor_returns_none_when_no_https_preview_is_available(
    status_code: int, payload: dict[str, object]
) -> None:
    adaptor = DeezerPreviewAdaptor(
        transport=httpx.MockTransport(lambda request: httpx.Response(status_code, json=payload))
    )

    assert adaptor.resolve_preview_url("123") is None


def test_deezer_adaptor_raises_for_a_provider_failure() -> None:
    adaptor = DeezerPreviewAdaptor(
        transport=httpx.MockTransport(lambda request: httpx.Response(500, json={}))
    )

    with pytest.raises(ProviderResolutionError):
        adaptor.resolve_preview_url("123")


def test_registry_rejects_duplicate_provider_adaptors() -> None:
    adaptor = DeezerPreviewAdaptor()

    with pytest.raises(ValueError, match="exactly one adaptor"):
        PreviewProviderAdaptors([adaptor, adaptor])
