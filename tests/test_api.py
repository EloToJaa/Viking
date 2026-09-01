from unittest.mock import Mock

import pytest
import requests

from viking.api import VikingApiError, VikingClient
from viking.models import VikingResponse


def test_request_sends_auth_and_returns_json() -> None:
    session = Mock(spec=requests.Session)
    response = Mock(spec=requests.Response)
    response.content = b'{"meals": []}'
    response.json.return_value = {"meals": []}
    session.request.return_value = response
    client = VikingClient(
        base_url="https://example.test/api/",
        token="secret",
        timeout=5,
        session=session,
    )

    result = client.request("get", "/menu", params={"date": "2026-09-02"})

    assert result == VikingResponse({"meals": []})
    session.request.assert_called_once_with(
        "GET",
        "https://example.test/api/menu",
        headers={
            "Accept": "application/json",
            "company-id": "kuchniavikinga",
            "x-launcher-type": "BROWSER_PANEL",
            "Authorization": "Bearer secret",
        },
        params={"date": "2026-09-02"},
        json=None,
        data=None,
        timeout=5,
    )


def test_login_uses_form_data_and_keeps_session_cookies() -> None:
    session = Mock(spec=requests.Session)
    response = Mock(spec=requests.Response)
    response.content = b""
    session.request.return_value = response

    VikingClient(session=session).login("user@example.com", "secret")

    session.request.assert_called_once_with(
        "POST",
        "https://panel.kuchniavikinga.pl/api/auth/login",
        headers={
            "Accept": "application/json",
            "company-id": "kuchniavikinga",
            "x-launcher-type": "BROWSER_PANEL",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        params=None,
        json=None,
        data={"username": "user@example.com", "password": "secret"},
        timeout=30.0,
    )


def test_request_turns_http_error_into_domain_error() -> None:
    session = Mock(spec=requests.Session)
    response = Mock(spec=requests.Response)
    response.status_code = 401
    response.text = '{"detail": "invalid token"}'
    response.json.return_value = {"detail": "invalid token"}
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    session.request.return_value = response
    client = VikingClient(session=session)

    with pytest.raises(VikingApiError, match="HTTP 401: invalid token"):
        client.request("GET", "/menu")


def test_request_rejects_non_json_compatible_response() -> None:
    session = Mock(spec=requests.Session)
    response = Mock(spec=requests.Response)
    response.content = b"invalid"
    response.json.return_value = {"value": object()}
    session.request.return_value = response
    client = VikingClient(session=session)

    with pytest.raises(VikingApiError, match="invalid response"):
        client.request("GET", "/menu")
