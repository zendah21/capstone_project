from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent,LoopAgent

from meal_planner_agent.config import CORE_GEN_CONFIG, MODEL_NAME,suppress_output_callback
from meal_planner_agent.run_smoke_tests import ShoppingListValidationChecker


# ========= ADK structured output schema =========

class ShoppingListOutput(BaseModel):
    """
    Output of meal_ingredients_agent.

    shopping_list_text:
      A plain-text / Markdown shopping list grouped by categories and bullet points.
    """
    shopping_list_text: str = Field(
        description=(
            "A human-friendly shopping list in plain text or Markdown, grouped "
            "by categories (e.g. 'Produce', 'Meat & Poultry', 'Dairy', 'Pantry & Grains'), "
            "with one item per line."
        )
    )


# ========= Instructions (aligned with ShoppingListOutput) =========

SHOPPING_AGENT_INSTRUCTIONS = """
You are MealIngredientsAgent (the Shopping Agent) in a multi-agent system.

Goal: turn a one-day meal_plan_json into a concise, usable grocery list.

Steps:
- Extract all ingredients from meals[].items.
- Consolidate duplicates; simplify units to grocery-friendly sizes (bags, bunches, cartons, kg, L). Skip generic staples unless specific.
- Group into logical store categories (e.g., Produce; Meat & Poultry; Dairy & Refrigerated; Pantry & Grains).

Output (strict):
{
  "shopping_list_text": "<plain text or Markdown list grouped by category>"
}
- No extra keys, no markdown fences, no commentary. Top-level must be valid JSON matching the schema.
"""


# ========= ADK agent definition =========

meal_ingredients_agent = LlmAgent(
    name="meal_ingredients_agent",
    description=(
        "Shopping List assistant. Takes the complete one-day meal plan JSON, "
        "extracts all ingredients, consolidates them, and returns a categorized "
        "shopping list as plain text/Markdown in `shopping_list_text`."
    ),
    model=MODEL_NAME,
    instruction=SHOPPING_AGENT_INSTRUCTIONS,
    generate_content_config=CORE_GEN_CONFIG,
    # ADK structured output:
    output_schema=ShoppingListOutput,      # enforce JSON with shopping_list_text field
    output_key="shopping_list_result",     # stored in state['shopping_list_result']
)


robust_list_creator = LoopAgent(
    name="robust_list_creator",
    description="A robust list creator that retries if it fails.",
    sub_agents=[
       meal_ingredients_agent,
        ShoppingListValidationChecker(name="list_validation_checker"),
    ],
    max_iterations=3,
    after_agent_callback=suppress_output_callback,
)