from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class EmbeddingTask(StrEnum):
    PASSAGE = "retrieval.passage"
    QUERY = "retrieval.query"


class PassageEmbeddingRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=128)
    provider: str | None = None
    model: str | None = None
    dimension: int | None = Field(default=None, ge=1, le=4096)

    @field_validator("texts")
    @classmethod
    def reject_empty_texts(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("Embedding input must not contain empty text")
        return cleaned


class QueryEmbeddingRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    provider: str | None = None
    model: str | None = None
    dimension: int | None = Field(default=None, ge=1, le=4096)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Embedding input must not be blank")
        return value


class EmbeddingResponse(BaseModel):
    embeddings: list[list[float]]
    provider: str
    model: str
    dimension: int
