from datetime import date
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from viking.cli import _auto_select_delivery, _review_summary, app
from viking.domain import ScheduledDelivery
from viking.models import (
    DaySelection,
    Delivery,
    DeliveryMenu,
    MealOption,
    ReviewSummary,
    SelectedMeal,
)

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


def test_review_summary_converts_five_point_score_to_percentage() -> None:
    review = ReviewSummary(score=4.6, number=27)

    assert _review_summary(review) == "Reviews: 92% · 27 reviews"
    assert _review_summary(None) == "No reviews"


@patch("viking.cli.load_schedule")
@patch("viking.cli._authenticated_client")
def test_show_formats_meals_and_daily_nutrition_total(
    authenticated_client: Mock, load_schedule: Mock
) -> None:
    client = authenticated_client.return_value
    delivery = Delivery.model_validate({"deliveryId": 46, "date": "2026-09-03"})
    load_schedule.return_value = {
        date(2026, 9, 3): [ScheduledDelivery(order_id=34, delivery=delivery)]
    }
    client.delivery_menu.return_value = DeliveryMenu.model_validate(
        {
            "deliveryMenuMeal": [
                {
                    "deliveryMealId": 10,
                    "dietCaloriesMealId": 20,
                    "mealName": "OBIAD",
                    "menuMealName": "Kurczak z ryżem",
                    "amount": 2,
                    "nutrition": {
                        "calories": 450,
                        "protein": 30,
                        "fat": 10,
                        "carbohydrate": 55,
                    },
                }
            ]
        }
    )

    result = runner.invoke(app, ["show", "2026-09-03"], color=True)

    assert result.exit_code == 0
    assert "Thursday, 03 September 2026" in result.stdout
    assert "Kurczak z ryżem" in result.stdout
    assert "Daily total" in result.stdout
    assert "900 kcal · 60 g protein · 20 g fat · 110 g carbs" in result.stdout
    assert "\x1b[" in result.stdout


@patch("viking.cli.load_schedule")
@patch("viking.cli._authenticated_client")
def test_show_options_prints_review_percentage_and_count(
    authenticated_client: Mock, load_schedule: Mock
) -> None:
    client = authenticated_client.return_value
    delivery = Delivery.model_validate({"deliveryId": 46, "date": "2026-09-03"})
    load_schedule.return_value = {
        date(2026, 9, 3): [ScheduledDelivery(order_id=34, delivery=delivery)]
    }
    current = SelectedMeal.model_validate(
        {
            "deliveryMealId": 10,
            "dietCaloriesMealId": 19,
            "mealName": "OBIAD",
            "menuMealName": "Current",
            "switchable": True,
        }
    )
    client.delivery_menu.return_value = DeliveryMenu(delivery_menu_meal=[current])
    client.switch_options.return_value.meal_change_options = [
        MealOption.model_validate(
            {
                "menuMealDetails": {
                    "menuMealId": 2,
                    "menuMealName": "Offered",
                    "dietCaloriesMealId": 20,
                    "mealName": "OBIAD",
                },
                "reviewSummary": {"score": 4.6, "number": 27},
            }
        )
    ]

    result = runner.invoke(app, ["show-options", "2026-09-03", "dinner"])

    assert result.exit_code == 0
    assert "Reviews: 92% · 27 reviews" in result.stdout


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
