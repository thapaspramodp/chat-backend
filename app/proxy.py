"""
proxy.py — Core OpenAI proxy logic.

The OpenAI client is constructed here using the server-side API key.
Streamlit (or any other frontend) NEVER touches the key.
"""
from typing import AsyncGenerator, List, Optional
from openai import AsyncOpenAI
from .config import settings

# Single shared async client — key stays server-side
_client = AsyncOpenAI(api_key=settings.openai_api_key)


class Message:
    """Simple message DTO."""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


async def stream_chat_completion(
    messages: List[dict],
    model: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """
    Streams tokens from OpenAI chat completions.
    Yields raw text chunks (not SSE formatted — FastAPI wraps them).
    """
    target_model = model or settings.openai_model

    stream = await _client.chat.completions.create(
        model=target_model,
        messages=messages,
        stream=True,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


async def single_chat_completion(
    messages: List[dict],
    model: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """
    Non-streaming completion — returns full response text.
    """
    target_model = model or settings.openai_model

    response = await _client.chat.completions.create(
        model=target_model,
        messages=messages,
        stream=False,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""
