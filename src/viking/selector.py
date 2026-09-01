import json
from collections.abc import Iterable
from typing import Any

from openai import OpenAI

from viking.models import DaySelection, MealOption, SelectedMeal

# Intentionally kept here as a plain constant so it is easy to tune.
SYSTEM_PROMPT = """
You choose the best available Kuchnia Vikinga meal for the user. Prefer a
balanced menu with plenty of protein and fiber, reasonable calories, and lower
amounts of sugar, salt, and saturated fat. Consider ingredients, allergens,
ratings, and the existing selection. Choose exactly one offered option for
each meal. Treat a high review percentage backed by more reviews as stronger
evidence than the same percentage backed by very few reviews. Never invent
IDs. Briefly explain every choice.
""".strip()


class MealSelector:
    def __init__(self, model: str = "gpt-5.6", client: OpenAI | None = None) -> None:
        self.model = model
        self.client = client or OpenAI()

    def select(
        self,
        day: str,
        candidates: Iterable[tuple[SelectedMeal, list[MealOption]]],
    ) -> DaySelection:
        payload: list[dict[str, Any]] = []
        for current, options in candidates:
            payload.append(
                {
                    "deliveryMealId": current.delivery_meal_id,
                    "meal": current.meal_name,
                    "current": current.model_dump(mode="json", by_alias=True),
                    "options": [_option_payload(option) for option in options],
                }
            )
        response = self.client.responses.parse(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=f"Select meals for {day} from this JSON:\n{json.dumps(payload, ensure_ascii=False)}",
            text_format=DaySelection,
            store=False,
        )
        selection = response.output_parsed
        if selection is not None:
            return selection
        raise RuntimeError("OpenAI returned no structured meal selection")


def _option_payload(option: MealOption) -> dict[str, Any]:
    payload = option.model_dump(mode="json", by_alias=True)
    review = option.review_summary
    if review is None:
        payload["reviewPercentage"] = None
        payload["reviewCount"] = 0
        return payload
    payload["reviewPercentage"] = review.percentage
    payload["reviewCount"] = review.number
    return payload
