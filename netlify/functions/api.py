import json
from functools import lru_cache
from typing import List, Optional, AsyncGenerator
import httpx
from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from openai import AsyncOpenAI
from mangum import Mangum

# ── 1. Settings & Config ──────────────────────────────────────────────────────
class Settings(BaseSettings):
    # OpenAI (backend eyes only)
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    # Proxy auth — must match what the Streamlit app sends in X-API-Key
    proxy_api_key: str = "changeme-replace-with-strong-secret"

    # CORS origins
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501,https://loquacious-cheesecake-52cee0.netlify.app"

    # RAG bridge (optional)
    enable_rag: bool = False
    rag_backend_url: str = "http://localhost:8001"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra env variables in Netlify without crashing

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

# ── 2. OpenAI & HTTP Clients ──────────────────────────────────────────────────
_openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

# ── 3. Proxy Completion Generator ─────────────────────────────────────────────
async def stream_chat_completion(
    messages: List[dict],
    model: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Streams tokens directly from OpenAI Chat Completions API."""
    target_model = model or settings.openai_model
    try:
        stream = await _openai_client.chat.completions.create(
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
    except Exception as e:
        yield f"\n[OpenAI Proxy Error: {str(e)}]\n"

# ── 4. RAG Bridge Generator ───────────────────────────────────────────────────
async def stream_rag_response(message: str) -> AsyncGenerator[str, None]:
    """Passes messages transparently to the rag-app backend."""
    if not settings.enable_rag:
        yield "[RAG is disabled. Set ENABLE_RAG=true in Netlify variables and ensure your RAG app is running.]\n"
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
        yield f"\n[RAG backend not reachable at {settings.rag_backend_url}]\n"
    except httpx.HTTPStatusError as e:
        yield f"\n[RAG backend error: HTTP {e.response.status_code}]\n"
    except Exception as e:
        yield f"\n[Unexpected RAG bridge error: {e}]\n"

# ── 5. FastAPI App Setup ──────────────────────────────────────────────────────
app = FastAPI(
    title="Chat Backend Proxy (Serverless)",
    description="Secure FastAPI proxy wrapper running on Netlify Functions.",
    version="1.0.0",
)

# CORS Middleware
_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth dependency
def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    if x_api_key != settings.proxy_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")

# ── 6. Request / Response Models ──────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7
    stream: bool = True

class RagChatRequest(BaseModel):
    message: str

# ── 7. API Routes ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "model": settings.openai_model,
        "rag_enabled": settings.enable_rag,
    }

@app.post("/chat/completions", tags=["chat"], dependencies=[Depends(require_api_key)])
async def chat_completions(req: ChatCompletionRequest):
    messages = [m.model_dump() for m in req.messages]
    return StreamingResponse(
        stream_chat_completion(
            messages=messages,
            model=req.model,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        ),
        media_type="text/plain"
    )

@app.post("/rag/chat", tags=["rag"], dependencies=[Depends(require_api_key)])
async def rag_chat(req: RagChatRequest):
    return StreamingResponse(
        stream_rag_response(req.message),
        media_type="text/plain"
    )

@app.get("/models", tags=["meta"], dependencies=[Depends(require_api_key)])
def list_models():
    return {
        "default": settings.openai_model,
        "available": [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ],
        "rag_enabled": settings.enable_rag,
    }

# ── 8. Mangum Serverless Handler ──────────────────────────────────────────────
# Strip "/.netlify/functions/api" so FastAPI routes are matched relative to root (/)
handler = Mangum(app, api_gateway_base_path="/.netlify/functions/api")
