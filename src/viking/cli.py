import json
import os
from datetime import date
from enum import StrEnum
from typing import Annotated, Any

import typer
from openai import OpenAIError
from pydantic import BaseModel

from viking.api import DEFAULT_API_URL, DEFAULT_TIMEOUT, VikingApiError, VikingClient
from viking.domain import load_schedule, meal_matches, requested_days
from viking.models import MealOption, Nutrition, ReviewSummary, SelectedMeal
from viking.selector import DEFAULT_OPENAI_MODEL, MealSelector

app = typer.Typer(help="Inspect and select Kuchnia Vikinga meals.", no_args_is_help=True)


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


@app.callback()
def main() -> None:
    """Configure and run Viking API commands."""


@app.command("show")
def show(
    day: Annotated[str | None, typer.Argument(help="Start date (YYYY-MM-DD); defaults to today.")] = None,
    to: Annotated[str | None, typer.Option("--to", help="Inclusive end date (YYYY-MM-DD).")] = None,
    all_days: Annotated[bool, typer.Option("--all", help="Show every available delivery day.")] = False,
) -> None:
    """Show currently selected meals for a day or date range."""
    start, end = _date_selection(day, to, all_days)
    client = _authenticated_client()
    try:
        schedule = load_schedule(client)
        for selected_day in requested_days(schedule, start, end, all_days):
            deliveries = schedule.get(selected_day, [])
            if not deliveries:
                typer.secho(f"\n{selected_day}: unavailable", fg="yellow", bold=True)
                continue
            meals: list[SelectedMeal] = []
            for scheduled in deliveries:
                menu = client.delivery_menu(scheduled.delivery.delivery_id)
                meals.extend(menu.delivery_menu_meal)
            _print_day(selected_day, meals)
    except VikingApiError as error:
        _fail(str(error))


@app.command("show-options")
def show_options(
    day: Annotated[str, typer.Argument(help="Delivery date (YYYY-MM-DD).")],
    meal: Annotated[str, typer.Argument(help="breakfast, second-breakfast, 2nd-breakfast, dinner, tea, or supper")],
) -> None:
    """Show all switch options for one meal on a delivery day."""
    selected_day = _parse_date(day)
    expected_meal = _parse_meal(meal)
    client = _authenticated_client()
    try:
        schedule = load_schedule(client)
        deliveries = schedule.get(selected_day, [])
        if not deliveries:
            typer.echo(f"{selected_day}: unavailable")
            return
        found = False
        for scheduled in deliveries:
            menu = client.delivery_menu(scheduled.delivery.delivery_id)
            for current in menu.delivery_menu_meal:
                if not meal_matches(current, expected_meal):
                    continue
                found = True
                _print_options(client, scheduled.order_id, scheduled.delivery.delivery_id, current)
        if not found:
            typer.echo(f"{selected_day}: {expected_meal} is not present")
    except VikingApiError as error:
        _fail(str(error))


@app.command("auto-select")
def auto_select(
    day: Annotated[str | None, typer.Argument(help="Start date (YYYY-MM-DD); defaults to today.")] = None,
    to: Annotated[str | None, typer.Option("--to", help="Inclusive end date (YYYY-MM-DD).")] = None,
    all_days: Annotated[bool, typer.Option("--all", help="Process every available delivery day.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Choose and print without changing meals.")] = False,
    model: Annotated[
        str, typer.Option("--model", envvar="OPENAI_MODEL", help="OpenAI model.")
    ] = DEFAULT_OPENAI_MODEL,
) -> None:
    """Ask OpenAI to choose the best offered meals and apply the choices."""
    start, end = _date_selection(day, to, all_days)
    client = _authenticated_client()
    try:
        selector = MealSelector(model=model)
        schedule = load_schedule(client)
        for selected_day in requested_days(schedule, start, end, all_days):
            deliveries = schedule.get(selected_day, [])
            if not deliveries:
                typer.echo(f"{selected_day}: unavailable")
                continue
            for scheduled in deliveries:
                _auto_select_delivery(
                    client, selector, scheduled.order_id, scheduled.delivery.delivery_id,
                    selected_day, dry_run,
                )
    except (VikingApiError, OpenAIError, RuntimeError) as error:
        _fail(str(error))


