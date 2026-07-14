import os
from fastapi import FastAPI, Request, HTTPException, status
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

app = FastAPI(title="FIFA World Cup 2026 Venue Operations Copilot")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom In-Memory Rate Limiter (Max 10 requests per minute per IP)
class RateLimiter:
    def __init__(self, limit: int = 10, window: int = 60):
        self.limit = limit
        self.window = window
        self.records = defaultdict(list)

    def is_limited(self, ip: str) -> bool:
        now = time.time()
        # Prune logs older than the sliding window
        self.records[ip] = [t for t in self.records[ip] if now - t < self.window]
        
        if len(self.records[ip]) >= self.limit:
            return True
        self.records[ip].append(now)
        return False

limiter = RateLimiter(limit=10, window=60)

class QueryRequest(BaseModel):
    question: str

@app.post("/query")
async def query(request: Request, payload: QueryRequest, sim_minutes: int = 0):
    # Check rate limit
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
def health():
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
