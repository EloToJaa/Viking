from typing import Any

import requests
from pydantic import ValidationError

from viking.models import VikingResponse

DEFAULT_API_URL = "https://panel.kuchniavikinga.pl/api"
DEFAULT_TIMEOUT = 30.0


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
        params: dict[str, str] | None = None,
        json: Any = None,
    ) -> VikingResponse | str | None:
        url = f"{self.base_url}/{path.lstrip('/')}"

        try:
            response = self.session.request(
                method.upper(),
                url,
                headers=self._headers(),
                params=params,
                json=json,
                timeout=self.timeout,
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
            return VikingResponse.model_validate(payload)
        except ValidationError as error:
            raise VikingApiError(f"Viking API returned an invalid response: {error}") from error

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if not self.token:
            return headers

        headers["Authorization"] = f"Bearer {self.token}"
        return headers


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
