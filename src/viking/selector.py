import json
from collections.abc import Iterable
from typing import Any

from openai import OpenAI

from viking.models import DaySelection, MealOption, SelectedMeal

# Intentionally kept here as a plain constant so it is easy to tune.
SYSTEM_PROMPT = """
Wybierz posiłki dla użytkownika. Zasady:
- W tygodniu poniedziałek - piątek na drugie śniadanie wybierz zawsze shake, sok lub podobne
- Na śniadanie zawsze wybieraj najwyżej oceniony (procent) słodki posiłek np. naleśniki, jogurt, czekolada
- Na wszystkie pozostałe posiłki wybierz najlepiej ocenione posiłki (procent -> lista ocen)

Wybieraj posiłki tylko z wybranych opcji. Pamiętaj, żeby krótko opisać swoje wybory.
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
