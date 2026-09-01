# Viking

Use AI to select the best meals from Kuchnia Vikinga

## Development

Enter the reproducible development environment:

```sh
nix develop
```

Inspect the CLI with either toolchain:

```sh
uv run viking --help
nix run -- --help
```

Send a request to a public Viking API endpoint:

```sh
uv run viking request /panel/open/cities/top-10
```

The API defaults to `https://panel.kuchniavikinga.pl/api`. Override it with
`VIKING_API_URL` or `--base-url`. Use `--method` and `--data` for requests with
a JSON body:

```sh
uv run viking request /endpoint --method POST --data '{"key":"value"}'
```

The panel's authenticated endpoints use its login session. Login and persistent
session handling have been mapped but are not implemented in the CLI yet.

JSON responses are validated with Pydantic before they are printed. Add
endpoint-specific models in `src/viking/models.py` as the API contract becomes
available.

Add dependencies with `uv add <package>` and commit the updated
`pyproject.toml` and `uv.lock` files.

Run the test suite with:

```sh
uv run pytest
```
