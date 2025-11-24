from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


# ========= ADK structured output schemas =========


class StoreResult(BaseModel):
    """
    One candidate store, normalized for the StoreFinderAgent.
    Can come from web search (no coordinates) or from a places API (with coords).
    """
    name: str = Field(description="Name of the store, supermarket, or hypermarket.")
    address: Optional[str] = Field(
        default=None,
        description="Human-readable store address or description if known."
    )
    lat: Optional[float] = Field(
        default=None,
        description="Latitude of the store, if available."
    )
    lng: Optional[float] = Field(
        default=None,
        description="Longitude of the store, if available."
    )
    distance_meters: Optional[float] = Field(
        default=None,
        description="Approximate distance from the user in meters, if available."
    )
    source: str = Field(
        description="Which provider this result came from (e.g. 'google_search', 'mapbox', 'internal')."
    )
    extra: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional extra metadata (rating, opening_hours, URL, etc.)."
    )


class StoreFinderOutput(BaseModel):
    """
    Output of store_finder_agent.

    - explanation: natural language summary / recommendation.
    - stores: list of candidate stores the agent considered.
    """
    explanation: str = Field(
        description="Natural language explanation of the recommended stores and how to choose."
    )
    stores: List[StoreResult] = Field(
        description="List of nearby stores the agent suggests or compares."
    )


# ========= Instructions (aligned with StoreFinderOutput) =========

STORE_FINDER_INSTRUCTIONS = """
You are StoreFinderAgent in a multi-agent meal-planning system.

ROLE
----
- You are NOT user-facing. You only talk to the orchestrator.
- Receive ONE JSON input and return ONE JSON matching StoreFinderOutput. No markdown fences.

LOCATION RULES
--------------
- Never ask for location. Use the query/user_location provided and do the best search you can.
- Food-only scope (supermarket, hypermarket, grocery, butcher, bakery, fish market, food markets in malls).

INPUT (do not echo)
- query: string describing the food-related store search (e.g., "supermarket in <area>").
- user_location: { "lat": <float>, "lng": <float> } or null/missing.
- max_results: integer.

TOOL
- Call search_nearby_stores once with query, user_location, max_results.

PROCESS
1) Call the tool.
2) Map each result to StoreResult (name, address, lat, lng, distance_meters, source, extra=raw).
3) Choose best options by proximity when available; you may return all.
4) Build explanation mentioning top 1-3 and approximate distance when present.

EMPTY RESULTS
- If no usable results, still return:
  { "explanation": "...could not find... you can usually find large supermarkets...", "stores": [] }

OUTPUT FORMAT
- Exactly one JSON object matching StoreFinderOutput. No extra keys, no fences, no commentary.
"""
