# meal_planner_agent/config.py
from __future__ import annotations

from google.genai import types as genai_types
from google.adk.agents.callback_context import CallbackContext
from google.genai.types import Content

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

# ---------------------------------------------------------------------------
# 1. Safety settings
# ---------------------------------------------------------------------------

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
# 2. Helper to build GenerateContentConfig
# ---------------------------------------------------------------------------

def build_generate_content_config(
    temperature: float,
    max_tokens: int,
    response_mime_type: str | None = None,
) -> genai_types.GenerateContentConfig:
    """
    Construct a GenerateContentConfig with generation parameters, safety settings,
    and an optional response_mime_type (e.g. 'application/json' for structured agents).
    """
    return genai_types.GenerateContentConfig(
        temperature=temperature,
        top_p=TOP_P,
        top_k=TOP_K,
        max_output_tokens=max_tokens,
        safety_settings=SAFETY_SETTINGS,
        response_mime_type=response_mime_type,
    )

# ---------------------------------------------------------------------------
# 3. Configs used by agents
# ---------------------------------------------------------------------------

# Core JSON agents (profile, core planner, shopping list, store finder)
CORE_GEN_CONFIG = build_generate_content_config(
    temperature=TEMPERATURE_CORE,
    max_tokens=MAX_OUTPUT_TOKENS_CORE,
    response_mime_type="application/json",   # FORCE pure JSON
)

# Orchestrator: chatty, natural language, strongly discourage JSON
ORCH_GEN_CONFIG = build_generate_content_config(
    temperature=TEMPERATURE_ORCH,
    max_tokens=MAX_OUTPUT_TOKENS_ORCH,
    response_mime_type="text/plain",         # bias away from JSON/structured output
)

def suppress_output_callback(callback_context: CallbackContext) -> Content:
    """Suppresses the output of the agent by returning an empty Content object."""
    return Content()