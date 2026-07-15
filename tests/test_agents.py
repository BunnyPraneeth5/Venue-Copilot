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
    # Assert new risk classification fields
    assert s101["risk_level"] == "HIGH"
    assert s101["exceeds_threshold"] is True

    # Section 102 should be LOW risk (gap_pct = 14.0%)
    s102 = next(s for s in data["sections"] if s["section"] == "102")
    assert s102["risk_level"] == "LOW"
    assert s102["exceeds_threshold"] is False

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
    # Assert new risk classification fields
    assert s101["risk_level"] == "HIGH"
    assert s101["exceeds_threshold"] is True

    # Section 102 has 550 USA and 50 Mexico. Total = 600.
    # Minority is Mexico (50). Mixing ratio = 50 / 600 = 8.3%
    s102 = next(s for s in data["sections"] if s["section"] == "102")
    assert s102["density_pct"] == 8.3
    assert s102["risk_level"] == "LOW"
    assert s102["exceeds_threshold"] is False

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

@pytest.mark.parametrize("sim_minutes", [-30, 0, 45, 120])
def test_agents_boundary_offsets(sim_minutes):
    clock.set_offset(sim_minutes)
    
    # Run occupancy agent
    occ_data = occupancy_agent.run()
    assert "sections" in occ_data
    for s in occ_data["sections"]:
        assert "section" in s
        assert "scanned_in" in s
        assert "estimated_seated" in s
        assert "gap_pct" in s
        assert "risk_level" in s
        assert "exceeds_threshold" in s

    # Run flow agent
    flow_data = flow_agent.run()
    assert "bottlenecks" in flow_data
    for b in flow_data["bottlenecks"]:
        assert "gate" in b
        assert "severity" in b
        assert "delay_minutes" in b
        assert "passengers" in b

    # Run fan mix agent
    mix_data = fan_mix_agent.run()
    assert "sections" in mix_data
    for s in mix_data["sections"]:
        assert "section" in s
        assert "risk_level" in s
        assert "exceeds_threshold" in s

def test_fan_mix_threshold_boundaries(monkeypatch):
    # Test right at 40% boundary (USA: 600, Mexico: 400 -> 40%)
    manifest_40 = [{
        "section": "101",
        "capacity": 1000,
        "tickets": {
            "USA": 600,
            "Mexico": 400
        }
    }]
    
    monkeypatch.setattr(fan_mix_agent, "load_json", lambda filename: manifest_40)
    data = fan_mix_agent.run()
    s = data["sections"][0]
    assert s["density_pct"] == 40.0
    assert s["risk_level"] == "MEDIUM"
    assert s["exceeds_threshold"] is False

    # Test just above 40% boundary (USA: 599, Mexico: 401 -> 40.1%)
    manifest_40_1 = [{
        "section": "101",
        "capacity": 1000,
        "tickets": {
            "USA": 599,
            "Mexico": 401
        }
    }]
    monkeypatch.setattr(fan_mix_agent, "load_json", lambda filename: manifest_40_1)
    data = fan_mix_agent.run()
    s = data["sections"][0]
    assert s["density_pct"] == 40.1
    assert s["risk_level"] == "HIGH"
    assert s["exceeds_threshold"] is True

def test_occupancy_threshold_boundaries(monkeypatch):
    clock.set_offset(0)
    manifest = [{"section": "102", "capacity": 600, "tickets": {"USA": 600}}]
    
    # 90 scanned in total (< 100), 50 estimated seated -> gap = 44.4% (> 35%)
    # Under limit constraint, must be LOW and False
    stream_low_count = [
        {"section": "102", "sim_minutes_offset": -60, "count": 50},
        {"section": "102", "sim_minutes_offset": 0, "count": 40}
    ]
    
    monkeypatch.setattr(occupancy_agent, "load_json", lambda filename: manifest if filename == "seating_manifest.json" else stream_low_count)
    data = occupancy_agent.run()
    s = data["sections"][0]
    assert s["scanned_in"] == 90
    assert s["risk_level"] == "LOW"
    assert s["exceeds_threshold"] is False

    # 200 scanned in (>= 100), 130 seated -> gap = 35.0% -> MEDIUM and False
    stream_boundary_35 = [
        {"section": "102", "sim_minutes_offset": -60, "count": 130},
        {"section": "102", "sim_minutes_offset": 0, "count": 70}
    ]
    monkeypatch.setattr(occupancy_agent, "load_json", lambda filename: manifest if filename == "seating_manifest.json" else stream_boundary_35)
    data = occupancy_agent.run()
    s = data["sections"][0]
    assert s["scanned_in"] == 200
    assert s["gap_pct"] == 35.0
    assert s["risk_level"] == "MEDIUM"
    assert s["exceeds_threshold"] is False

    # 200 scanned in (>= 100), 129 seated -> gap = 35.5% -> HIGH and True
    stream_boundary_35_5 = [
        {"section": "102", "sim_minutes_offset": -60, "count": 129},
        {"section": "102", "sim_minutes_offset": 0, "count": 71}
    ]
    monkeypatch.setattr(occupancy_agent, "load_json", lambda filename: manifest if filename == "seating_manifest.json" else stream_boundary_35_5)
    data = occupancy_agent.run()
    s = data["sections"][0]
    assert s["scanned_in"] == 200
    assert s["gap_pct"] == 35.5
    assert s["risk_level"] == "HIGH"
    assert s["exceeds_threshold"] is True
