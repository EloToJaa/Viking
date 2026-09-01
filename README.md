# Viking

A Python 3.14 CLI for inspecting Kuchnia Vikinga deliveries and using OpenAI
to choose meals. Viking API responses and OpenAI selections are validated with
Pydantic before they are used.

## Setup

Enter the uv2nix development shell:

```sh
nix develop
```

Authenticated commands read credentials from the environment. `auto-select`
also uses the standard OpenAI SDK environment variable:

```sh
export VIKING_USERNAME='you@example.com'
export VIKING_PASSWORD='your-viking-password'
export OPENAI_API_KEY='your-openai-api-key'
```

The API URL defaults to `https://panel.kuchniavikinga.pl/api`; override it with
`VIKING_API_URL`. The OpenAI model defaults to `gpt-5.6`; override it with
`OPENAI_MODEL` or `--model`.

## Commands

Run the application through Nix by placing its arguments after `--`:

```sh
# Today, one day, an inclusive range, or every available delivery day
nix run . -- show
nix run . -- show 2026-09-03
nix run . -- show 2026-09-03 --to 2026-09-07
nix run . -- show --all

# Options for a meal. Accepted meal names are breakfast, second-breakfast
# (also 2nd-breakfast), dinner, tea, and supper.
nix run . -- show-options 2026-09-03 dinner

# Select immediately, or inspect the proposed changes first
nix run . -- auto-select 2026-09-03
nix run . -- auto-select 2026-09-03 --to 2026-09-07 --dry-run
nix run . -- auto-select --all --dry-run
```

Dates without a delivery and meals that cannot be changed are reported and
skipped. AI-provided IDs are checked against the current API options before a
selection request is sent. The editable system prompt is the `SYSTEM_PROMPT`
constant in `src/viking/selector.py`.

The low-level request command remains available for API exploration:

```sh
nix run . -- request /panel/open/cities/top-10
nix run . -- request /endpoint --method POST --data '{"key":"value"}'
```

## Development

Add dependencies with `uv add <package>` and commit both `pyproject.toml` and
`uv.lock`. Run tests with:

```sh
uv run pytest
```
