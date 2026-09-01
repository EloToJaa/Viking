from dataclasses import dataclass
from datetime import date, timedelta
from unicodedata import combining, normalize

from viking.api import VikingClient
from viking.models import Delivery, Order, SelectedMeal


@dataclass(frozen=True)
class ScheduledDelivery:
    order_id: int
    delivery: Delivery


def load_schedule(client: VikingClient) -> dict[date, list[ScheduledDelivery]]:
    schedule: dict[date, list[ScheduledDelivery]] = {}
    for order_id in client.active_order_ids():
        order = client.order(order_id)
        _add_order(schedule, order)
    return schedule


def requested_days(
    schedule: dict[date, list[ScheduledDelivery]],
    start: date | None,
    end: date | None,
    all_days: bool,
) -> list[date]:
    if all_days:
        return sorted(schedule)
    first = start or date.today()
    last = end or first
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def meal_matches(meal: SelectedMeal, expected: str) -> bool:
    return normalized_meal_name(meal.meal_name) == expected


def normalized_meal_name(value: str) -> str:
    plain = "".join(character for character in normalize("NFKD", value) if not combining(character))
    compact = " ".join(plain.casefold().split())
    aliases = {
        "sniadanie": "breakfast",
        "ii sniadanie": "second-breakfast",
        "2 sniadanie": "second-breakfast",
        "drugie sniadanie": "second-breakfast",
        "obiad": "dinner",
        "podwieczorek": "tea",
        "kolacja": "supper",
    }
    return aliases.get(compact, compact)


def _add_order(schedule: dict[date, list[ScheduledDelivery]], order: Order) -> None:
    for delivery in order.deliveries:
        if delivery.deleted:
            continue
        schedule.setdefault(delivery.date, []).append(ScheduledDelivery(order.order_id, delivery))
