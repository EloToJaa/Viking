from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, RootModel


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ApiModel(BaseModel):
    """Base model for the panel's camelCase API responses."""

    model_config = ConfigDict(alias_generator=_to_camel, extra="ignore", populate_by_name=True)


class VikingResponse(RootModel[JsonValue]):
    """Validated JSON returned by an unmapped API endpoint."""

    model_config = ConfigDict(strict=True)


class ActiveOrderIds(RootModel[list[int]]):
    pass


class DeliveryMeal(ApiModel):
    delivery_meal_id: int
    amount: int = 1
    diet_calories_meal_id: int
    deleted: bool = False


class Delivery(ApiModel):
    delivery_id: int
    date: date
    delivery_meals: list[DeliveryMeal] = Field(default_factory=list)
    deleted: bool = False


class Order(ApiModel):
    order_id: int
    deliveries: list[Delivery] = Field(default_factory=list)


class Nutrition(ApiModel):
    weight: float | None = None
    calories: float | None = None
    protein: float | None = None
    fat: float | None = None
    carbohydrate: float | None = None
    dietary_fiber: float | None = None
    sugar: float | None = None
    salt: float | None = None
    saturated_fatty_acids: float | None = None
    calories_text: str | None = None


class SelectedMeal(ApiModel):
    delivery_meal_id: int
    diet_calories_meal_id: int
    meal_name: str
    menu_meal_name: str
    amount: int = 1
    switchable: bool = False
    nutrition: Nutrition | None = None
    ingredients: list[Any] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)


class DeliveryMenu(ApiModel):
    delivery_menu_meal: list[SelectedMeal] = Field(default_factory=list)


class MealOptionDetails(ApiModel):
    menu_meal_id: int
    menu_meal_name: str
    diet_calories_meal_id: int
    meal_name: str
    nutrition: Nutrition | None = None
    ingredients: list[Any] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)


class ReviewSummary(ApiModel):
    score: float
    number: int

    @property
    def percentage(self) -> float:
        if self.score <= 1:
            return self.score * 100
        if self.score <= 5:
            return self.score / 5 * 100
        return self.score


class MealOption(ApiModel):
    menu_meal_details: MealOptionDetails
    can_be_changed: bool = True
    meal_recommended: bool = False
    review_summary: ReviewSummary | None = None


class SwitchOptions(ApiModel):
    meal_change_options: list[MealOption] = Field(default_factory=list)


class SelectionChoice(BaseModel):
    delivery_meal_id: int
    diet_calories_meal_id: int
    reason: str


class DaySelection(BaseModel):
    choices: list[SelectionChoice]
