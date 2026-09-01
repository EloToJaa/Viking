from unittest.mock import Mock, patch

from typer.testing import CliRunner

from viking.cli import app

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
