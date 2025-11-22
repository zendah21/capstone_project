from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.tools import load_memory
from google.adk.tools.tool_context import ToolContext
from google.genai import types as genai_types

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
# 4. Helper: Build GenerateContentConfig for each agent
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
        safety_settings=SAFETY_SETTINGS,
    )

CORE_GEN_CONFIG = build_generate_content_config(
    temperature=TEMPERATURE_CORE,
    max_tokens=MAX_OUTPUT_TOKENS_CORE,
)

ORCH_GEN_CONFIG = build_generate_content_config(
    temperature=TEMPERATURE_ORCH,
    max_tokens=MAX_OUTPUT_TOKENS_ORCH,
)
