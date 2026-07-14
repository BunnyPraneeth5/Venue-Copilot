import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MOCK_DATA_DIR = BASE_DIR / "mock_data"

def load_json(filename: str):
    path = MOCK_DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def run() -> dict:
    """
    Computes a rival-fan density score per section.
    Rival-fan density score is computed as (minority team tickets / total tickets in section).
    Returns:
        {"sections": [{"section": "...", "dominant_team": "...", "minority_team": "...", "density_pct": float}]}
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
        
        results.append({
            "section": section,
            "dominant_team": dominant_team,
            "minority_team": minority_team,
            "density_pct": round(density_pct, 1)
        })
        
    return {"sections": results}
