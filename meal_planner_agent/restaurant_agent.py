import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from mcp import StdioServerParameters

from meal_planner_agent.config import CORE_GEN_CONFIG, MODEL_NAME

RESTAURANT_AGENT_INSTRUCTIONS = """  

You are the Restaurant Advisor Agent in the Meal Planner System.

Goals:
- Help users eat out/order from real restaurants using their diet profile (calories, allergies, preferences, goals).
- Be chat-friendly, positive, and concise.

Rules:
- Never invent restaurant names/menus/addresses. Use only results provided by the orchestrator.
- Output MUST be natural conversational text (no JSON, no code fences).
- If no results are provided, reassure and ask if they want to widen the search or adjust filters.

Behavior:
- Understand intent (e.g., vegetarian near me, biryani places open now, what to eat at Subway).
- Explain why options fit the user’s dietary needs; highlight safe/unsafe items for allergies/preferences.
- Keep responses friendly and real-data based.
"""


# Uses MCP-based Google Maps server; the API key is optional here so imports never fail.
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

restaurant_agent = LlmAgent(
    name="restaurant_agent",
    description=(
        "I am the Restaurant Finder. I assist the user in finding suitable "
        "restaurants based on their preferences, dietary restrictions, "
        "and current location. I can suggest places for dining out."
    ),
    model=MODEL_NAME,
    instruction=RESTAURANT_AGENT_INSTRUCTIONS,
    generate_content_config=CORE_GEN_CONFIG,
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=[
                        "-y",
                        "@modelcontextprotocol/server-google-maps",
                    ],
                    env={
                        "GOOGLE_MAPS_API_KEY": GOOGLE_MAPS_API_KEY,
                    },
                ),
            ),
        )
    ],
)
