from datetime import date
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from viking.cli import _auto_select_delivery, app
from viking.models import DaySelection, DeliveryMenu, MealOption, SelectedMeal

runner = CliRunner()


@patch("viking.cli.VikingClient")
def test_request_command_parses_input_and_prints_json(client_type: Mock) -> None:
    client = client_type.return_value
    client.request.return_value = {"meals": ["breakfast"]}

    result = runner.invoke(
        app,
        [
            "request",
            "/menu",
            "--query",
            "date=2026-09-02",
            "--data",
            '{"diet":"basic"}',
        ],
    )

    assert result.exit_code == 0
    assert '"breakfast"' in result.stdout
    client.request.assert_called_once_with(
        "GET",
        "/menu",
        params={"date": "2026-09-02"},
        json={"diet": "basic"},
    )


def test_request_command_rejects_invalid_query() -> None:
    result = runner.invoke(app, ["request", "/menu", "--query", "invalid"])

    assert result.exit_code == 2
    assert "Query parameter must be KEY=VALUE" in result.output


def test_auto_select_rejects_unoffered_ai_id() -> None:
    client = Mock()
    current = SelectedMeal.model_validate(
        {
            "deliveryMealId": 10,
            "dietCaloriesMealId": 19,
            "mealName": "OBIAD",
            "menuMealName": "Current",
            "switchable": True,
        }
    )
    option = MealOption.model_validate(
        {
            "menuMealDetails": {
                "menuMealId": 2,
                "menuMealName": "Offered",
                "dietCaloriesMealId": 20,
                "mealName": "OBIAD",
            }
        }
    )
    client.delivery_menu.return_value = DeliveryMenu(delivery_menu_meal=[current])
    client.switch_options.return_value.meal_change_options = [option]
    selector = Mock()
    selector.select.return_value = DaySelection.model_validate(
        {"choices": [{"delivery_meal_id": 10, "diet_calories_meal_id": 999, "reason": "No"}]}
    )

    _auto_select_delivery(client, selector, 34, 46, date(2026, 9, 3), False)

    client.select_meal.assert_not_called()