def _auto_select_delivery(
    client: VikingClient,
    selector: MealSelector,
    order_id: int,
    delivery_id: int,
    selected_day: date,
    dry_run: bool,
) -> None:
    menu = client.delivery_menu(delivery_id)
    candidates: list[tuple[SelectedMeal, list[MealOption]]] = []
    for meal in menu.delivery_menu_meal:
        if not meal.switchable:
            typer.echo(f"{selected_day}: {meal.meal_name} cannot be changed")
            continue
        try:
            switch_options = client.switch_options(order_id, delivery_id, meal.delivery_meal_id)
        except VikingApiError as error:
            typer.echo(f"{selected_day}: {meal.meal_name} cannot be chosen: {error}")
            continue
        options = [option for option in switch_options.meal_change_options if option.can_be_changed]
        if not options:
            typer.echo(f"{selected_day}: {meal.meal_name} has no available options")
            continue
        candidates.append((meal, options))
    if not candidates:
        typer.echo(f"{selected_day}: no meals can be selected")
        return

    selection = selector.select(selected_day.isoformat(), candidates)
    offered = {
        current.delivery_meal_id: {
            option.menu_meal_details.diet_calories_meal_id: option for option in options
        }
        for current, options in candidates
    }
    selected_meals: set[int] = set()
    for choice in selection.choices:
        options = offered.get(choice.delivery_meal_id)
        if options is None or choice.diet_calories_meal_id not in options:
            typer.echo(f"{selected_day}: OpenAI returned an invalid choice for meal {choice.delivery_meal_id}")
            continue
        if choice.delivery_meal_id in selected_meals:
            typer.echo(f"{selected_day}: OpenAI returned a duplicate choice for meal {choice.delivery_meal_id}")
            continue
        selected_meals.add(choice.delivery_meal_id)
        option = options[choice.diet_calories_meal_id]
        action = "would select" if dry_run else "selected"
        if not dry_run:
            try:
                client.select_meal(
                    order_id, delivery_id, choice.delivery_meal_id, choice.diet_calories_meal_id
                )
            except VikingApiError as error:
                typer.echo(f"{selected_day}: could not select {option.menu_meal_details.menu_meal_name}: {error}")
                continue
        typer.echo(f"{selected_day}: {action} {option.menu_meal_details.menu_meal_name} — {choice.reason}")
    for current, _options in candidates:
        if current.delivery_meal_id in selected_meals:
            continue
        typer.echo(f"{selected_day}: OpenAI did not choose {current.meal_name}")


def _print_options(
    client: VikingClient, order_id: int, delivery_id: int, meal: SelectedMeal
) -> None:
    typer.secho(f"\n{meal.meal_name} OPTIONS", fg="cyan", bold=True)
    typer.secho("─" * 56, fg="bright_black")
    typer.secho("Currently selected", fg="magenta", bold=True)
    typer.secho(f"  {meal.menu_meal_name}", fg="green")
    if not meal.switchable:
        typer.secho("\nThis meal cannot be changed.", fg="yellow", bold=True)
        return
    options = client.switch_options(order_id, delivery_id, meal.delivery_meal_id).meal_change_options
    if not options:
        typer.secho("\nNo available options.", fg="yellow", bold=True)
        return
    typer.secho("\nAvailable options", fg="magenta", bold=True)
    for index, option in enumerate(options, start=1):
        details = option.menu_meal_details
        typer.secho(f"\n{index}. {details.menu_meal_name}", fg="yellow", bold=True)
        typer.secho(
            f"   Selection ID: {details.diet_calories_meal_id}", fg="bright_black"
        )
        if option.meal_recommended:
            typer.secho("   ★ Recommended", fg="green", bold=True)
        summary = _nutrition_summary(details.nutrition)
        if summary:
            typer.secho(f"   {summary}", fg="bright_black")
        typer.secho(f"   {_review_summary(option.review_summary)}", fg="bright_black")


def _authenticated_client() -> VikingClient:
    username = os.getenv("VIKING_USERNAME")
    password = os.getenv("VIKING_PASSWORD")
    if not username or not password:
        _fail("Set VIKING_USERNAME and VIKING_PASSWORD to use authenticated commands.")
    client = VikingClient(base_url=os.getenv("VIKING_API_URL", DEFAULT_API_URL))
    try:
        client.login(username, password)
    except VikingApiError as error:
        _fail(str(error))
    return client


def _date_selection(
    day: str | None, end: str | None, all_days: bool
) -> tuple[date | None, date | None]:
    if all_days and (day or end):
        raise typer.BadParameter("--all cannot be combined with a date or --to")
    if end and not day:
        raise typer.BadParameter("--to requires a start date")
    start_date = _parse_date(day) if day else None
    end_date = _parse_date(end) if end else None
    if start_date and end_date and end_date < start_date:
        raise typer.BadParameter("--to must not be before the start date")
    return start_date, end_date


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise typer.BadParameter(f"Date must use YYYY-MM-DD: {value}") from error


