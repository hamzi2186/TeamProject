from pydantic import BaseModel, Field, field_validator


class LLMUsage(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class LLMGenerateRequest(BaseModel):
    system_prompt: str = Field(min_length=1, max_length=50_000)
    user_prompt: str = Field(min_length=1, max_length=50_000)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=800, ge=1, le=8192)
    consumer: str | None = None

    @field_validator("system_prompt", "user_prompt")
    @classmethod
    def reject_blank_prompts(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Prompt text must not be blank")
        return cleaned


class LLMGenerateResponse(BaseModel):
    text: str
    provider: str
    model: str
    usage: LLMUsage
