# Chat Backend Proxy

A **FastAPI** server that acts as a secure proxy between your Streamlit frontend and the OpenAI API.

> **Security guarantee**: The `OPENAI_API_KEY` lives only in `.env` on the server. The Streamlit app never receives or touches it. The frontend authenticates with a separate `PROXY_API_KEY`.

---

## Project Structure

```
chat-backend/
├── app/
│   ├── __init__.py
│   ├── config.py        ← reads .env (OpenAI key lives here)
│   ├── main.py          ← FastAPI routes + auth middleware
│   ├── proxy.py         ← OpenAI async client wrapper
│   └── rag_bridge.py    ← HTTP bridge to the rag-app (optional)
├── run.py               ← launcher
├── requirements.txt
└── .env.example         ← copy to .env and fill in values
```

---

## Quick Start

### 1. Set up environment

```powershell
cd "c:\Users\thapas\Documents\chat test\chat-backend"

# Copy the env template
copy .env.example .env
```

Edit `.env` and fill in:
```env
OPENAI_API_KEY=sk-proj-your-real-key-here
PROXY_API_KEY=pick-a-strong-secret-phrase
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Run the server

```powershell
# Development (auto-reload)
python run.py --reload

# Production
python run.py --host 0.0.0.0 --port 8080
```

The server starts at **http://127.0.0.1:8080**

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | ❌ None | Liveness check |
| `GET` | `/models` | ✅ X-API-Key | List available models |
| `POST` | `/chat/completions` | ✅ X-API-Key | Streaming chat proxy |
| `POST` | `/rag/chat` | ✅ X-API-Key | RAG-augmented chat (optional) |

All protected routes require the `X-API-Key: <PROXY_API_KEY>` header.

---

## RAG Integration (Optional)

To enable RAG, set in `.env`:
```env
ENABLE_RAG=true
RAG_BACKEND_URL=http://localhost:8000   # port where rag-app runs
```

The `/rag/chat` endpoint forwards requests to the **rag-app backend** which holds its own `OPENAI_API_KEY`. No key duplication needed.

---

## Testing

```powershell
# Health check
curl http://localhost:8080/health

# Chat (replace with your PROXY_API_KEY)
curl -X POST http://localhost:8080/chat/completions `
  -H "X-API-Key: changeme-replace-with-strong-secret" `
  -H "Content-Type: application/json" `
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'
```

---

## Interactive Docs

Once running, visit:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc
