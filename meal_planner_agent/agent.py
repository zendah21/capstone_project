"""
Multi-step Meal Planner agents for Google ADK.

- meal_planner_core_agent:
    Low-level agent that accepts a JSON `meal_request` and returns a JSON meal plan.

- meal_profile_agent:
    Helper agent that takes partial user info + conversation context,
    fills missing fields with smart defaults, and returns a complete `meal_request`.

- root_agent (meal_planner_agent):
    User-facing orchestrator. Talks to the user, collects key fields,
    optionally delegates missing-field handling to `meal_profile_agent`,
    and only when the request is ready delegates to `meal_planner_core_agent`.

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

# Which Gemini model to use for all agents
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

# ---------------------------------------------------------------------------
# 1.a Profile / defaults agent – fills missing fields
# ---------------------------------------------------------------------------

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
  "conversation_summary": <string>   // short natural language summary of what the user said
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
  "preferences.likes": <bool>,
  "preferences.dislikes": <bool>,
  "preferences.cuisine_preferences": <bool>,
  "preferences.avoid_red_meat": <bool>,
  "meals_per_day": <bool>
}

Your RESPONSE MUST be a SINGLE JSON object:

{
  "meal_request": { ...complete meal_request... },
  "used_defaults": { ...booleans... }
}

Constraints:
- Output MUST be valid JSON (no markdown, no backticks, no comments).
- All numeric fields must be numbers, not strings.
- Be conservative and safe in defaults; do NOT make medical claims.
"""

ORCHESTRATOR_INSTRUCTIONS = """
You are MealPlannerOrchestrator, the main user-facing agent.

Overall responsibilities:
- Chat naturally with the user.
- Make meal planning feel light and friendly, not like filling a long form.
- Collect enough information for a good `meal_request`, but avoid overwhelming the user.
- When appropriate, delegate to:
  - `meal_profile_agent` to fill missing fields with defaults.
  - `meal_planner_core_agent` to generate the final meal plan.

Fields for `meal_request`:
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

Use conversation history and avoid repetition:
- Treat previous answers in this conversation as the user's profile.
- Reuse known values instead of asking again, unless the user indicates a change.
- If the user already gave something (e.g. weight), do NOT ask for it again.

Do NOT overwhelm the user:
- Ask at most 1–2 short, focused questions at a time.
- If the user seems casual or not very detailed, prefer using smart defaults instead of asking for every field.
- Explain briefly when you are using defaults, e.g.:
  "I’ll assume a moderate activity level and about 2200 calories unless you tell me otherwise."

Default-handling strategy with sub-agents:

1) Start from what the user gives you in regular conversation (goals, broad preferences, etc.).

2) Build a partial object internally:
   {
     "age": ...maybe known or missing...,
     "gender": ...,
     "weight": ...,
     "height": ...,
     "diet_goal": ...,
     "daily_calorie_limit": ...,
     "activity_level": ...,
     "allergies": ...,
     "preferences": {
       "likes": ...,
       "dislikes": ...,
       "cuisine_preferences": ...,
       "avoid_red_meat": ...
     },
     "meals_per_day": ...
   }

3) If a few important fields are missing but the user does not seem interested in giving more details:
   - Summarize the conversation in a short natural language string.
   - Call the sub-agent `meal_profile_agent` with JSON like:

     {
       "partial_meal_request": { ...whatever you have... },
       "conversation_summary": "<short summary of goals, lifestyle, and hints>"
     }

   - `meal_profile_agent` will return:
     {
       "meal_request": { ...complete meal_request... },
       "used_defaults": { ...which fields were defaulted... }
     }

4) Then delegate MEAL GENERATION to the sub-agent `meal_planner_core_agent` by passing ONLY
   the `meal_request` object it needs.

5) If all fields are already specified clearly by the user:
   - You may skip `meal_profile_agent` and directly call `meal_planner_core_agent` with the complete `meal_request`.

After the core agent returns:
- You receive a JSON meal plan from `meal_planner_core_agent`.
- Your job is to:
  - Explain the plan in friendly, natural language:
    - Mention number of meals, overall calorie level, and how it supports the user's goal.
    - Highlight any important notes or constraints (e.g. no red meat, allergy-safe).
  - If `used_defaults` indicated that some fields are defaulted, gently mention that the plan
    can be further customized if they provide more details.

Encouraging gradual refinement:
- At the END of the explanation, ask at most one or two light questions such as:
  - "If you want to make this even healthier or more tailored, I can adjust it — for example,
     we can tweak the calories or focus more on your favorite foods. Interested?"
  - "Also, if you have any allergies or foods you absolutely avoid, tell me so I can tune this plan for you."

Rules:
- Do not invent specific values (age, weight, calories, etc.) and then claim they came from the user.
- It is OK to use clearly described defaults (e.g. "I’ll assume a moderate activity level") as long as you say so.
- Avoid medical claims. You are not a doctor.
- Maintain a supportive, non-judgmental tone at all times.
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
# 3.a Profile / defaults agent (partial → full meal_request)
# ---------------------------------------------------------------------------

meal_profile_agent = LlmAgent(
    name="meal_profile_agent",
    description=(
        "Takes a partial meal_request plus conversation summary, fills in "
        "missing fields with sensible defaults, and returns a complete "
        "`meal_request` along with flags indicating which fields used defaults."
    ),
    model=MODEL_NAME,
    instruction=MEAL_PROFILE_INSTRUCTIONS,
    generate_content_config=CORE_GEN_CONFIG,  # JSON-focused config
)

# ---------------------------------------------------------------------------
# 4. Orchestrator agent – ROOT for ADK Web
# ---------------------------------------------------------------------------

root_agent = LlmAgent(
    name="meal_planner_agent",
    description=(
        "Conversational meal-planning assistant. Talks to the user, collects "
        "key fields for `meal_request`, optionally delegates missing-field "
        "handling to `meal_profile_agent`, then delegates to "
        "`meal_planner_core_agent` to generate the final plan."
    ),
    model=MODEL_NAME,
    instruction=ORCHESTRATOR_INSTRUCTIONS,
    generate_content_config=ORCH_GEN_CONFIG,  # Use generate_content_config
    # Multi-agent: the orchestrator can invoke these sub-agents when ready.
    sub_agents=[meal_planner_core_agent, meal_profile_agent],
)
