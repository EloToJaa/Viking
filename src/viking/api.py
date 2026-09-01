from typing import Any, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from viking.models import ActiveOrderIds, DeliveryMenu, Order, SwitchOptions, VikingResponse

DEFAULT_API_URL = "https://panel.kuchniavikinga.pl/api"
DEFAULT_TIMEOUT = 30.0
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class VikingApiError(RuntimeError):
    """Raised when a request to the Viking API fails."""


class VikingClient:
    def __init__(
        self,
        base_url: str = DEFAULT_API_URL,
        token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.session = session or requests.Session()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        json: Any = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        response_model: type[ResponseModel] = VikingResponse,
    ) -> ResponseModel | str | None:
        url = f"{self.base_url}/{path.lstrip('/')}"
        request_headers = self._headers()
        request_headers.update(headers or {})

        try:
            response = self.session.request(
                method.upper(), url, headers=request_headers, params=params, json=json,
                data=data, timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as error:
            response = error.response
            status = response.status_code if response is not None else "unknown"
            detail = _response_error_detail(response)
            raise VikingApiError(f"Viking API returned HTTP {status}: {detail}") from error
        except requests.RequestException as error:
            raise VikingApiError(f"Could not reach the Viking API: {error}") from error

        if not response.content:
            return None

        try:
            payload = response.json()
        except requests.JSONDecodeError:
            return response.text

        try:
            return response_model.model_validate(payload)
        except ValidationError as error:
            raise VikingApiError(f"Viking API returned an invalid response: {error}") from error

    def login(self, username: str, password: str) -> None:
        self.request(
            "POST", "/auth/login", data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def active_order_ids(self) -> list[int]:
        response = self.request("GET", "/company/customer/order/active-ids", response_model=ActiveOrderIds)
        return _require_model(response, ActiveOrderIds).root

    def order(self, order_id: int) -> Order:
        response = self.request("GET", f"/company/customer/order/{order_id}", response_model=Order)
        return _require_model(response, Order)

    def delivery_menu(self, delivery_id: int) -> DeliveryMenu:
        response = self.request(
            "GET", f"/company/general/menus/delivery/{delivery_id}/new", response_model=DeliveryMenu
        )
        return _require_model(response, DeliveryMenu)

    def switch_options(self, order_id: int, delivery_id: int, delivery_meal_id: int) -> SwitchOptions:
        response = self.request("GET", _switch_path(order_id, delivery_id, delivery_meal_id), response_model=SwitchOptions)
        return _require_model(response, SwitchOptions)

    def select_meal(
        self, order_id: int, delivery_id: int, delivery_meal_id: int,
        diet_calories_meal_id: int, amount: int = 1,
    ) -> None:
        self.request(
            "PUT", _switch_path(order_id, delivery_id, delivery_meal_id),
            params={"amount": amount, "dietCaloriesMealId": diet_calories_meal_id},
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "company-id": "kuchniavikinga",
            "x-launcher-type": "BROWSER_PANEL",
        }
        if not self.token:
            return headers
        headers["Authorization"] = f"Bearer {self.token}"
        return headers


def _require_model(value: BaseModel | str | None, expected: type[ResponseModel]) -> ResponseModel:
    if isinstance(value, expected):
        return value
    raise VikingApiError(f"Viking API returned an empty or non-JSON response for {expected.__name__}")


def _switch_path(order_id: int, delivery_id: int, delivery_meal_id: int) -> str:
    return f"/company/customer/order/{order_id}/deliveries/{delivery_id}/delivery-meals/{delivery_meal_id}/switch"


def _response_error_detail(response: requests.Response | None) -> str:
    if response is None:
        return "no response"
    try:
        payload = response.json()
    except requests.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message") or payload.get("error")
        if detail:
            return str(detail)
    text = response.text.strip()
    if text:
        return text[:500]
    return response.reason or "request failed"
