from typing import List
from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent

from meal_planner_agent.config import CORE_GEN_CONFIG, MODEL_NAME


# ========= Pydantic schemas for ADK structured output =========

class Preferences(BaseModel):
    likes: List[str] = Field(default_factory=list, description="Foods the user likes.")
    dislikes: List[str] = Field(default_factory=list, description="Foods the user dislikes.")
    cuisine_preferences: List[str] = Field(
        default_factory=list,
        description="Preferred cuisines (e.g. 'Italian', 'Middle Eastern')."
    )
    avoid_red_meat: bool = Field(
        default=False,
        description="True if the user wants to avoid red meat."
    )


class MealRequest(BaseModel):
    age: int = Field(description="User age in years.")
    gender: str = Field(description="User gender.")
    weight: float = Field(description="User weight in kilograms.")
    height: float = Field(description="User height in centimeters.")
    diet_goal: str = Field(
        description="Diet goal, e.g. 'muscle_gain', 'fat_loss', or 'maintenance'."
    )
    daily_calorie_limit: float = Field(
        description="Target daily calorie intake for the plan."
    )
    activity_level: str = Field(
        description="Activity level: 'low', 'moderate', or 'high'."
    )
    allergies: List[str] = Field(
        default_factory=list,
        description="List of allergies or intolerances (e.g. 'lactose')."
    )
    preferences: Preferences = Field(description="User food and cuisine preferences.")
    meals_per_day: int = Field(description="Number of meals per day.")


class UsedDefaultsPreferences(BaseModel):
    likes: bool = Field(description="True if likes were defaulted.")
    dislikes: bool = Field(description="True if dislikes were defaulted.")
    cuisine_preferences: bool = Field(description="True if cuisine_preferences were defaulted.")
    avoid_red_meat: bool = Field(description="True if avoid_red_meat was defaulted.")


class UsedDefaults(BaseModel):
    age: bool
    gender: bool
    weight: bool
    height: bool
    diet_goal: bool
    daily_calorie_limit: bool
    activity_level: bool
    allergies: bool
    preferences: UsedDefaultsPreferences
    meals_per_day: bool


class MealProfileOutput(BaseModel):
    """
    Output of meal_profile_agent.

    - meal_request: fully-filled MealRequest used by downstream agents.
    - used_defaults: flags indicating which fields were defaulted.
    """
    meal_request: MealRequest
    used_defaults: UsedDefaults


# ========= Instructions (aligned with the schema above) =========

MEAL_PROFILE_INSTRUCTIONS = """
You are MealProfileAgent in a multi-agent meal-planning system.

Your purpose is to:
- Take PARTIAL user info about a `meal_request` plus conversation context.
- Fill in any missing fields with sensible, safe default values.
- Return a COMPLETE `meal_request` that can be used by MealPlannerCoreAgent.
- Indicate which fields were filled using defaults.

You receive a SINGLE JSON object with this structure:

{
  "partial_meal_request": {
    "age": <int or null>,
    "gender": <string or null>,
    "weight": <number or null>,
    "height": <number or null>,
    "diet_goal": <string or null>,
    "daily_calorie_limit": <number or null>,
    "activity_level": <string or null>,
    "allergies": [<string>] or null,
    "preferences": {
      "likes": [<string>] or null,
      "dislikes": [<string>] or null,
      "cuisine_preferences": [<string>] or null,
      "avoid_red_meat": <bool or null>
    } or null,
    "meals_per_day": <int or null>
  },
  "conversation_summary": <string>
}

Your tasks:

1. Use the partial fields + conversation_summary to infer or set reasonable defaults:
   - If age is missing, choose a safe adult age (e.g. 30).
   - If gender is missing, you MAY infer it cautiously from context; if unclear, pick "unspecified".
   - If weight/height are missing, choose moderate, non-extreme defaults (e.g. 75 kg, 170 cm).
   - If diet_goal is missing, default to "maintenance".
   - If daily_calorie_limit is missing, estimate a reasonable value using typical formulas based on
     age/gender/weight/height/activity_level and then round to a simple number (e.g. 2000, 2200, 2500).
   - If activity_level is missing, default to "moderate".
   - If allergies are missing, default to an empty list [].
   - If preferences.* are missing, default to empty lists and avoid extreme restrictions.
   - If avoid_red_meat is missing, default to false.
   - If meals_per_day is missing, default to 3 or 4 based on conversation hints.

2. Build a COMPLETE `meal_request` object with all fields filled:

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

3. Also return a `used_defaults` object describing which fields were filled using defaults:

{
  "age": <bool>,
  "gender": <bool>,
  "weight": <bool>,
  "height": <bool>,
  "diet_goal": <bool>,
  "daily_calorie_limit": <bool>,
  "activity_level": <bool>,
  "allergies": <bool>,
  "preferences": {
    "likes": <bool>,
    "dislikes": <bool>,
    "cuisine_preferences": <bool>,
    "avoid_red_meat": <bool>
  },
  "meals_per_day": <bool>
}

Your RESPONSE MUST be a SINGLE JSON object:

{
  "meal_request": { ...complete meal_request... },
  "used_defaults": { ...booleans matching the schema above... }
}

Constraints:
- Output MUST be valid JSON (no markdown, no backticks, no comments).
- All numeric fields must be numbers, not strings.
- Be conservative and safe in defaults; do NOT make medical claims.
"""


# ========= ADK agent with structured output (output_schema + output_key) =========

meal_profile_agent = LlmAgent(
    name="meal_profile_agent",
    description=(
        "Takes a partial meal_request plus conversation summary, fills in "
        "missing fields with sensible defaults, and returns a complete "
        "`meal_request` along with flags indicating which fields used defaults."
    ),
    model=MODEL_NAME,
    instruction=MEAL_PROFILE_INSTRUCTIONS,
    generate_content_config=CORE_GEN_CONFIG,
    # ADK structured output:
    output_schema=MealProfileOutput,   # validated output schema
    output_key="profile_result",       # stored in state['profile_result']
)
