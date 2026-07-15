import os
import json
from pathlib import Path
from app.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent
MOCK_DATA_DIR = BASE_DIR / "mock_data"

def load_json(filename: str) -> list[dict]:
    path = MOCK_DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def run() -> dict:
    """
    Computes a rival-fan density score per section.
    Rival-fan density score is computed as (minority team tickets / total tickets in section).
    
    Risk Level Breakpoints:
    - LOW: density_pct < 20.0
    - MEDIUM: 20.0 <= density_pct <= 40.0
    - HIGH: density_pct > 40.0 (exceeds threshold)
    
    Returns:
        {"sections": [{
            "section": "...", 
            "dominant_team": "...", 
            "minority_team": "...", 
            "density_pct": float,
            "risk_level": "HIGH" | "MEDIUM" | "LOW",
            "exceeds_threshold": bool
        }]}
    """
    seating_manifest = load_json("seating_manifest.json")
    results = []
    
    for item in seating_manifest:
        section = item["section"]
        tickets = item["tickets"]
        total_tickets = sum(tickets.values())
        
        # Sort teams by ticket counts descending
        sorted_teams = sorted(tickets.items(), key=lambda x: x[1], reverse=True)
        
        dominant_team = sorted_teams[0][0] if len(sorted_teams) > 0 else "N/A"
        minority_team = sorted_teams[1][0] if len(sorted_teams) > 1 else "N/A"
        
        minority_count = sorted_teams[1][1] if len(sorted_teams) > 1 else 0
        
        density_pct = (minority_count / total_tickets) * 100 if total_tickets > 0 else 0.0
        
        # Determine risk level and threshold status
        if density_pct > settings.DENSITY_RISK_THRESHOLD:
            risk_level = "HIGH"
            exceeds_threshold = True
        elif density_pct >= 20.0:
            risk_level = "MEDIUM"
            exceeds_threshold = False
        else:
            risk_level = "LOW"
            exceeds_threshold = False

        results.append({
            "section": section,
            "dominant_team": dominant_team,
            "minority_team": minority_team,
            "density_pct": round(density_pct, 1),
            "risk_level": risk_level,
            "exceeds_threshold": exceeds_threshold
        })
        
    return {"sections": results}

