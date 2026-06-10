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

### Parse, validate, serialize

```python
from dpp_sdk import from_json, to_json, validate_dpp4fun

# Parse an incoming passport (accepts both flat and nested JSON shapes)
dpp = from_json(raw_json)

# Validate against the DPP rule set (raises on violations)
validate_dpp4fun(dpp)

# Serialize back to the flattened wire JSON
payload = to_json(dpp)
```

### Full lifecycle

This builds a passport from typed models, validates it, stores it in the repository,
registers it with the registry, then reads, updates, and deletes it. It runs as-is against
the local mock services — see [Testing against the mock services](#testing-against-the-mock-services)
to start them first.

```python
from datetime import date
from uuid import uuid4

from dpp_sdk import (
    Address, BillOfMaterials, Characteristics, Contact, Dimensions,
    Documentation, Dpp4Fun, Dpp4FunJsonCodec, DppCore, DppValidationError,
    Email, Material, Nameplate, Organization, OrganizationRole,
    PassportMetadata, ProductClassification, validate_dpp4fun,
)
from dpp_sdk.clients import (
    DppRegistryClient, DppRepoClient, RegisterDppRequest, local_repo_base_url,
)

# 1. Build a passport from typed, validated models.
manufacturer = Organization(
    name="ACME Furniture GmbH",
    gln="4012345000009",
    role=OrganizationRole.MANUFACTURER,
    contact=Contact(
        organization="ACME HQ",
        address=Address(country="DE", town="Berlin", street="Hauptstr. 1", zipCode="10115"),
        email=Email(emailAddress="info@acme.example", typeOfEmail="business"),
    ),
)

dpp = Dpp4Fun(
    coreDpp=DppCore(
        passportMetadata=PassportMetadata(
            uniqueProductIdentifier=uuid4(),            # drives dpp.dpp_id
            passportUpdateDates=[date.today()],
            qrCodeOrDigitalTag="QR-001",
        ),
        nameplate=Nameplate(
            gtinCode="GTIN-0001",                       # drives dpp.product_id
            internalArticleNumber="ART-1",
            manufacturer=manufacturer,
        ),
        documentation=Documentation(
            digitalInstructionsLink="https://acme.example/docs",
            downloadable=True,
            availableForYears=10,
        ),
    ),
    classification=ProductClassification(
        sector="Furniture", category="Office Chair", group="Seating",
        tags=["ergonomic", "adjustable"],
    ),
    characteristics=Characteristics(
        productName="ErgoChair Pro", productType="Office Chair", brand="ACME",
        dimensions=Dimensions(width=60.0, height=120.0, depth=60.0, unit="cm"),
        weight=14.5, features=["lumbar-support"],
    ),
    billOfMaterials=BillOfMaterials(
        materials=[
            Material(name="steel", mandatory=True, portion=0.6, reference="MAT-STEEL"),
            Material(name="foam", portion=0.4),
        ],
    ),
)

# 2. Validate against the full DPP rule set (collects all violations, then raises).
try:
    validate_dpp4fun(dpp)
except DppValidationError as exc:
    raise SystemExit(f"passport is invalid: {exc}")

# 3. Connect the clients. (Swap for_local_mock() for the explicit-URL constructors in prod.)
repo = DppRepoClient.for_local_mock(Dpp4FunJsonCodec(), validate_dpp4fun)
registry = DppRegistryClient.for_local_mock()
assert repo.health_check() and registry.health_check(), "start the mock services first"

# 4. Store the passport in the repository (POST /dpps -> dppId).
created = repo.create_dpp(dpp)
print("stored:", created.dppId)

# 5. Register it with the registry. The registry verifies the repo reference,
#    so the passport must already exist in the repo.
registered = registry.post_new_dpp_to_registry(
    RegisterDppRequest(
        productIdentifier=dpp.product_id,
        dppIdentifier=dpp.dpp_id,
        operatorIdentifier="operator-123",
        repoUrl=local_repo_base_url(),
    )
)
print("registered:", registered.registryIdentifier)

# 6. Read it back — by id and by product id.
fetched = repo.read_dpp_by_id(dpp.dpp_id)
assert repo.read_dpp_by_product_id(dpp.product_id).dpp_id == dpp.dpp_id

# 7. Update a single curated element (PATCH /dpps/{id}/elements/{path}).
repo.update_data_element(dpp.dpp_id, "characteristics.productName", "ErgoChair Pro 2")

# 8. Soft-delete the passport (DELETE /dpps/{id}).
repo.delete_dpp_by_id(dpp.dpp_id)
```

## HTTP clients

The `httpx`-based clients for the registry and repository APIs live in `dpp_sdk.clients`.

In production, pass the real endpoint of each service explicitly:

```python
from dpp_sdk.clients import DppRegistryClient, DppRepoClient
from dpp_sdk.dpp4fun import Dpp4FunJsonCodec, validate_dpp4fun

repo = DppRepoClient(
    "https://repo.example.com",
    codec=Dpp4FunJsonCodec(),
    validator=validate_dpp4fun,
)
registry = DppRegistryClient("https://registry.example.com")
```

### Testing against the mock services

The companion [CIR4FUN-EU/dpp-sdk](https://github.com/CIR4FUN-EU/dpp-sdk) project ships
runnable mock services (`mock-dpp-repo`, `mock-eu-registry`) so you can integration-test
your application against real REST endpoints. Start them with the provided
[`docker-compose.yml`](https://github.com/CIR4FUN-EU/dpp-sdk/blob/main/dpp-sdk-demo/docker-compose.yml):

```bash
git clone https://github.com/CIR4FUN-EU/dpp-sdk.git
cd dpp-sdk/dpp-sdk-demo
docker compose up --build      # repo on :8080, registry on :8081
```

Then point the clients at them with the `for_local_mock()` factories:

```python
repo = DppRepoClient.for_local_mock(Dpp4FunJsonCodec(), validate_dpp4fun)
registry = DppRegistryClient.for_local_mock()

# Verify the services are up before exercising them (GET /health):
assert repo.health_check() and registry.health_check()
```

`for_local_mock()` defaults to the mock endpoints **`http://localhost:8080`** (repo) and
**`http://localhost:8081`** (registry). Override them without code changes via environment
variables — either the port or a full base URL:

| Variable | Default | Overrides |
|---|---|---|
| `DPP_REPO_PORT` / `DPP_REGISTRY_PORT` | `8080` / `8081` | the port on `localhost` |
| `DPP_REPO_BASE_URL` / `DPP_REGISTRY_BASE_URL` | — | the whole base URL (takes precedence) |

Or pass an explicit override directly: `DppRepoClient.for_local_mock(codec, validator, base_url="http://localhost:9000")`.
The defaults are also exposed as `DEFAULT_REPO_BASE_URL` / `DEFAULT_REGISTRY_BASE_URL` and the
helpers `local_repo_base_url()` / `local_registry_base_url()` in `dpp_sdk.clients`.

## Packages

| Package | Purpose |
|---|---|
| `dpp_sdk.core` | Core DPP model, validation, and JSON transport |
| `dpp_sdk.dpp4fun` | Furniture-specific DPP aggregate |
| `dpp_sdk.clients` | HTTP clients for the DPP registry & repository APIs |