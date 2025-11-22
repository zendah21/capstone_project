from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.tools import load_memory
from google.adk.tools.tool_context import ToolContext
from google.genai import types as genai_types

from meal_planner_agent.config import CORE_GEN_CONFIG,MODEL_NAME

MEAL_PLANNER_INSTRUCTIONS = """
You are MealPlannerCoreAgent in a multi-agent system.

You receive a single JSON object called `meal_request` with this structure:

{
  "age": <int>,
  "gender": <string>,
  "weight": <number>,            // kg
  "height": <number>,            // cm
  "diet_goal": <string>,         // "muscle_gain", "fat_loss", "maintenance", etc.
  "daily_calorie_limit": <number>,
  "activity_level": <string>,    // "low", "moderate", "high"
  "allergies": [<string>],
  "preferences": {
    "likes": [<string>],
    "dislikes": [<string>],
    "cuisine_preferences": [<string>],
    "avoid_red_meat": <bool>
  },
  "meals_per_day": <int>
}

Your job:
1. Read the `meal_request`.
2. Generate a realistic ONE-DAY meal plan that respects:
   - daily_calorie_limit
   - diet_goal
   - allergies and intolerances
   - likes / dislikes
   - avoid_red_meat flag
   - meals_per_day
3. Respond with a SINGLE JSON object of this exact shape:

{
  "day": 1,
  "total_calories": <number>,
  "meals": [
    {
      "name": <string>,
      "description": <string>,
      "items": [<string>],
      "calories": <number>,
      "macros": {
        "protein": <number>,
        "carbs": <number>,
        "fat": <number>
      },
      "time_suggestion": <string>   // e.g. "08:00"
    },
    ...
  ],
  "notes": [<string>]
}

Constraints:
- Output MUST be valid JSON (no markdown, no backticks, no comments).
- All numeric fields must be numbers, not strings.
- total_calories should roughly equal the sum of meal calories.
"""

meal_planner_core_agent = LlmAgent(
    name="meal_planner_core_agent",
    description=(
        "Receives a `meal_request` JSON and returns a structured daily "
        "meal plan as JSON."
    ),
    model=MODEL_NAME,
    instruction=MEAL_PLANNER_INSTRUCTIONS,
    generate_content_config=CORE_GEN_CONFIG,
)


