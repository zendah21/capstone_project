from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions


class MealPlanValidationChecker(BaseAgent):
    """Checks if the meal plan generated is valid."""

    async def _run_async_impl(
        self, context: InvocationContext
    ) -> AsyncGenerator[Event, None]:

        meal_plan = context.session.state.get("meal_plan")

        # If meal plan exists → escalate to next agent (e.g., ShoppingListAgent)
        if meal_plan:
            yield Event(
                author=self.name,
                actions=EventActions(escalate=True),
            )

        # If meal plan doesn't exist → stop here (or allow regeneration)
        else:
            yield Event(author=self.name)


class ShoppingListValidationChecker(BaseAgent):
    """Checks if the shopping list is valid."""

    async def _run_async_impl(
        self, context: InvocationContext
    ) -> AsyncGenerator[Event, None]:

        shopping_list = context.session.state.get("shopping_list")

        # If shopping list exists → escalate to next agent (e.g., StoreFinderAgent)
        if shopping_list:
            yield Event(
                author=self.name,
                actions=EventActions(escalate=True),
            )

        # If not → do not escalate
        else:
            yield Event(author=self.name)
