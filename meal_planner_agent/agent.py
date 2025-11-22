"""
ADK Web app: Multi-step Meal Planner + dynamic SQLite DB tools + session + memory.

Layers:
- Session: handled by ADK runtime (per chat session).
- Memory: via built-in `load_memory` tool (semantic across sessions).
- DB: SQLite (assistant_data.db) with fully dynamic schema:
      agent can CREATE/ALTER tables and INSERT/UPDATE/SELECT rows,
      with basic safety guards.

Tools (plain Python functions; ADK wraps them automatically):
- inspect_schema: see current tables and columns.
- execute_sql: run arbitrary SQL (CREATE TABLE, ALTER TABLE, INSERT, UPDATE, SELECT, ...).

Agents:
- meal_planner_core_agent:
    Low-level agent that accepts a JSON `meal_request` and returns a JSON meal plan.

- meal_profile_agent:
    Helper agent that takes partial user info + conversation context,
    fills missing fields with smart defaults, and returns a complete `meal_request`.

- root_agent (meal_planner_agent):
    User-facing orchestrator. Talks to the user, collects key fields,
    optionally delegates missing-field handling to `meal_profile_agent`,
    and only when the request is ready delegates to `meal_planner_core_agent`.
    It can also use SQLite + load_memory as long-term memory.

App:
- name: my_agent
- root_agent: meal_planner_agent
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import os

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.tools import load_memory
from google.adk.tools.tool_context import ToolContext
from google.genai import types as genai_types

from meal_planner_agent.config import MODEL_NAME,ORCH_GEN_CONFIG

from meal_planner_agent.meal_planner_instructions import meal_planner_core_agent
from meal_planner_agent.shopping_list_instructions import meal_ingredients_agent
from meal_planner_agent.meal_profile_instructions import meal_profile_agent
from meal_planner_agent.orchestrator_instructions import ORCHESTRATOR_INSTRUCTIONS

load_dotenv()

# SQLite DB path for dynamic structured memory
DB_PATH = os.getenv("ASSISTANT_DB_PATH", "assistant_data.db")


# ---------------------------------------------------------------------------
# 1. SQLite helpers (DB layer)
# ---------------------------------------------------------------------------

def _get_connection() -> sqlite3.Connection:
    """
    Open SQLite connection.

    We don't create any fixed tables here.
    The agent is free to design the schema using execute_sql().
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# 2. Dynamic DB tools (plain functions – no decorator)
# ---------------------------------------------------------------------------

def inspect_schema(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Inspect the current SQLite schema: list tables and their columns.

    Returns:
        {
          "tables": [
            {
              "name": "users",
              "columns": [
                {"name": "id", "type": "INTEGER", "notnull": 1, "pk": 1},
                ...
              ]
            },
            ...
          ]
        }
    """
    conn = _get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    tables = [row["name"] for row in cur.fetchall()]

    result: List[Dict[str, Any]] = []
    for tname in tables:
        cur.execute(f"PRAGMA table_info({tname});")
        cols = []
        for col in cur.fetchall():
            cols.append(
                {
                    "cid": col["cid"],
                    "name": col["name"],
                    "type": col["type"],
                    "notnull": col["notnull"],
                    "default_value": col["dflt_value"],
                    "pk": col["pk"],
                }
            )
        result.append({"name": tname, "columns": cols})

    conn.close()
    return {"tables": result}


def execute_sql(
    tool_context: ToolContext,
    sql: str,
    params_json: Optional[str] = None,
    expect_result: bool = False,
) -> Dict[str, Any]:
    """
    Execute arbitrary SQL against the SQLite DB with basic safety rules.

    Use this tool to:
    - CREATE TABLE / ALTER TABLE / CREATE INDEX ...
    - INSERT / UPDATE / DELETE (with WHERE)
    - SELECT to fetch rows

    Args:
        sql:
            The SQL statement to execute. It can contain named parameters like
            :user_id, :age, :goal, etc.
        params_json:
            Optional JSON-encoded dict of parameters, e.g.:
            '{"age": 25, "weight_kg": 90, "goal": "fat_loss"}'
        expect_result:
            True if you expect a result set (e.g. SELECT), False otherwise.

    Safety:
        - DROP TABLE is blocked.
        - DELETE without WHERE is blocked.

    Note:
        - The current ADK user_id is automatically injected into params
          under the key 'user_id'. You can safely use :user_id in SQL
          without adding it to params_json.
    """
    sql_stripped = sql.strip().lower()

    # Basic safety guardrails
    if sql_stripped.startswith("drop table"):
        raise ValueError("DROP TABLE is disabled for safety.")
    if sql_stripped.startswith("delete") and " where " not in sql_stripped:
        raise ValueError("DELETE without WHERE is disabled for safety.")

    params: Dict[str, Any] = {}
    if params_json:
        try:
            loaded = json.loads(params_json)
            if isinstance(loaded, dict):
                params = loaded
            else:
                raise ValueError("params_json must be a JSON object.")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid params_json, not valid JSON: {e}")

    # Inject the current ADK user_id so the agent can use :user_id
    user_id = getattr(tool_context, "user_id", "user")
    if "user_id" not in params:
        params["user_id"] = user_id

    conn = _get_connection()
    cur = conn.cursor()

    if expect_result:
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()

        data = [{k: row[k] for k in row.keys()} for row in rows]

        return {
            "rows": data,
            "rowcount": len(data),
        }
    else:
        cur.execute(sql, params)
        affected = cur.rowcount
        conn.commit()
        conn.close()
        return {"rowcount": affected}






# ---------------------------------------------------------------------------
# 8. Orchestrator agent – ROOT for ADK Web
# ---------------------------------------------------------------------------

root_agent = LlmAgent(
    name="meal_planner_agent",
    description=(
        "Conversational meal-planning assistant. Talks to the user, collects "
        "key fields for `meal_request`, optionally delegates missing-field "
        "handling to `meal_profile_agent`, then delegates to "
        "`meal_planner_core_agent` to generate the final plan. **It can also "
        "use `meal_ingredients_agent` to generate a shopping list.** It can also "
        "remember user profiles and preferences in a dynamic SQLite DB and "
        "via semantic memory."
    ),
    model=MODEL_NAME,
    instruction=ORCHESTRATOR_INSTRUCTIONS,
    generate_content_config=ORCH_GEN_CONFIG,
    # Orchestrator can call sub-agents
    sub_agents=[meal_planner_core_agent, meal_profile_agent, meal_ingredients_agent], # <--- ADDED meal_ingredients_agent
    # Tools: semantic memory + dynamic DB
)

# ---------------------------------------------------------------------------
# 9. App object for ADK Web
# ---------------------------------------------------------------------------

app = App(
    name="meal_planner_agent",
    root_agent=root_agent,
)
