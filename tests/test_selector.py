import json
from types import SimpleNamespace
from unittest.mock import Mock

from viking.models import DaySelection, MealOption, SelectedMeal
from viking.selector import MealSelector, SYSTEM_PROMPT


def test_selector_uses_structured_output_and_system_prompt() -> None:
    client = Mock()
    expected = DaySelection.model_validate(
        {"choices": [{"delivery_meal_id": 10, "diet_calories_meal_id": 20, "reason": "Balanced"}]}
    )
    client.responses.parse.return_value = SimpleNamespace(output_parsed=expected)
    current = SelectedMeal.model_validate(
        {
            "deliveryMealId": 10,
            "dietCaloriesMealId": 19,
            "mealName": "OBIAD",
            "menuMealName": "Old meal",
        }
    )
    option = MealOption.model_validate(
        {
            "menuMealDetails": {
                "menuMealId": 2,
                "menuMealName": "New meal",
                "dietCaloriesMealId": 20,
                "mealName": "OBIAD",
            },
            "reviewSummary": {"score": 4.6, "number": 27},
        }
    )

    result = MealSelector(model="test-model", client=client).select("2026-09-03", [(current, [option])])

    assert result == expected
    call = client.responses.parse.call_args.kwargs
    assert call["model"] == "test-model"
    assert call["instructions"] == SYSTEM_PROMPT
    assert call["text_format"] is DaySelection
    assert call["store"] is False
    sent_options = json.loads(call["input"].split("\n", maxsplit=1)[1])[0]["options"]
    assert sent_options[0]["reviewPercentage"] == 92
    assert sent_options[0]["reviewCount"] == 27
