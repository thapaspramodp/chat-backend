"""
main.py — FastAPI proxy server entry point.

Security model:
  - OPENAI_API_KEY lives in .env — never forwarded to any client
  - Frontend (Streamlit) authenticates with PROXY_API_KEY only
  - /chat/completions  → OpenAI (via proxy.py, streaming)
  - /rag/chat          → rag-app backend (via rag_bridge.py, streaming)
  - /health            → liveness check (no auth required)
"""
from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import json

from .config import settings
from .proxy import stream_chat_completion
from .rag_bridge import stream_rag_response

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Chat Backend Proxy",
    description=(
        "Secure proxy between Streamlit and OpenAI. "
        "The OpenAI API key is never exposed to the frontend."
    ),
    version="1.0.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth dependency ───────────────────────────────────────────────────────────
def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """
    Validates the proxy API key sent by the frontend.
    This is NOT the OpenAI key — it's the PROXY_API_KEY from .env.
    """
    if x_api_key != settings.proxy_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# ── Request / Response models ─────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str       # "system" | "user" | "assistant"
    content: str


class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None          # overrides server default if provided
    max_tokens: int = 1024
    temperature: float = 0.7
    stream: bool = True                  # always streamed; kept for API compat


class RagChatRequest(BaseModel):
    message: str


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
def health():
    """Liveness check — no auth required."""
    return {
        "status": "ok",
        "model": settings.openai_model,
        "rag_enabled": settings.enable_rag,
    }


@app.post("/chat/completions", tags=["chat"], dependencies=[Depends(require_api_key)])
async def chat_completions(req: ChatCompletionRequest):
    """
    Streaming chat completions proxy.

    The frontend sends messages; this endpoint forwards them to OpenAI
    using the server-side API key and streams tokens back.

    Headers required:
        X-API-Key: <PROXY_API_KEY>   (NOT the OpenAI key)
    """
    messages = [m.model_dump() for m in req.messages]

    async def token_generator():
        async for token in stream_chat_completion(
            messages=messages,
            model=req.model,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        ):
            yield token

    return StreamingResponse(token_generator(), media_type="text/plain")


@app.post("/rag/chat", tags=["rag"], dependencies=[Depends(require_api_key)])
async def rag_chat(req: RagChatRequest):
    """
    RAG-augmented chat proxy.

    Forwards the message to the existing rag-app backend (which holds its
    own OPENAI_API_KEY). Requires ENABLE_RAG=true in .env and the
    rag-app to be running at RAG_BACKEND_URL.

    Headers required:
        X-API-Key: <PROXY_API_KEY>   (NOT the OpenAI key)
    """
    async def rag_generator():
        async for chunk in stream_rag_response(req.message):
            yield chunk

    return StreamingResponse(rag_generator(), media_type="text/plain")


@app.get("/models", tags=["meta"], dependencies=[Depends(require_api_key)])
def list_models():
    """Returns available model options for the frontend dropdown."""
    return {
        "default": settings.openai_model,
        "available": [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-3.5-turbo",
        ],
        "rag_enabled": settings.enable_rag,
    }
