import os
import json
from pathlib import Path
from app.clock import clock
from app.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent
MOCK_DATA_DIR = BASE_DIR / "mock_data"

def load_json(filename: str) -> list[dict]:
    path = MOCK_DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run() -> dict:
    """
    Compares turnstile scan counts against expected seated presence at the current simulated time.
    Flags sections with high concourse occupancy.
    
    Risk Level Breakpoints (Only computed if scanned_in >= 100):
    - LOW: gap_pct < 20.0 (or scanned_in < 100)
    - MEDIUM: 20.0 <= gap_pct <= 35.0
    - HIGH: gap_pct > 35.0 (exceeds threshold)
    
    Returns:
        {"sections": [{
            "section": "...", 
            "ticketed": int, 
            "scanned_in": int, 
            "estimated_seated": int, 
            "gap_pct": float,
            "risk_level": "HIGH" | "MEDIUM" | "LOW",
            "exceeds_threshold": bool
        }]}
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
        delay = settings.CONCOURSE_DELAYS.get(section, 10)
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
            
        # Determine risk level and threshold status
        if scanned_in >= settings.MIN_SCANNED_FOR_RISK:
            if gap_pct > settings.BOTTLENECK_GAP_THRESHOLD:
                risk_level = "HIGH"
                exceeds_threshold = True
            elif gap_pct >= 20.0:
                risk_level = "MEDIUM"
                exceeds_threshold = False
            else:
                risk_level = "LOW"
                exceeds_threshold = False
        else:
            risk_level = "LOW"
            exceeds_threshold = False

        results.append({
            "section": section,
            "ticketed": ticketed,
            "scanned_in": scanned_in,
            "estimated_seated": estimated_seated,
            "gap_pct": round(gap_pct, 1),
            "risk_level": risk_level,
            "exceeds_threshold": exceeds_threshold
        })
        
    return {"sections": results}

