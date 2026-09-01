from datetime import date

from viking.domain import load_schedule, meal_matches, requested_days
from viking.models import Order, SelectedMeal


class FakeClient:
    def active_order_ids(self) -> list[int]:
        return [34]

    def order(self, order_id: int) -> Order:
        assert order_id == 34
        return Order.model_validate(
            {
                "orderId": 34,
                "deliveries": [
                    {"deliveryId": 46, "date": "2026-09-03"},
                    {"deliveryId": 47, "date": "2026-09-04", "deleted": True},
                ],
            }
        )


def test_schedule_and_requested_range_include_unavailable_days() -> None:
    schedule = load_schedule(FakeClient())  # type: ignore[arg-type]

    assert list(schedule) == [date(2026, 9, 3)]
    assert requested_days(schedule, date(2026, 9, 2), date(2026, 9, 4), False) == [
        date(2026, 9, 2),
        date(2026, 9, 3),
        date(2026, 9, 4),
    ]


def test_polish_meal_names_map_to_cli_names() -> None:
    meal = SelectedMeal.model_validate(
        {
            "deliveryMealId": 1,
            "dietCaloriesMealId": 2,
            "mealName": "II ŚNIADANIE",
            "menuMealName": "Owsianka",
        }
    )

    assert meal_matches(meal, "second-breakfast")
