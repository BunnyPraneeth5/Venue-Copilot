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
