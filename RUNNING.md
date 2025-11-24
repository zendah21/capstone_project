# Running the Meal Planner (ADK Web)

This app is exposed at `meal_planner_agent.agent:app`. Use the runner provided (`run_adk.py`) or call ADK Web directly.

## 1) Install dependencies
```
pip install -r requirements.txt
```
(The runner also installs these on startup.)

## 2) Set identity and keys
- `ASSISTANT_USER_ID` (required for per-user partitioning; defaults to `user` if unset)
- `ASSISTANT_SESSION_ID` (optional; set per tab/run if you want session isolation)
- `MAPBOX_ACCESS_TOKEN` (store finder)
- `GOOGLE_MAPS_API_KEY` (restaurant MCP)

You can also pass `user_id`/`session_id` via your runner; `execute_sql` will auto-inject them into SQL params.

## 3) Start the server
Option A (runner):
```
python run_adk.py --host 0.0.0.0 --port 8080
```

Option B (direct ADK Web, if installed):
```
python -m google.adk.web --app meal_planner_agent.agent:app --host 0.0.0.0 --port 8080
# or
adk web --app meal_planner_agent.agent:app --host 0.0.0.0 --port 8080
```

Open http://localhost:8080 to chat.

## 4) How data is partitioned
- `execute_sql` injects `:user_id` (and `:session_id` when provided). Use those in your SQL for per-user or per-session isolation.
- `load_memory` is available for semantic long-term recall; session context is handled automatically by ADK per tab.

## 5) Outputs and schemas
- Core planner: `MealPlanOutput` (`meal_plan_json`)
- Profile filler: `MealProfileOutput` (`profile_result`)
- Shopping list: `ShoppingListOutput` (`shopping_list_result`)
- Store finder: `StoreFinderOutput` (`store_finder_result`)
- Restaurant: natural language only (no schema)
- Orchestrator: no schema; must rewrite all structured outputs to plain language for the user.

## 6) Tool output hygiene
Orchestrator must never surface raw JSON or tool payloads. Always rewrite tool/agent results into user-friendly text before replying.***
