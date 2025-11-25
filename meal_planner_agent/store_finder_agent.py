# meal_planner_agent/store_finder_agent.py
from google.adk.agents import LlmAgent

from meal_planner_agent.config import CORE_GEN_CONFIG, MODEL_NAME
from meal_planner_agent.store_finder_instructions import (
    StoreFinderOutput,
    STORE_FINDER_INSTRUCTIONS,
)
from meal_planner_agent.store_finder_tools import search_nearby_stores


# Sub-agent dedicated to store lookup; orchestrator rewrites its outputs.
store_finder_agent = LlmAgent(
    name="store_finder_agent",
    description="Finds nearby grocery stores for the user's meal plan and explains the best options.",
    model=MODEL_NAME,
    instruction=STORE_FINDER_INSTRUCTIONS,
    generate_content_config=CORE_GEN_CONFIG,
    tools=[search_nearby_stores],
    output_schema=StoreFinderOutput,
    output_key="store_finder_result",
)
