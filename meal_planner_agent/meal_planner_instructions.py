from typing import List
from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent
from google.genai import types as genai_types

from meal_planner_agent.config import CORE_GEN_CONFIG, MODEL_NAME


# --------- OUTPUT SCHEMA FOR CORE AGENT (ADK STANDARD) ---------

class MealMacros(BaseModel):
    protein: float = Field(description="Protein grams for this meal.")
    carbs: float = Field(description="Carbohydrate grams for this meal.")
    fat: float = Field(description="Fat grams for this meal.")


class MealEntry(BaseModel):
    name: str = Field(description="Name of the meal, e.g. 'Breakfast Omelette'.")
    description: str = Field(description="Short description of the meal.")
    items: List[str] = Field(description="List of ingredient items for this meal.")
    calories: float = Field(description="Approximate calories for this meal.")
    macros: MealMacros = Field(description="Macronutrient breakdown for this meal.")
    time_suggestion: str = Field(
        description="Suggested time label, e.g. '08:00', 'Lunch', 'Evening snack'."
    )


class MealPlanOutput(BaseModel):
    day: int = Field(description="Day index of this plan (usually 1).")
    total_calories: float = Field(description="Total calories for the full day plan.")
    meals: List[MealEntry] = Field(description="List of meals for this day.")
    notes: List[str] = Field(
        description="Optional notes, tips, or warnings related to the plan."
    )


MEAL_PLANNER_INSTRUCTIONS = """
You are MealPlannerCoreAgent in a multi-agent system.

You receive a single JSON object called `meal_request` with this structure:

{
  "age": <int>,
  "gender": <string>,
  "weight": <number>,
  "height": <number>,
  "diet_goal": <string>,
  "daily_calorie_limit": <number>,
  "activity_level": <string>,
  "allergies": [<string>],
  "preferences": {
    "likes": [<string>],
    "dislikes": [<string>],
    "cuisine_preferences": [<string>],
    "avoid_red_meat": <bool>
  },
  "meals_per_day": <int>
}

You MUST respond ONLY with a JSON object that matches the MealPlanOutput schema:
{
  "day": <int>,
  "total_calories": <number>,
  "meals": [ ... MealEntry objects ... ],
  "notes": [<string>]
}

"""

meal_planner_core_agent = LlmAgent(
    name="meal_planner_core_agent",
    description=(
        "Core planner. Takes a `meal_request` JSON and returns a structured daily "
        "meal plan JSON that matches the MealPlanOutput schema."
        """PROFILE AGENT RESPONSE HANDLING RULE:
            The meal_profile_agent returns JSON internally.
            You MUST NOT show this JSON to the user.

            You must:
            - Extract the meaning internally
            - Summarize it in natural language
            - NEVER display the actual JSON structure, even partially
            - NEVER quote keys, brackets, or schema fields

            Example of correct behavior:
            "Great! I filled in the remaining details for your meal profile. You're all set!"

            Example of forbidden behavior:
            { "meal_request": ... }    ← NEVER ALLOWED
        """

    ),
    model=MODEL_NAME,
    instruction=MEAL_PLANNER_INSTRUCTIONS,
    generate_content_config=CORE_GEN_CONFIG,
    # ADK structured outputs:
    output_schema=MealPlanOutput,   # enforce schema
    output_key="meal_plan_json",    # saved in state['meal_plan_json']
)
