# Meal Planner Agent

Single-orchestrator meal-planning assistant built on Google ADK. The orchestrator is the only user-facing agent; specialist agents run as tools and all structured outputs are rewritten into natural language before replying.

## Prerequisites
- Python 3.11+
- `.env` with:
  - `MAPBOX_ACCESS_TOKEN` (store search)
  - Optional: `GOOGLE_API_KEY` / `GOOGLE_MAPS_API_KEY` if you add Google tools
  - Optional: `ASSISTANT_USER_ID`, `ASSISTANT_SESSION_ID`

## Install
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run the web UI
```bash
python -m google.adk.cli web . --host 0.0.0.0 --port 8000 --reload
```
Open http://localhost:8000 and select `meal_planner_agent`.

## Store search (Mapbox Search Box)
- Tool: `meal_planner_agent/store_finder_tools.py` (suggest + retrieve; Kuwait bias by default).
- CLI checks:
  - `python test_mapbox_stores.py` (prompts for a query; loads `.env`)
  - `python mapbox_search_loop.py` (interactive loop)

## Architecture
- Orchestrator (`agent.py`): only agent that talks to the user; calls specialist agents as tools via `AgentTool`.
- Sub-agents (tools):
  - `meal_profile_agent` (fill missing profile fields)
  - `meal_planner_core_agent` (generate meal plan JSON)
  - `meal_ingredients_agent` (shopping list)
  - `restaurant_agent` (restaurant suggestions)
  - `search_nearby_stores` (Mapbox POI lookup)
- Dynamic SQLite tools: `inspect_schema`, `execute_sql`; semantic memory via `load_memory`.

## Key files
- `meal_planner_agent/agent.py` — orchestrator wiring, tools, runner helper.
- `meal_planner_agent/orchestrator_instructions.py` — strict “no JSON to user” and rewrite rules.
- `meal_planner_agent/store_finder_tools.py` — Mapbox Search Box integration.
- `test_mapbox_stores.py`, `mapbox_search_loop.py` — quick Mapbox checks.

## Notes
- Sub-agent/tool outputs are always rewritten by the orchestrator; the Dev UI may show internal events for debugging.
- Store finder filters out non-Kuwait hits and tries to keep only store-like POIs; fallback returns all retrieved POIs if filters are too strict.
