from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, OpenAIError, RateLimitError
from pydantic import SecretStr
from qa_support import answer_json

from enterprise_knowledge_engine.qa.errors import QAError
from enterprise_knowledge_engine.qa.providers import FakeLLMProvider, OpenAIChatProvider
from enterprise_knowledge_engine.qa.schemas import GeneratedAnswer


def mock_openai(monkeypatch, completion=None, failure=None):
    client = MagicMock()
    if failure:
        client.chat.completions.create.side_effect = failure
    else:
        client.chat.completions.create.return_value = completion or SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=answer_json(), refusal=None),
                )
            ],
            model="test-structured-model",
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120),
        )
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    monkeypatch.setattr("enterprise_knowledge_engine.qa.providers.OpenAI", factory)
    return factory, client


def test_chat_adapter_uses_strict_schema_and_bounded_parameters(settings, monkeypatch):
    settings.openai_api_key = SecretStr("test-only-openai-key")
    factory, client = mock_openai(monkeypatch)
    response = OpenAIChatProvider(settings).generate(
        [
            {"role": "system", "content": "instruction"},
            {"role": "user", "content": "private source"},
        ]
    )
    args = client.chat.completions.create.call_args.kwargs
    assert args["response_format"]["type"] == "json_schema"
    assert args["response_format"]["json_schema"]["strict"] is True
    assert args["response_format"]["json_schema"]["schema"] == GeneratedAnswer.model_json_schema()
    assert args["model"] == settings.llm_model
    assert args["max_completion_tokens"] == settings.llm_max_output_tokens
    assert args["store"] is False
    assert "tools" not in args
    assert factory.call_args.kwargs["timeout"] == settings.llm_timeout_seconds
    assert factory.call_args.kwargs["max_retries"] == settings.llm_max_retries
    assert response.usage.input_tokens == 100
    assert response.usage.output_tokens == 20
    assert response.usage.total_tokens == 120
    assert response.model == "test-structured-model"


@pytest.mark.parametrize(
    "kind,code,status",
    [
        ("timeout", "llm_timeout", 504),
        ("rate_limit", "llm_rate_limited", 503),
        ("connection", "llm_unavailable", 503),
        ("other", "llm_request_failed", 502),
    ],
)
def test_chat_errors_are_safe(settings, monkeypatch, kind, code, status):
    settings.openai_api_key = SecretStr("test-only-openai-key")
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    failures = {
        "timeout": APITimeoutError(request=request),
        "rate_limit": RateLimitError(
            "private quota details", response=httpx.Response(429, request=request), body=None
        ),
        "connection": APIConnectionError(request=request, message="private connection details"),
        "other": OpenAIError("private prompt and credential"),
    }
    mock_openai(monkeypatch, failure=failures[kind])
    with pytest.raises(QAError) as error:
        OpenAIChatProvider(settings).generate([{"role": "user", "content": "private input"}])
    assert error.value.code == code
    assert error.value.status_code == status
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "finish,refusal,content,code",
    [
        ("length", None, "{}", "llm_incomplete_output"),
        ("stop", "provider refusal", None, "llm_refused"),
        ("stop", None, None, "llm_invalid_output"),
    ],
)
def test_incomplete_refused_or_empty_outputs_fail(
    settings, monkeypatch, finish, refusal, content, code
):
    settings.openai_api_key = SecretStr("test-only-openai-key")
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish, message=SimpleNamespace(refusal=refusal, content=content)
            )
        ],
        model="test-model",
        usage=None,
    )
    mock_openai(monkeypatch, completion)
    with pytest.raises(QAError) as error:
        OpenAIChatProvider(settings).generate([{"role": "user", "content": "question"}])
    assert error.value.code == code


def test_missing_usage_remains_null(settings, monkeypatch):
    settings.openai_api_key = SecretStr("test-only-openai-key")
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop", message=SimpleNamespace(refusal=None, content=answer_json())
            )
        ],
        model="test-model",
        usage=None,
    )
    mock_openai(monkeypatch, completion)
    assert OpenAIChatProvider(settings).generate([]).usage is None


def test_missing_chat_key_is_not_a_fake_fallback(settings):
    settings.openai_api_key = None
    with pytest.raises(QAError) as error:
        OpenAIChatProvider(settings).generate([])
    assert error.value.code == "llm_not_configured"


def test_default_fake_is_deterministic_and_abstains():
    provider = FakeLLMProvider()
    first = provider.generate([])
    assert first == provider.generate([])
    assert GeneratedAnswer.model_validate_json(first.content).status == "insufficient_evidence"
    assert first.usage is None


@pytest.mark.parametrize(
    "status,code", [(401, "llm_not_authorized"), (400, "llm_request_rejected")]
)
def test_permanent_provider_errors_are_classified(settings, monkeypatch, status, code):
    from openai import AuthenticationError, BadRequestError

    settings.openai_api_key = SecretStr("fixture-key")
    request = httpx.Request("POST", "https://example.invalid")
    error_type = AuthenticationError if status == 401 else BadRequestError
    failure = error_type("SECRET", response=httpx.Response(status, request=request), body=None)
    mock_openai(monkeypatch, failure=failure)
    with pytest.raises(QAError) as error:
        OpenAIChatProvider(settings).generate([{"role": "user", "content": "fixture"}])
    assert error.value.code == code
    assert "SECRET" not in str(error.value)
