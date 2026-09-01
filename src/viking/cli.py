import json
from enum import StrEnum
from typing import Annotated, Any

import typer
from pydantic import BaseModel

from viking.api import DEFAULT_API_URL, DEFAULT_TIMEOUT, VikingApiError, VikingClient

app = typer.Typer(
    help="Send requests to the Kuchnia Vikinga API.",
    no_args_is_help=True,
)


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


@app.callback()
def main() -> None:
    """Configure and run Viking API commands."""


@app.command("request")
def send_request(
    path: Annotated[str, typer.Argument(help="API path, for example /menu.")],
    method: Annotated[
        HttpMethod,
        typer.Option("--method", "-X", case_sensitive=False, help="HTTP method."),
    ] = HttpMethod.GET,
    base_url: Annotated[
        str,
        typer.Option(
            "--base-url",
            envvar="VIKING_API_URL",
            help="Viking API base URL.",
        ),
    ] = DEFAULT_API_URL,
    token: Annotated[
        str | None,
        typer.Option(
            "--token",
            envvar="VIKING_API_TOKEN",
            help="Bearer token. Prefer the environment variable to shell history.",
        ),
    ] = None,
    query: Annotated[
        list[str] | None,
        typer.Option("--query", "-q", help="Query parameter as KEY=VALUE. Repeatable."),
    ] = None,
    data: Annotated[
        str | None,
        typer.Option("--data", "-d", help="JSON request body."),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=0.1, help="Request timeout in seconds."),
    ] = DEFAULT_TIMEOUT,
) -> None:
    """Send an HTTP request and print its response."""
    client = VikingClient(base_url=base_url, token=token, timeout=timeout)

    try:
        response = client.request(
            method.value,
            path,
            params=_parse_query(query or []),
            json=_parse_json(data),
        )
    except VikingApiError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error

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
