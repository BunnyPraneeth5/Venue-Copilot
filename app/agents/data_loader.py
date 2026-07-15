import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MOCK_DATA_DIR = BASE_DIR / "mock_data"

def load_json(filename: str) -> list[dict]:
    path = MOCK_DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

SEATING_MANIFEST = load_json("seating_manifest.json")
TURNSTILE_STREAM = load_json("turnstile_stream.json")
TRANSIT_SCHEDULE = load_json("transit_schedule.json")

# Pre-index turnstile stream by section, sorted by sim_minutes_offset
from collections import defaultdict
_by_section = defaultdict(list)
for event in TURNSTILE_STREAM:
    _by_section[event["section"]].append(event)

TURNSTILE_BY_SECTION = {
    sec: sorted(events, key=lambda e: e["sim_minutes_offset"])
    for sec, events in _by_section.items()
}
