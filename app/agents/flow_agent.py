import os
import json
from pathlib import Path
from app.clock import clock

BASE_DIR = Path(__file__).resolve().parent.parent
MOCK_DATA_DIR = BASE_DIR / "mock_data"

def load_json(filename: str) -> list[dict]:
    path = MOCK_DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def run() -> dict:
    """
    Predicts gate bottleneck windows by correlating delayed arrivals with upcoming surge times.
    Surge times: Kickoff (0 mins), Halftime (45 mins).
    Returns:
        {"bottlenecks": [{"gate": "...", "predicted_bottleneck_time": int, "severity": "..."}]}
    """
    transit_schedule = load_json("transit_schedule.json")
    current_offset = clock.get_offset()
    
    bottlenecks = []
    
    # We analyze upcoming or very recent arrivals (e.g. within last 15 minutes to future)
    for arrival in transit_schedule:
        gate = arrival["gate"]
        scheduled = arrival["scheduled_offset"]
        actual = arrival["actual_offset"]
        passengers = arrival["passengers"]
        delay = actual - scheduled
        
        # Only check arrivals that haven't fully cleared yet (actual offset is current or future, or within last 10 mins)
        if actual < current_offset - 10:
            continue
            
        # Determine overlap with surge times:
        # Kickoff surge: sim_minutes -15 to +15
        # Halftime surge: sim_minutes 35 to 55
        is_near_kickoff = abs(actual - 0) <= 15
        is_near_halftime = abs(actual - 45) <= 15
        
        severity = "LOW"
        
        # If there is a delay or massive passenger count, classify severity
        if delay > 0 or passengers >= 1500:
            if passengers >= 2000 and (delay >= 20 or is_near_kickoff or is_near_halftime):
                severity = "HIGH"
            elif passengers >= 1200 or delay >= 15:
                severity = "MEDIUM"
            else:
                severity = "LOW"
                
        # If there is a delay and it overlaps with kickoff or halftime, elevate severity
        if delay > 0 and (is_near_kickoff or is_near_halftime):
            if severity == "MEDIUM":
                severity = "HIGH"
            elif severity == "LOW":
                severity = "MEDIUM"
                
        bottlenecks.append({
            "gate": gate,
            "predicted_bottleneck_time": actual,
            "severity": severity,
            "delay_minutes": delay,
            "passengers": passengers
        })
        
    return {"bottlenecks": bottlenecks}
