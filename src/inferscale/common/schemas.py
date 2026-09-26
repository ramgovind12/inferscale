from typing import Literal, Optional
from pydantic import BaseModel, Field

class UsageSchema(BaseModel):
    """Schema for usage data."""

    model: str = Field(..., description="The model used for inference.")
    prompt_tokens: int = Field(..., description="The number of tokens in the prompt.")
    completion_tokens: int = Field(..., description="The number of tokens in the completion.")
    total_tokens: int = Field(..., description="The total number of tokens used.")

class InferenceRequestSchema(BaseModel):
    """Schema for an inference request."""

    request_id: str = Field(..., description="Unique identifier for the inference request.")
    model: str = Field(..., description="The model to be used for inference.")
    prompt: str = Field(..., description="The input prompt for the model.")
    max_tokens: Optional[int] = Field(None, description="The maximum number of tokens to generate.")
    temperature: Optional[float] = Field(None, description="Sampling temperature for randomness.")
    top_p: Optional[float] = Field(None, description="Nucleus sampling parameter.")
    n: Optional[int] = Field(None, description="Number of completions to generate.")
    stream: Optional[bool] = Field(False, description="Whether to stream the output or not.")
    stop: Optional[list[str]] = Field(None, description="List of stop sequences for generation.")
    presence_penalty: Optional[float] = Field(None, description="Penalty for new tokens based on their presence in the text so far.")
    frequency_penalty: Optional[float] = Field(None, description="Penalty for new tokens based on their frequency in the text so far.")

class InferenceResponseSchema(BaseModel):
    """Schema for an inference response."""

    id: str = Field(..., description="Unique identifier for the inference request.")
    object: Literal["inference"] = Field(..., description="Type of the object returned.")
    created: int = Field(..., description="Timestamp of when the inference was created.")
    model: str = Field(..., description="The model used for inference.")
    choices: list[dict] = Field(..., description="List of choices returned by the model.")
    usage: UsageSchema = Field(..., description="Usage data for the inference request.")