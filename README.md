# dpp-sdk (Python)

Python SDK for **Digital Product Passports (DPP)**, built on [Pydantic v2](https://docs.pydantic.dev).

It provides typed models, validation, and JSON transport for digital product passports,
plus HTTP clients for the two DPP backend APIs:

- the **DPP registry** — hosted by the European Commission, and
- the **DPP repository** — hosted by economic operators or service providers.

Both APIs conform to the draft standardisation documents published by **CEN/CENELEC**.

## Install

```bash
pip install dpp-sdk
```

Requires Python 3.11+.

## Quickstart

```python
from dpp_sdk import Dpp4Fun, from_json, to_json, validate_dpp4fun

# Parse an incoming passport (accepts both flat and nested JSON shapes)
dpp = from_json(raw_json)

# Validate against the DPP rule set (raises on violations)
validate_dpp4fun(dpp)

# Serialize back to the flattened wire JSON
payload = to_json(dpp)
```

The `httpx`-based clients for the registry and repository APIs live in `dpp_sdk.clients`:

```python
from dpp_sdk.clients import DppRepoClient, DppRegistryClient
```

## Packages

| Package | Purpose |
|---|---|
| `dpp_sdk.core` | Core DPP model, validation, and JSON transport |
| `dpp_sdk.dpp4fun` | Furniture-specific DPP aggregate |
| `dpp_sdk.clients` | HTTP clients for the DPP registry & repository APIs |

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest        # tests
mypy          # type check (strict)
ruff check .  # lint
```
