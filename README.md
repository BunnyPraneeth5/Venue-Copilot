# FIFA World Cup 2026 - Venue Operations Copilot (PromptWars Challenge)

A GenAI-driven decision-support assistant designed for **Venue Operations Staff** managing FIFA World Cup 2026 matches.

This copilot addresses two major, unsolved tournament safety challenges:

1. **Rival Fan Section Mixing**: Preventing opposing, high-intensity fan sections from mixing beyond safe density thresholds.
2. **Ticketed vs. Actual Seat Presence**: Identifying discrepancies between ticket scans (turnstile entries) and actual concourse/seat presence (detecting dangerous concourse bottlenecks).

---

## 🌟 The Core Approach & Logic

### How it differs from "Smart Stadium Dashboards"

Traditional "smart stadium" tools are passive: they display pre-aggregated metrics on visual dashboard widgets, relying on operations staff to continuously monitor charts, look for anomalies, and guess appropriate interventions.

**This Copilot is active and reasoning-driven.** It takes a natural-language query from an operator (e.g., *"Should we redirect transit arrivals?"* or *"Are there any crowd safety issues in the east concourse?"*) and reasons *ad hoc* across multiple live telemetry signals in real time. It correlates data from three specialized context agents to form a cohesive situational report and outputs a concrete, single recommended action—all within seconds.

---

## 🏗️ System Architecture & Workflow

The system is composed of a FastAPI backend and a semantic, keyboard-accessible plain HTML/JS frontend:

```mermaid
graph TD
    Client[Web Browser Interface] -->|POST /query?sim_minutes=N| API[FastAPI Server]
    API -->|Orchestrate| Orchestrator[Orchestrator]
    Orchestrator -->|asyncio.gather| OA[Occupancy Agent]
    Orchestrator -->|asyncio.gather| FA[Fan Mix Agent]
    Orchestrator -->|asyncio.gather| FL[Flow Agent]
    
    OA -->|Query| Clock[Simulated Clock]
    FL -->|Query| Clock
    
    OA -->|Telemetry| Orchestrator
    FA -->|Telemetry| Orchestrator
    FL -->|Telemetry| Orchestrator
    
    Orchestrator -->|Combined Data + Question| DA[Decision Agent]
    DA -->|System Prompt + Guards| Gemini[Gemini 2.5 Flash]
    Gemini -->|Action Recommendation| DA
    DA -->|Answer| Orchestrator
    Orchestrator -->|Response JSON| API
    API -->|Display Answer & Telemetry| Client
```

1. **Simulated Clock (`app/clock.py`)**: Uses context variables to manage request-scoped simulation offsets (`?sim_minutes=N`). The clock's kickoff is set to a constant reference time (`2026-06-15 18:00:00`) independent of the server's real wall-clock, ensuring data consistency for judges at any date.
2. **Occupancy Agent (`app/agents/occupancy_agent.py`)**: Compares turnstile scans against estimated seated presence to detect concourse build-ups.
3. **Fan Mix Agent (`app/agents/fan_mix_agent.py`)**: Evaluates section ticket distributions to compute rival fan density risk.
4. **Flow Agent (`app/agents/flow_agent.py`)**: Predicts gate bottleneck windows by correlating delayed transit schedules with upcoming kickoff/halftime surges.
5. **Provider Registry (`app/provider_registry.py`)**: Maintains agent operational states (`ACTIVE`, `DEGRADED`, `DISABLED`). If any agent fails or times out, the orchestrator registers it as `DEGRADED` and continues utilizing the remaining agents without crashing.
6. **Decision Agent (`app/agents/decision_agent.py`)**: Feeds gathered data and the user query to Gemini. It uses a rigorous system instruction set to act as a prompt-injection guardrail, ensuring user questions are treated purely as *data* rather than commands. Answers are restricted to under 150 words and conclude with one concrete action.

---

## 🚀 How to Run Locally

### Prerequisites

- Python 3.11 or Python 3.12 installed.
- A Gemini API key.

### Setup and Running

1. Clone the repository and navigate to the directory:

   ```bash
   cd promptwars-venue-copilot
   ```

2. Create a virtual environment and activate it:

   ```bash
   python -m venv venv
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory and add your Gemini API Key:

   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   ```

5. Run the FastAPI server:

   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

6. Open your web browser and visit:
   `http://localhost:8000/static/index.html`

---

## 🧪 Running Automated Tests

Run the test suite using pytest to verify agent calculations, simulated clock offsets, API endpoints, rate limiting, and agent error-isolation:

```bash
python -m pytest
```

---

## 🚀 Deployment Instructions

This app is optimized to deploy directly on free-tier platforms such as **Render**, **Railway**, or **Fly.io**:

1. **Deploying on Render**:
   - Create a new **Web Service** linked to your repository.
   - Select **Python** as the environment.
   - Use Build Command: `pip install -r requirements.txt`
   - Use Start Command: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - In Environment Settings, add key `GEMINI_API_KEY` with your API credentials.

---

## 📝 Critical Assumptions

- **Mock Data**: Since real-time stadium sensor feeds, turnstile gates, and transit arrival logs are not publicly accessible, all data inputs are simulated.
- **Simulated Clock**: A simulated clock is intentionally implemented rather than using the system's real datetime. This guarantees that whenever a evaluator runs the project (regardless of timezone, date, or year), the timeline aligns perfectly with the mock data offsets.
