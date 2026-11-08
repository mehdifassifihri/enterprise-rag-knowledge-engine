from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from enterprise_knowledge_engine.core.config import Settings
from enterprise_knowledge_engine.qa.errors import QAError
from enterprise_knowledge_engine.qa.prompts import ChatMessage
from enterprise_knowledge_engine.qa.schemas import GeneratedAnswer, TokenUsage


@dataclass(frozen=True)
class LLMCompletion:
    content: str
    model: str
    usage: TokenUsage | None = None


class LLMProvider(Protocol):
    model: str

    def generate(self, messages: Sequence[ChatMessage]) -> LLMCompletion: ...


class FakeLLMProvider:
    """Deterministic fixture provider. Unscripted fake mode always abstains."""

    model = "fake-llm-v1"

    def __init__(self, content: str | None = None) -> None:
        self.content = (
            content
            if content is not None
            else GeneratedAnswer(
                status="insufficient_evidence", claims=[], reason="insufficient_support"
            ).model_dump_json()
        )

    def generate(self, messages: Sequence[ChatMessage]) -> LLMCompletion:
        return LLMCompletion(content=self.content, model=self.model)


class OpenAIChatProvider:
    def __init__(self, config: Settings) -> None:
        self.config = config
        self.model = config.llm_model

    def generate(self, messages: Sequence[ChatMessage]) -> LLMCompletion:
        return self.generate_structured(
            messages, GeneratedAnswer.model_json_schema(), "grounded_answer"
        )

    def generate_structured(
        self, messages: Sequence[ChatMessage], schema: dict, schema_name: str
    ) -> LLMCompletion:
        key = self.config.openai_api_key
        if key is None or not key.get_secret_value():
            raise QAError("llm_not_configured", "Answer provider is not configured", 503)
        try:
            with OpenAI(
                api_key=key.get_secret_value(),
                timeout=self.config.llm_timeout_seconds,
                max_retries=self.config.llm_max_retries,
            ) as client:
                result = client.chat.completions.create(
                    model=self.model,
                    messages=list(messages),
                    max_completion_tokens=self.config.llm_max_output_tokens,
                    store=False,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "strict": True,
                            "schema": schema,
                        },
                    },
                )
            if not result.choices or result.choices[0].finish_reason != "stop":
                raise QAError(
                    "llm_incomplete_output", "Answer provider did not complete its response", 502
                )
            message = result.choices[0].message
            if message.refusal:
                raise QAError("llm_refused", "Answer provider declined the request", 502)
            if not message.content:
                raise QAError("llm_invalid_output", "Answer provider returned invalid output", 502)
            usage = None
            if result.usage is not None:
                usage = TokenUsage(
                    input_tokens=result.usage.prompt_tokens,
                    output_tokens=result.usage.completion_tokens,
                    total_tokens=result.usage.total_tokens,
                )
            return LLMCompletion(content=message.content, model=result.model, usage=usage)
        except APITimeoutError:
            raise QAError("llm_timeout", "Answer provider timed out", 504) from None
        except RateLimitError:
            raise QAError(
                "llm_rate_limited", "Answer provider is temporarily rate limited", 503
            ) from None
        except APIConnectionError:
            raise QAError("llm_unavailable", "Answer provider is unavailable", 503) from None
        except (AuthenticationError, PermissionDeniedError):
            raise QAError(
                "llm_not_authorized", "Answer provider authorization failed", 503
            ) from None
        except BadRequestError:
            raise QAError(
                "llm_request_rejected", "Answer provider rejected the request", 502
            ) from None
        except OpenAIError:
            raise QAError("llm_request_failed", "Answer provider request failed", 502) from None


def get_llm_provider(request: Request) -> LLMProvider:
    return build_llm_provider(request.app.state.settings)


def build_llm_provider(config: Settings) -> LLMProvider:
    if config.llm_provider == "fake":
        return FakeLLMProvider()
    return OpenAIChatProvider(config)
