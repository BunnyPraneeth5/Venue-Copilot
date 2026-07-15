import os

class Config:
    # Rate limiting
    RATE_LIMIT: int = int(os.getenv("RATE_LIMIT", "10"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    TRUST_PROXY_HEADERS: bool = os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"

    # Agent settings
    AGENT_TIMEOUT: float = float(os.getenv("AGENT_TIMEOUT", "4.0"))
    
    # Concourse delays per section (in minutes)
    CONCOURSE_DELAYS: dict[str, int] = {
        "101": 30,
        "203": 30,
        "102": 10,
        "103": 10,
        "201": 10,
        "202": 10
    }

    # Gemini LLM model name
    GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

    # Risk thresholds
    DENSITY_RISK_THRESHOLD: float = float(os.getenv("DENSITY_RISK_THRESHOLD", "40.0"))
    BOTTLENECK_GAP_THRESHOLD: float = float(os.getenv("BOTTLENECK_GAP_THRESHOLD", "35.0"))
    MIN_SCANNED_FOR_RISK: int = int(os.getenv("MIN_SCANNED_FOR_RISK", "100"))

settings = Config()
