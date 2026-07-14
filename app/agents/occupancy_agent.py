import os
import json
from pathlib import Path
from app.clock import clock

BASE_DIR = Path(__file__).resolve().parent.parent
MOCK_DATA_DIR = BASE_DIR / "mock_data"

# Normal sections have a 10-minute transit delay from turnstile to seat.
# High-density mixing sections (101, 203) have a 30-minute transit delay.
CONCOURSE_DELAYS = {
    "101": 30,
    "203": 30,
    "102": 10,
    "103": 10,
    "201": 10,
    "202": 10
}

def load_json(filename: str):
    path = MOCK_DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def run() -> dict:
    """
    Compares turnstile scan counts against expected seated presence at the current simulated time.
    Flags sections with high concourse occupancy.
    Returns:
        {"sections": [{"section": "...", "ticketed": int, "scanned_in": int, "estimated_seated": int, "gap_pct": float}]}
    """
    seating_manifest = load_json("seating_manifest.json")
    turnstile_stream = load_json("turnstile_stream.json")
    
    current_offset = clock.get_offset()
    results = []
    
    for item in seating_manifest:
        section = item["section"]
        ticketed = sum(item["tickets"].values())
        capacity = item["capacity"]
        
        # Calculate scanned-in count up to current time
        scanned_in = sum(
            event["count"] 
            for event in turnstile_stream 
            if event["section"] == section and event["sim_minutes_offset"] <= current_offset
        )
        
        # Calculate estimated seated based on the section's concourse delay
        delay = CONCOURSE_DELAYS.get(section, 10)
        estimated_seated = sum(
            event["count"]
            for event in turnstile_stream
            if event["section"] == section and event["sim_minutes_offset"] <= (current_offset - delay)
        )
        
        # Ensure estimated seated is bounded by scanned_in
        estimated_seated = min(estimated_seated, scanned_in)
        
        # gap_pct represents the percentage of scanned-in people who are not in their seats
        if scanned_in > 0:
            gap_pct = ((scanned_in - estimated_seated) / scanned_in) * 100
        else:
            gap_pct = 0.0
            
        results.append({
            "section": section,
            "ticketed": ticketed,
            "scanned_in": scanned_in,
            "estimated_seated": estimated_seated,
            "gap_pct": round(gap_pct, 1)
        })
        
    return {"sections": results}
