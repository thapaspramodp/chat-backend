from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── OpenAI (backend eyes only) ──────────────────────────────────────────
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    # ── Proxy auth ──────────────────────────────────────────────────────────
    # Streamlit sends this; the real OpenAI key is never exposed
    proxy_api_key: str = "changeme-replace-with-strong-secret"

    # ── CORS ────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501"

    # ── RAG bridge (optional) ────────────────────────────────────────────────
    # When true, /rag/chat forwards requests to the rag-app backend
    enable_rag: bool = False
    rag_backend_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
