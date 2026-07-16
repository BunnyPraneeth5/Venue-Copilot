import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.provider_registry import provider_registry
import app.agents.decision_agent as decision_agent

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_gemini_api(monkeypatch):
    """
    Automatically mock the Gemini LLM API call for all integration tests
    to prevent external HTTP requests and ensure consistent test behavior.
    """
    async def mock_call_llm(prompt: str) -> str:
        return "Test recommendation: Deploy operations staff to Gate A immediately."
    monkeypatch.setattr(decision_agent, "call_llm", mock_call_llm)

def test_health_endpoint():
    provider_registry.reset()
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["providers"]["occupancy_agent"] == "ACTIVE"
    assert data["providers"]["fan_mix_agent"] == "ACTIVE"
    assert data["providers"]["flow_agent"] == "ACTIVE"

def test_root_redirect():
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"

def test_query_endpoint_success():
    payload = {"question": "Are there any current bottleneck risks?"}
    response = client.post("/query?sim_minutes=15", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "agent_data" in data
    assert data["answer"] == "Test recommendation: Deploy operations staff to Gate A immediately."
    
    agent_data = data["agent_data"]
    assert "occupancy_agent" in agent_data
    assert "fan_mix_agent" in agent_data
    assert "flow_agent" in agent_data
    assert agent_data["occupancy_agent"]["status"] == "ACTIVE"
    assert agent_data["occupancy_agent"]["data"] is not None

def test_rate_limiting():
    # Clear limiter state before running the test
    from app.main import limiter
    limiter.records.clear()
    
    payload = {"question": "Rate limit test query"}
    
    # Submit 10 consecutive requests (which should succeed)
    for _ in range(10):
        response = client.post("/query", json=payload)
        assert response.status_code == 200
        
    # The 11th request must fail with 429 Too Many Requests
    response = client.post("/query", json=payload)
    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit exceeded. Maximum 10 queries per minute."
    
    # Reset state afterwards
    limiter.records.clear()

def test_rate_limiting_x_forwarded_for(monkeypatch):
    from app.main import limiter
    from app.config import settings

    # Case A: TRUST_PROXY_HEADERS is False (default)
    # The X-Forwarded-For header should be ignored and the fallback client host should be used
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    limiter.records.clear()
    
    payload = {"question": "Forwarded header test A"}
    headers = {"X-Forwarded-For": "203.0.113.195, 70.41.3.18"}
    
    response = client.post("/query", json=payload, headers=headers)
    assert response.status_code == 200
    
    # "203.0.113.195" should NOT be tracked since we didn't trust proxy headers
    assert "203.0.113.195" not in limiter.records
    assert "testclient" in limiter.records  # client host fallback

    # Case B: TRUST_PROXY_HEADERS is True
    # The X-Forwarded-For header should be honored and the first IP in the list used
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    limiter.records.clear()
    
    payload = {"question": "Forwarded header test B"}
    headers = {"X-Forwarded-For": "203.0.113.195, 70.41.3.18"}
    
    response = client.post("/query", json=payload, headers=headers)
    assert response.status_code == 200
    
    # Assert that the rate limiter recorded the request under the first IP of X-Forwarded-For
    assert "203.0.113.195" in limiter.records
    assert len(limiter.records["203.0.113.195"]) == 1
    assert "70.41.3.18" not in limiter.records
    assert "testclient" not in limiter.records
    
    # Reset state afterwards
    limiter.records.clear()


def test_query_validation_empty_question():
    payload = {"question": ""}
    response = client.post("/query", json=payload)
    assert response.status_code == 422


def test_query_validation_too_long_question():
    payload = {"question": "a" * 600}
    response = client.post("/query", json=payload)
    assert response.status_code == 422


def test_cors_options_invalid_origin():
    headers = {
        "Origin": "https://evil.com",
        "Access-Control-Request-Method": "POST",
    }
    response = client.options("/query", headers=headers)
    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin != "https://evil.com"
    assert allow_origin != "*"

