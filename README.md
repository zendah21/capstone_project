# Meal Planner Agent

Single-orchestrator meal-planning assistant built on Google ADK. The orchestrator collects user needs, delegates to sub-agents/tools, rewrites structured outputs into natural language, and can look up nearby food stores via Mapbox Search Box.

## Prerequisites
- Python 3.11+
- Environment variables in `.env`:
  - `MAPBOX_ACCESS_TOKEN` (for store search)
  - `GOOGLE_API_KEY` / `GOOGLE_MAPS_API_KEY` if you enable Google-backed tools
  - Optional: `ASSISTANT_USER_ID`, `ASSISTANT_SESSION_ID`

## Install
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run the web UI
```
python -m google.adk.cli web . --host 0.0.0.0 --port 8000 --reload
```
Open http://localhost:8000 and select `meal_planner_agent`.

## Store search tools (Mapbox Search Box)
- `meal_planner_agent/store_finder_tools.py` powers store lookup via suggest+retrieve.
- For quick CLI checks:
  - `python test_mapbox_stores.py` (prompts for a query)
  - `python mapbox_search_loop.py` (interactive loop)

## Agent notes
- The orchestrator is the only user-facing agent; sub-agents are internal.
- Sub-agents produce JSON; the orchestrator rewrites results to plain language before replying.
- Store finder filters to Kuwait by default; adjust `country`/`categories` in `search_nearby_stores` if needed.

## Testing
- Basic store lookup: run `python test_mapbox_stores.py` with your token set.
- Interactive loop: `python mapbox_search_loop.py`.

## Key files
- `meal_planner_agent/agent.py` — app wiring + runner helper.
- `meal_planner_agent/orchestrator_instructions.py` — orchestrator behavior and hygiene rules.
- `meal_planner_agent/store_finder_tools.py` — Mapbox Search Box integration.
- `meal_planner_agent/store_finder_agent.py` — store sub-agent definition.
- `test_mapbox_stores.py` / `mapbox_search_loop.py` — CLI checks for store search.
