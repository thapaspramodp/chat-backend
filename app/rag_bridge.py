"""
rag_bridge.py — Thin HTTP bridge to the existing rag-app backend.

When ENABLE_RAG=true, requests to /rag/chat are forwarded to the
rag-app's /api/chat endpoint. This keeps OpenAI credentials isolated:
the rag-app already holds its own OPENAI_API_KEY and does RAG + streaming.

The bridge acts as a transparent pass-through — it does NOT add
any OpenAI key; that belongs to the rag-app's .env.
"""
import httpx
from typing import AsyncGenerator
from .config import settings


async def stream_rag_response(message: str) -> AsyncGenerator[str, None]:
    """
    Forward a chat message to the rag-app /api/chat endpoint and
    stream the response back token-by-token.

    If the rag-app is unavailable, yields an error message instead
    of crashing the whole backend.
    """
    if not settings.enable_rag:
        yield "[RAG is disabled. Set ENABLE_RAG=true and ensure the rag-app is running.]\n"
        return

    rag_url = f"{settings.rag_backend_url.rstrip('/')}/api/chat"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                rag_url,
                json={"message": message},
                headers={"Content-Type": "application/json"},
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_text():
                    if chunk:
                        yield chunk
    except httpx.ConnectError:
        yield (
            "\n[RAG backend is not reachable. "
            f"Check that the rag-app is running at {settings.rag_backend_url}]\n"
        )
    except httpx.HTTPStatusError as e:
        yield f"\n[RAG backend error: HTTP {e.response.status_code}]\n"
    except Exception as e:
        yield f"\n[Unexpected RAG bridge error: {e}]\n"
