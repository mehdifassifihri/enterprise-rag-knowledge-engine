from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import SecretStr

from enterprise_knowledge_engine.retrieval.errors import RetrievalError
from enterprise_knowledge_engine.retrieval.reranking import CohereReranker


def test_cohere_adapter_calls_real_endpoint_contract(settings, monkeypatch):
    settings.cohere_api_key = SecretStr("test-only-cohere-key")
    client = MagicMock()
    client.post.return_value.json.return_value = {
        "results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.1}]
    }
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    monkeypatch.setattr("enterprise_knowledge_engine.retrieval.reranking.httpx.Client", factory)
    result = CohereReranker(settings).rerank("money back", ["billing support", "refund policy"])
    assert [item.index for item in result] == [1, 0]
    call = client.post.call_args
    assert call.args[0] == "https://api.cohere.com/v2/rerank"
    assert call.kwargs["json"]["query"] == "money back"
    assert call.kwargs["json"]["top_n"] == 2
    assert call.kwargs["json"]["model"] == settings.reranker_model
    assert factory.call_args.kwargs["timeout"] == settings.reranker_timeout_seconds


def test_cohere_adapter_failure_is_safe(settings, monkeypatch):
    settings.cohere_api_key = SecretStr("test-only-cohere-key")
    client = MagicMock()
    client.post.side_effect = httpx.TimeoutException("private-key-and-text")
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    monkeypatch.setattr("enterprise_knowledge_engine.retrieval.reranking.httpx.Client", factory)
    with pytest.raises(RetrievalError) as error:
        CohereReranker(settings).rerank("private query", ["private text"])
    assert error.value.code == "reranker_unavailable"
    assert "private" not in str(error.value)


def test_cohere_missing_key_is_explicit(settings):
    settings.cohere_api_key = None
    with pytest.raises(RetrievalError) as error:
        CohereReranker(settings).rerank("hello", ["text"])
    assert error.value.code == "reranker_not_configured"
