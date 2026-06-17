"""
run.py — Launch the chat-backend proxy server.

Usage:
    python run.py
    python run.py --port 9000 --host 0.0.0.0
"""
import uvicorn
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chat Backend Proxy")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
