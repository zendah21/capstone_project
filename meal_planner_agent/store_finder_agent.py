from google.adk.agents import LlmAgent
from meal_planner_agent.config import MODEL_NAME, CORE_GEN_CONFIG
from meal_planner_agent.store_finder_tools import search_nearby_stores
from meal_planner_agent.store_finder_instructions import STORE_FINDER_INSTRUCTIONS
from google.adk.agents import LlmAgent
from meal_planner_agent.store_finder_instructions import StoreFinderOutput


store_finder_agent = LlmAgent(
    name="store_finder_agent",
    description="Finds nearby grocery stores for the user’s meal plan and explains the best options.",
    model=MODEL_NAME,
    instruction=STORE_FINDER_INSTRUCTIONS,
    generate_content_config=CORE_GEN_CONFIG,
    tools=[search_nearby_stores],
    # ADK structured output:
    output_schema=StoreFinderOutput,   # validated output schema
    output_key="store_finder_result",  # stored in state['store_finder_result']
)