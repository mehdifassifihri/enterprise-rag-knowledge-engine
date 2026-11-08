from typing import Literal
from uuid import UUID

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: PostgresDsn = Field(repr=False)
    api_key: SecretStr
    # The bootstrap key remains valid for /info; document access requires a tenant binding.
    api_key_tenant_id: UUID | None = None
    tenant_api_keys: dict[UUID, SecretStr] = Field(default_factory=dict, repr=False)
    revoked_api_key_hashes: set[str] = Field(default_factory=set, repr=False)
    embedding_max_retries: int = Field(default=1, ge=0, le=3)

    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=50 * 1024 * 1024)
    max_extracted_chars: int = Field(default=1_000_000, ge=100, le=2_000_000)
    max_pdf_pages: int = Field(default=200, ge=1, le=1000)
    pdf_timeout_seconds: int = Field(default=15, ge=1, le=60)
    chunk_size: int = Field(default=1500, ge=100, le=2000)
    chunk_overlap: int = Field(default=200, ge=0)
    max_chunks: int = Field(default=1000, ge=1, le=2000)
    embedding_provider: Literal["openai", "fake"] = "openai"
    embedding_model: Literal["text-embedding-3-small", "text-embedding-3-large"] = (
        "text-embedding-3-small"
    )
    embedding_dimensions: int = 1536
    embedding_batch_size: int = Field(default=32, ge=1, le=64)
    embedding_timeout_seconds: float = Field(default=20, ge=1, le=60)
    openai_api_key: SecretStr | None = None
    search_candidate_limit: int = Field(default=50, ge=50, le=200)
    search_rrf_k: int = Field(default=60, ge=1, le=1000)
    search_vector_strategy: Literal["exact", "hnsw"] = "exact"
    search_hnsw_ef_search: int = Field(default=100, ge=40, le=1000)
    reranker_provider: Literal["none", "cohere"] = "none"
    reranker_model: str = Field(default="rerank-v5.0-pro", min_length=1, max_length=100)
    reranker_max_candidates: int = Field(default=50, ge=50, le=200)
    reranker_timeout_seconds: float = Field(default=10, ge=1, le=30)
    cohere_api_key: SecretStr | None = None
    llm_provider: Literal["openai", "fake"] = "openai"
    llm_model: str = Field(default="gpt-4.1-mini", min_length=1, max_length=100)
    llm_timeout_seconds: float = Field(default=30, ge=1, le=120)
    llm_max_retries: int = Field(default=1, ge=0, le=3)
    llm_max_output_tokens: int = Field(default=1200, ge=128, le=4096)
    qa_default_top_k: int = Field(default=5, ge=1, le=20)
    qa_search_mode: Literal["vector", "keyword", "hybrid"] = "hybrid"
    qa_rerank: bool = False
    qa_max_sources: int = Field(default=8, ge=1, le=20)
    qa_context_char_budget: int = Field(default=12000, ge=512, le=24000)
    qa_max_passage_chars: int = Field(default=2000, ge=32, le=2000)
    qa_min_cosine_similarity: float = Field(default=0.2, ge=-1, le=1)
    qa_min_keyword_score: float = Field(default=0.0, ge=0, le=1)
    mcp_api_key: SecretStr | None = Field(default=None, repr=False)
    mcp_max_output_bytes: int = Field(default=262144, ge=4096, le=1048576)
    mcp_max_concurrent_calls: int = Field(default=1, ge=1, le=4)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    docs_enabled: bool = False
    db_pool_size: int = Field(default=5, ge=1, le=50)

    @field_validator("revoked_api_key_hashes")
    @classmethod
    def validate_revocations(cls, values: set[str]) -> set[str]:
        if any(
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value) for value in values
        ):
            raise ValueError("Revocations must be lowercase SHA-256 digests")
        return values

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32 or value.get_secret_value().startswith("REPLACE_"):
            raise ValueError("API_KEY must be a generated secret of at least 32 characters")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_driver(cls, value: PostgresDsn) -> PostgresDsn:
        if value.scheme != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return value

    @model_validator(mode="after")
    def validate_ingestion(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if self.embedding_dimensions != 1536:
            raise ValueError(
                "EMBEDDING_DIMENSIONS must match VECTOR(1536); change schema via migration"
            )
        keys = [self.api_key.get_secret_value()]
        for key in self.tenant_api_keys.values():
            self.validate_api_key(key)
            keys.append(key.get_secret_value())
        if len(set(keys)) != len(keys):
            raise ValueError("API keys must be unique across tenant bindings")
        return self
