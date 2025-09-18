from pydantic import BaseModel, Field
from typing import Optional

class ProduceMessage(BaseModel):
    """
    Pydantic model for validating incoming request messages for completions.
    """
    request_id: Optional[str] = None  # Unique identifier for the request, optional
    model: str = "gemma-3b-it"        # The AI model to use, with a default value
    prompt: str = Field(..., min_length=1) # The input prompt, required and must not be empty
    max_tokens: int                   # Maximum number of tokens to generate
    temperature: float = 0.8          # Sampling temperature for generation, with a default value
    stream: bool = False              # Whether to stream the response, with a default value