def _parse_meal(value: str) -> str:
    normalized = {"2nd-breakfast": "second-breakfast"}.get(value.casefold(), value.casefold())
    if normalized in {"breakfast", "second-breakfast", "dinner", "tea", "supper"}:
        return normalized
    raise typer.BadParameter(f"Unknown meal: {value}")


def _nutrition_summary(nutrition: Nutrition | None) -> str:
    if nutrition is None:
        return ""
    values: list[str] = []
    for label, value in (
        ("kcal", nutrition.calories), ("g protein", nutrition.protein),
        ("g fat", nutrition.fat), ("g carbs", nutrition.carbohydrate),
    ):
        if value is not None:
            values.append(f"{value:g} {label}")
    return " · ".join(values)


def _review_summary(review: ReviewSummary | None) -> str:
    if review is None or review.number == 0:
        return "No reviews"
    noun = "review" if review.number == 1 else "reviews"
    return f"Reviews: {review.percentage:.0f}% · {review.number} {noun}"


def _print_day(selected_day: date, meals: list[SelectedMeal]) -> None:
    typer.secho(f"\n{selected_day:%A, %d %B %Y}", fg="cyan", bold=True)
    typer.secho("─" * 56, fg="bright_black")
    if not meals:
        typer.secho("  No selected meals", fg="yellow")
        return
    for meal in meals:
        amount = f" ×{meal.amount}" if meal.amount != 1 else ""
        typer.secho(f"{meal.meal_name}{amount}", fg="yellow", bold=True)
        typer.secho(f"  {meal.menu_meal_name}", fg="green")
        summary = _nutrition_summary(meal.nutrition)
        if summary:
            typer.secho(f"  {summary}", fg="bright_black")
    typer.secho("Daily total", fg="magenta", bold=True)
    summary = _nutrition_summary(_daily_nutrition(meals))
    typer.secho(f"  {summary or 'nutrition unavailable'}", bold=True)


def _daily_nutrition(meals: list[SelectedMeal]) -> Nutrition:
    totals: dict[str, float | None] = {}
    for field in ("calories", "protein", "fat", "carbohydrate"):
        values = [
            getattr(meal.nutrition, field) if meal.nutrition is not None else None
            for meal in meals
        ]
        if any(value is None for value in values):
            totals[field] = None
            continue
        totals[field] = sum(value * meal.amount for value, meal in zip(values, meals, strict=True))
    return Nutrition.model_validate(totals)


@app.command("request")
def send_request(
    path: Annotated[str, typer.Argument(help="API path, for example /menu.")],
    method: Annotated[HttpMethod, typer.Option("--method", "-X", case_sensitive=False)] = HttpMethod.GET,
    base_url: Annotated[str, typer.Option("--base-url", envvar="VIKING_API_URL")] = DEFAULT_API_URL,
    token: Annotated[str | None, typer.Option("--token", envvar="VIKING_API_TOKEN")] = None,
    query: Annotated[list[str] | None, typer.Option("--query", "-q", help="KEY=VALUE; repeatable.")] = None,
    data: Annotated[str | None, typer.Option("--data", "-d", help="JSON request body.")] = None,
    timeout: Annotated[float, typer.Option("--timeout", min=0.1)] = DEFAULT_TIMEOUT,
) -> None:
    """Send an arbitrary HTTP request and print its response."""
    client = VikingClient(base_url=base_url, token=token, timeout=timeout)
    try:
        response = client.request(
            method.value, path, params=_parse_query(query or []), json=_parse_json(data)
        )
    except VikingApiError as error:
        _fail(str(error))
    _print_response(response)


def _parse_query(values: list[str]) -> dict[str, str] | None:
    if not values:
        return None
    parameters: dict[str, str] = {}
    for value in values:
        key, separator, item = value.partition("=")
        if separator and key:
            parameters[key] = item
            continue
        raise typer.BadParameter(f"Query parameter must be KEY=VALUE: {value}")
    return parameters


def _parse_json(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise typer.BadParameter(f"Request body is not valid JSON: {error.msg}") from error


def _print_response(response: Any) -> None:
    if response is None:
        return
    if isinstance(response, str):
        typer.echo(response)
        return
    if isinstance(response, BaseModel):
        response = response.model_dump()
    typer.echo(json.dumps(response, indent=2, ensure_ascii=False))


def _fail(message: str) -> Any:
    typer.echo(message, err=True)
    raise typer.Exit(code=1)
