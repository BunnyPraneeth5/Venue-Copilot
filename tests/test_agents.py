import pytest
from app.clock import clock
from app.agents import occupancy_agent, fan_mix_agent, flow_agent
from app import orchestrator
from app.provider_registry import provider_registry, ProviderStatus
from datetime import datetime

def test_simulated_clock():
    # Verify default state (0 minutes offset)
    clock.set_offset(0)
    assert clock.get_offset() == 0
    assert clock.now() == datetime(2026, 6, 15, 18, 0, 0)

    # Verify advanceable state
    clock.set_offset(30)
    assert clock.get_offset() == 30
    assert clock.now() == datetime(2026, 6, 15, 18, 30, 0)

def test_occupancy_agent():
    # Test offset at kickoff (0 minutes)
    clock.set_offset(0)
    data = occupancy_agent.run()
    assert "sections" in data
    assert len(data["sections"]) == 6
    
    # Section 101 has capacity 500. Let's inspect the results:
    s101 = next(s for s in data["sections"] if s["section"] == "101")
    assert s101["ticketed"] == 500
    # Scanned-in at t=0 should be 50 + 80 + 120 + 150 + 70 = 470
    assert s101["scanned_in"] == 470
    # Seated estimate at t=0 for Section 101 (30 mins concourse delay)
    # is cumulative scans up to t=-30 mins: 50 + 80 + 120 = 250
    assert s101["estimated_seated"] == 250
    # Gap percentage: (470 - 250) / 470 = 46.8%
    assert s101["gap_pct"] == 46.8

def test_fan_mix_agent():
    data = fan_mix_agent.run()
    assert "sections" in data
    assert len(data["sections"]) == 6

    # Section 101 has 260 USA and 240 Mexico. Total = 500.
    # Minority is Mexico (240). Mixing ratio = 240 / 500 = 48.0%
    s101 = next(s for s in data["sections"] if s["section"] == "101")
    assert s101["dominant_team"] == "USA"
    assert s101["minority_team"] == "Mexico"
    assert s101["density_pct"] == 48.0

    # Section 203 has 250 USA and 250 Mexico. Total = 500.
    # Minority is USA (250). Mixing ratio = 250 / 500 = 50.0%
    s203 = next(s for s in data["sections"] if s["section"] == "203")
    assert s203["density_pct"] == 50.0

def test_flow_agent():
    # Test at kickoff (0 minutes offset)
    clock.set_offset(0)
    data = flow_agent.run()
    assert "bottlenecks" in data
    
    # Gate A has arrival T_A2 at sim_minutes 10 (passengers=2200, scheduled=-15, delay=25)
    # Since actual=10 is >= 0 - 10, it should be listed.
    gate_a = next((b for b in data["bottlenecks"] if b["gate"] == "Gate A"), None)
    assert gate_a is not None
    assert gate_a["severity"] == "HIGH"
    assert gate_a["delay_minutes"] == 25
    assert gate_a["passengers"] == 2200

@pytest.mark.asyncio
async def test_orchestrator_graceful_degradation(monkeypatch):
    # Reset health statuses before testing
    provider_registry.reset()
    assert provider_registry.get_status("occupancy_agent") == ProviderStatus.ACTIVE

    # Mock decision_agent.run to return a simple mock response
    async def mock_decision_run(question, agent_data):
        return "Mock decision response"
    
    import app.agents.decision_agent as dec_agent
    monkeypatch.setattr(dec_agent, "run", mock_decision_run)

    # Monkeypatch occupancy_agent.run to throw an exception
    def failing_run():
        raise RuntimeError("Sensor failure")
        
    monkeypatch.setattr(occupancy_agent, "run", failing_run)

    # Execute orchestrator
    result = await orchestrator.handle_query("Is everything safe?")
    
    # Verify that orchestrator did not crash
    assert result["answer"] == "Mock decision response"
    # Verify that failed agent is marked as DEGRADED
    assert result["agent_data"]["occupancy_agent"]["status"] == "DEGRADED"
    assert result["agent_data"]["occupancy_agent"]["data"] is None
    assert provider_registry.get_status("occupancy_agent") == ProviderStatus.DEGRADED

    # Verify other agents completed successfully
    assert result["agent_data"]["fan_mix_agent"]["status"] == "ACTIVE"
    assert result["agent_data"]["fan_mix_agent"]["data"] is not None

    # Reset registry after test
    provider_registry.reset()
