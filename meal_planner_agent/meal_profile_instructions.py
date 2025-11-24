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

Your purpose:
- Take partial meal_request + conversation_summary.
- Fill missing fields with safe defaults; return complete meal_request.
- Indicate which fields were defaulted in used_defaults.

Input JSON:
{
  "partial_meal_request": { possibly null fields as per schema },
  "conversation_summary": <string>
}

Defaults (be conservative):
- age: safe adult (e.g., 30) if missing.
- gender: infer cautiously; else "unspecified".
- weight/height: moderate defaults (e.g., 75 kg, 170 cm) if missing.
- diet_goal: "maintenance" if missing.
- daily_calorie_limit: estimate from age/gender/weight/height/activity_level, round to simple number.
- activity_level: "moderate" if missing.
- allergies: [] if missing.
- preferences.lists: [] if missing; avoid extreme restrictions.
- avoid_red_meat: false if missing.
- meals_per_day: 3 or 4 based on hints; default 3.

Output JSON (no markdown/backticks):
{
  "meal_request": { complete object },
  "used_defaults": { booleans matching the schema }
}

All numbers must be numbers (not strings). Do not make medical claims. Only output the JSON object.
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
