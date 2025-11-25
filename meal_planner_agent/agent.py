# meal_planner_agent/agent.py
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
- meal_planner_core_agent: strict JSON meal planner (MealPlanOutput schema).
- meal_profile_agent: fills missing profile fields (JSON).
- meal_ingredients_agent: turns plan into shopping list (JSON).
- store_finder_agent: uses Mapbox tool to find nearby stores (JSON).
- restaurant_agent: suggests restaurants when the user wants to eat out.
- root_agent (meal_planner_agent): orchestrator that talks to the user and
  NEVER returns raw JSON — only friendly natural language.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import (
    InMemoryCredentialService,
)
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools import load_memory
from google.adk.tools.tool_context import ToolContext

from meal_planner_agent.config import MODEL_NAME, ORCH_GEN_CONFIG
from meal_planner_agent.meal_planner_instructions import meal_planner_core_agent
from meal_planner_agent.meal_profile_instructions import meal_profile_agent
from meal_planner_agent.shopping_list_instructions import meal_ingredients_agent
from meal_planner_agent.store_finder_tools import search_nearby_stores
from meal_planner_agent.restaurant_agent import restaurant_agent
from meal_planner_agent.orchestrator_instructions import ORCHESTRATOR_INSTRUCTIONS

# Local subclass so the runner sees the root agent as coming from this package
class LocalLlmAgent(LlmAgent):
    pass


load_dotenv()

# SQLite DB path for dynamic structured memory
DB_PATH = os.getenv("ASSISTANT_DB_PATH", "assistant_data.db")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. SQLite helpers (DB layer)
# ---------------------------------------------------------------------------

def _get_identity_params(tool_context: ToolContext) -> Dict[str, Optional[str]]:
    """
    Derive stable identity values for DB partitioning.

    - user_id: required partition key. Falls back to "user" if none is provided.
    - session_id: optional; present only if the runner sets it (per-session isolation).
    """
    user_id = getattr(tool_context, "user_id", None) or os.getenv("ASSISTANT_USER_ID") or "user"
    session_id = getattr(tool_context, "session_id", None) or os.getenv("ASSISTANT_SESSION_ID")
    return {"user_id": user_id, "session_id": session_id}


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
    conn: Optional[sqlite3.Connection] = None
    try:
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
            cols = [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "notnull": row["notnull"],
                    "pk": row["pk"],
                }
                for row in cur.fetchall()
            ]
            result.append({"name": tname, "columns": cols})

        logger.info("inspect_schema tables=%d", len(result))
        return {"tables": result}
    finally:
        if conn is not None:
            conn.close()


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
        - ATTACH and PRAGMA are blocked.
        - Only one statement per call is allowed.

    Note:
        - The current ADK user_id is automatically injected into params
          under the key 'user_id'. You can safely use :user_id in SQL
          without adding it to params_json.
        - If the runner provides session_id, it is also injected as :session_id
          so you can isolate rows per session when needed.
    """
    sql_stripped = sql.strip().lower()

    # Basic safety guardrails
    if sql_stripped.startswith("drop "):
        raise ValueError("DROP statements are disabled for safety.")
    if sql_stripped.startswith("delete") and " where " not in sql_stripped:
        raise ValueError("DELETE without WHERE is disabled for safety.")
    if sql_stripped.startswith("attach "):
        raise ValueError("ATTACH statements are disabled for safety.")
    if "pragma" in sql_stripped:
        raise ValueError("PRAGMA statements are disabled for safety.")
    if sql_stripped.count(";") > 1:
        raise ValueError("Only single SQL statements are allowed.")

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

    # Inject partitioning keys so queries can use :user_id and optionally :session_id
    ids = _get_identity_params(tool_context)
    if "user_id" not in params:
        params["user_id"] = ids["user_id"]
    if ids["session_id"] and "session_id" not in params:
        params["session_id"] = ids["session_id"]

    conn: Optional[sqlite3.Connection] = None
    start = time.monotonic()
    try:
        conn = _get_connection()
        cur = conn.cursor()

        if expect_result:
            cur.execute(sql, params)
            rows = cur.fetchall()
            data = [{k: row[k] for k in row.keys()} for row in rows]
            logger.info(
                "execute_sql query=%s rows=%d duration_ms=%.2f",
                sql.split()[0].upper(),
                len(data),
                (time.monotonic() - start) * 1000,
            )
            return {
                "rows": data,
                "rowcount": len(data),
            }
        else:
            cur.execute(sql, params)
            affected = cur.rowcount
            conn.commit()
            logger.info(
                "execute_sql statement=%s affected=%d duration_ms=%.2f",
                sql.split()[0].upper(),
                affected,
                (time.monotonic() - start) * 1000,
            )
            return {"rowcount": affected}
    finally:
        if conn is not None:
            conn.close()


# ---------------------------------------------------------------------------
# 3. Root orchestrator agent
# ---------------------------------------------------------------------------

root_agent = LocalLlmAgent(
    name="meal_planner_agent",
    description=(
        "Conversational meal-planning assistant. Talks to the user, collects "
        "key fields for `meal_request`, optionally delegates missing-field "
        "handling to `meal_profile_agent`, then delegates to "
        "`meal_planner_core_agent` to generate the final plan. **It can also "
        "use `meal_ingredients_agent` to generate a shopping list.** It can also "
        "remember user profiles and preferences in a dynamic SQLite DB and "
        "via semantic memory and must ALWAYS convert any structured output "
        "(JSON, dictionaries, tool results) into natural language "
        "(paragraphs, bullet lists, tables) BEFORE replying to the user."
    ),
    model=MODEL_NAME,
    instruction=ORCHESTRATOR_INSTRUCTIONS,
    generate_content_config=ORCH_GEN_CONFIG,
    # Orchestrator can call sub-agents (no hand-off for store finder; handled via tool)
    sub_agents=[
        meal_planner_core_agent,
        meal_profile_agent,
        meal_ingredients_agent,
        restaurant_agent,
    ],
    tools=[load_memory, inspect_schema, execute_sql, search_nearby_stores],
)

# ---------------------------------------------------------------------------
# 4. App object for ADK Web
# ---------------------------------------------------------------------------

app = App(
    name="meal_planner_agent",
    root_agent=root_agent,
)

