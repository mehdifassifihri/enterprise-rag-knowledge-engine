import httpx
import openai
import pytest


@pytest.mark.parametrize(
    "status,retry",
    [(400, False), (401, False), (403, False), (408, True), (409, True), (429, True), (503, True)],
)
def test_sdk_retry_policy_uses_mock_transport(monkeypatch, status, retry):
    """Exercise the installed real SDK without paid calls or real sleeps."""
    import openai._base_client as sdk

    calls, delays = [], []

    def handler(request):
        calls.append(request)
        if len(calls) == 1 or not retry:
            return httpx.Response(status, json={"error": {"message": "private fixture error"}})
        return httpx.Response(
            200,
            json={
                "data": [{"embedding": [1.0, 0.0], "index": 0}],
                "model": "fixture",
                "object": "list",
            },
        )

    monkeypatch.setattr(sdk.time, "sleep", delays.append)
    with openai.OpenAI(
        api_key="test-only",
        max_retries=1,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    ) as client:
        if retry:
            assert client.embeddings.create(input=["fixture"], model="fixture").data
        else:
            with pytest.raises(openai.APIStatusError):
                client.embeddings.create(input=["fixture"], model="fixture")
    assert len(calls) == (2 if retry else 1)
    assert all(0.375 <= delay <= 0.5 for delay in delays)


def test_sdk_backoff_is_exponential_bounded_and_exhausts(monkeypatch):
    import openai._base_client as sdk

    delays, calls = [], []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, json={"error": {"message": "fixture"}})

    monkeypatch.setattr(sdk.time, "sleep", delays.append)
    with openai.OpenAI(
        api_key="test-only",
        max_retries=2,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    ) as client:
        with pytest.raises(openai.APIStatusError):
            client.embeddings.create(input=["fixture"], model="fixture")
    assert len(calls) == 3
    assert 0.375 <= delays[0] <= 0.5
    assert 0.75 <= delays[1] <= 1.0


@pytest.mark.parametrize(
    "kind,code",
    [
        ("timeout", "embedding_timeout"),
        ("rate", "embedding_rate_limited"),
        ("auth", "embedding_not_authorized"),
        ("bad_request", "embedding_request_rejected"),
    ],
)
def test_embedding_failure_categories_are_safe(settings, monkeypatch, kind, code):
    from unittest.mock import MagicMock

    from pydantic import SecretStr

    from enterprise_knowledge_engine.ingestion.embeddings import OpenAIEmbeddingProvider
    from enterprise_knowledge_engine.ingestion.errors import IngestionError

    settings.openai_api_key = SecretStr("fixture-key")
    request = httpx.Request("POST", "https://example.invalid")
    errors = {
        "timeout": openai.APITimeoutError(request=request),
        "rate": openai.RateLimitError(
            "SECRET", response=httpx.Response(429, request=request), body=None
        ),
        "auth": openai.AuthenticationError(
            "SECRET", response=httpx.Response(401, request=request), body=None
        ),
        "bad_request": openai.BadRequestError(
            "SECRET", response=httpx.Response(400, request=request), body=None
        ),
    }
    client = MagicMock()
    client.embeddings.create.side_effect = errors[kind]
    monkeypatch.setattr(
        "enterprise_knowledge_engine.ingestion.embeddings.OpenAI", lambda **kw: client
    )
    with pytest.raises(IngestionError) as error:
        OpenAIEmbeddingProvider(settings).embed(["fixture"])
    assert error.value.code == code
    assert "SECRET" not in str(error.value)
    client.close.assert_called_once()
