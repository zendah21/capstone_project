"""
Multi-step Meal Planner agents for Google ADK.

- meal_planner_core_agent:
    Low-level agent that accepts a JSON `meal_request` and returns a JSON meal plan.

- root_agent (meal_planner_agent):
    User-facing orchestrator. Talks to the user, collects all required fields,
    and only when they are complete delegates to meal_planner_core_agent.

Tunable attributes:
- MODEL_NAME, TEMPERATURE, TOP_P, TOP_K, MAX_OUTPUT_TOKENS
- SAFETY_SETTINGS using HarmCategory + HarmBlockThreshold
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.genai import types as genai_types

# ---------------------------------------------------------------------------
# 0. Global configuration knobs
# ---------------------------------------------------------------------------

# Which Gemini model to use for both agents
MODEL_NAME = "gemini-2.0-flash"

# Generation / sampling controls
TEMPERATURE_CORE = 0.35        # more deterministic, for strict JSON
TEMPERATURE_ORCH = 0.6         # a bit more chatty for the orchestrator

TOP_P = 0.9
TOP_K = 40

# Hard cap on tokens the model can output for one response
MAX_OUTPUT_TOKENS_CORE = 1200
MAX_OUTPUT_TOKENS_ORCH = 1600

# (You can use these constants in any external Runner / CLI wrapper if you want.)
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0

# Basic safety settings (use HarmBlockThreshold, NOT SafetyThreshold)
SAFETY_SETTINGS = [
    genai_types.SafetySetting(
        category=genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    genai_types.SafetySetting(
        category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    genai_types.SafetySetting(
        category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
]


# ---------------------------------------------------------------------------
# 1. System prompts
# ---------------------------------------------------------------------------

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

ORCHESTRATOR_INSTRUCTIONS = """
You are MealPlannerOrchestrator, the main user-facing agent.

Your responsibilities:
- Chat naturally with the user.
- When the user asks for a meal plan, collect ALL required fields for the
  `meal_request`:

  1) age (int)
  2) gender (string)
  3) weight (kg, number)
  4) height (cm, number)
  5) diet_goal ("muscle_gain", "fat_loss", "maintenance", etc.)
  6) daily_calorie_limit (number)
  7) activity_level ("low", "moderate", "high")
  8) allergies (list of strings; [] if none)
  9) preferences.likes (list of foods)
 10) preferences.dislikes (list of foods)
 11) preferences.cuisine_preferences (list of cuisines)
 12) preferences.avoid_red_meat (boolean)
 13) meals_per_day (int)

Rules:
- Use conversation history: do NOT ask for the same info twice unless needed.
- If anything is missing/unclear, ask short, direct questions.
- When all fields are available and consistent, create a JSON object:

  {
    "meal_request": {
      ... all collected fields ...
    }
  }

  and DELEGATE the meal-plan generation to the sub-agent
  `meal_planner_core_agent`.

- After the sub-agent returns the JSON meal plan:
  - Explain it in a friendly natural-language summary (meals, calories, notes).
  - Offer to show the raw JSON if the user wants it.

- Do not invent specific values (age, weight, calories, etc.) if the user did
  not provide them; instead, ask.
- Avoid medical claims. You are not a doctor.
"""

# ---------------------------------------------------------------------------
# 2. Helper: Build GenerateContentConfig for each agent
# ---------------------------------------------------------------------------

def build_generate_content_config(
    temperature: float,
    max_tokens: int,
) -> genai_types.GenerateContentConfig:
    """
    Construct a GenerateContentConfig with generation parameters and safety settings.
    This is the CORRECT way to pass these settings to LlmAgent in Google ADK.
    """
    return genai_types.GenerateContentConfig(
        temperature=temperature,
        top_p=TOP_P,
        top_k=TOP_K,
        max_output_tokens=max_tokens,
        safety_settings=SAFETY_SETTINGS,  # Include safety settings here
    )


CORE_GEN_CONFIG = build_generate_content_config(
    temperature=TEMPERATURE_CORE,
    max_tokens=MAX_OUTPUT_TOKENS_CORE,
)

ORCH_GEN_CONFIG = build_generate_content_config(
    temperature=TEMPERATURE_ORCH,
    max_tokens=MAX_OUTPUT_TOKENS_ORCH,
)

# ---------------------------------------------------------------------------
# 3. Core meal-planning agent (JSON → JSON)
# ---------------------------------------------------------------------------

meal_planner_core_agent = LlmAgent(
    name="meal_planner_core_agent",
    description=(
        "Receives a `meal_request` JSON and returns a structured daily "
        "meal plan as JSON."
    ),
    model=MODEL_NAME,
    instruction=MEAL_PLANNER_INSTRUCTIONS,
    generate_content_config=CORE_GEN_CONFIG,  # Use generate_content_config
)

# ---------------------------------------------------------------------------
# 4. Orchestrator agent – ROOT for ADK Web
# ---------------------------------------------------------------------------

root_agent = LlmAgent(
    name="meal_planner_agent",
    description=(
        "Conversational meal-planning assistant. Talks to the user, collects "
        "all fields for `meal_request`, then delegates to "
        "`meal_planner_core_agent` to generate the final plan."
    ),
    model=MODEL_NAME,
    instruction=ORCHESTRATOR_INSTRUCTIONS,
    generate_content_config=ORCH_GEN_CONFIG,  # Use generate_content_config
    # Multi-agent: the orchestrator can invoke this sub-agent when ready.
    sub_agents=[meal_planner_core_agent],
)