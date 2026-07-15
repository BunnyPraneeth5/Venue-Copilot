import os
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import time
from collections import defaultdict

# Load environment variables from .env if present
load_dotenv()

from app.clock import clock
from app import orchestrator
from app.provider_registry import provider_registry
from app.config import settings

app = FastAPI(title="FIFA World Cup 2026 Venue Operations Copilot")

@app.get("/")
def redirect_to_static() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom In-Memory Rate Limiter (Max requests per window per IP)
class RateLimiter:
    def __init__(self, limit: int = settings.RATE_LIMIT, window: int = settings.RATE_LIMIT_WINDOW) -> None:
        self.limit = limit
        self.window = window
        self.records = defaultdict(list)

    def is_limited(self, ip: str) -> bool:
        now = time.time()
        # Prune logs older than the sliding window for all tracked IPs
        for k in list(self.records.keys()):
            self.records[k] = [t for t in self.records[k] if now - t < self.window]
            # Delete key if it's empty and we're not about to append to it
            if not self.records[k] and k != ip:
                del self.records[k]
        
        if len(self.records[ip]) >= self.limit:
            return True
        self.records[ip].append(now)
        return False

limiter = RateLimiter()

class QueryRequest(BaseModel):
    question: str

@app.post("/query")
async def query(request: Request, payload: QueryRequest, sim_minutes: int = 0) -> dict:
    # Check rate limit using X-Forwarded-For header if present, fallback to client host
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    if limiter.is_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 10 queries per minute."
        )
        
    # Configure simulated clock offset for this request context
    clock.set_offset(sim_minutes)
    
    # Process the query using the multi-agent orchestrator
    result = await orchestrator.handle_query(payload.question)
    return result

@app.get("/health")
def health() -> dict:
    # Return health status of all context agents
    return {
        "status": "healthy",
        "providers": provider_registry.get_all_statuses()
    }

# Ensure static files directory exists before mounting
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

# Mount the static directory for the single page application
app.mount("/static", StaticFiles(directory=static_dir), name="static")

if __name__ == "__main__":
    import uvicorn
    # Bind to PORT environment variable (default 8000) and host 0.0.0.0
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
