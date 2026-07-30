# dpp-sdk (Python)

Python SDK for **Digital Product Passports (DPP)**, built on [Pydantic v2](https://docs.pydantic.dev).

It provides typed models, explicit validation, DPP4Fun JSON transport, and synchronous
HTTP clients for two reusable DPP backend roles:

- a **DPP registry** that stores registration metadata, and
- the **DPP repository** — hosted by economic operators or service providers.

The implemented surface is aligned with the selected reusable Java SDK contracts and
selected draft API shapes. This package does not operate a registry or repository and
does not claim standards compliance, certification, or European Commission hosting.

## Install

```bash
pip install dpp-sdk
```

Requires Python 3.11+.

## Quickstart

### Parse, validate, serialize

```python
from dpp_sdk import from_json, to_json, validate_dpp4fun


def parse_validate_and_serialize(raw_json: str) -> str:
    # Parse an incoming passport (accepts both flat and nested JSON objects).
    dpp = from_json(raw_json)

    # Validate the semantic DPP rule set (raises on the first violation).
    validate_dpp4fun(dpp)

    # Serialize back to flattened, interoperable JSON.
    return to_json(dpp)
```

### Full lifecycle

This builds a passport from typed models, validates it, and shows repository and registry
operations. Configure clients with endpoints available in your application environment.

```python
from datetime import date
from uuid import uuid4

from dpp_sdk import (
    Address,
    BillOfMaterials,
    Characteristics,
    Contact,
    Dimensions,
    Documentation,
    Dpp4Fun,
    Dpp4FunJsonCodec,
    DppCore,
    DppValidationError,
    Email,
    Material,
    Nameplate,
    Organization,
    OrganizationRole,
    PassportMetadata,
    ProductClassification,
    validate_dpp4fun,
)
from dpp_sdk.clients import (
    DppRegistryClient,
    DppRepoClient,
    RegisterDppRequest,
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
            uniqueProductIdentifier=uuid4(),  # drives dpp.dpp_id
            passportUpdateDates=[date.today()],
            qrCodeOrDigitalTag="QR-001",
        ),
        nameplate=Nameplate(
            gtinCode="GTIN-0001",  # drives dpp.product_id
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
        sector="Furniture",
        category="Office Chair",
        group="Seating",
        tags=["ergonomic", "adjustable"],
    ),
    characteristics=Characteristics(
        productName="ErgoChair Pro",
        productType="Office Chair",
        brand="ACME",
        dimensions=Dimensions(width=60.0, height=120.0, depth=60.0, unit="cm"),
        weight=14.5,
        features=["lumbar-support"],
    ),
    billOfMaterials=BillOfMaterials(
        materials=[
            Material(name="steel", mandatory=True, portion=0.6, reference="MAT-STEEL"),
            Material(name="foam", portion=0.4),
        ],
    ),
)

# 2. Validate against the full DPP rule set (fail-fast: raises the first violation).
try:
    validate_dpp4fun(dpp)
except DppValidationError as exc:
    raise SystemExit(f"passport is invalid: {exc}")

# 3. Connect the clients using application-provided endpoints.
repo = DppRepoClient("https://repo.example.com", Dpp4FunJsonCodec(), validate_dpp4fun)
registry = DppRegistryClient("https://registry.example.com")

# 4. Store the passport in the repository (POST /v1/dpps -> dppId).
created = repo.create_dpp(dpp)
print("stored:", created.dppId)

# 5. Register it with the registry. The registry verifies the repo reference,
#    so the passport must already exist in the repo.
registered = registry.post_new_dpp_to_registry(
    RegisterDppRequest(
        uniqueProductIdentifier=dpp.product_id,
        digitalProductPassportId=dpp.dpp_id,
        uniqueEconomicOperatorIdentifier="operator-123",
        dppApiEndpoint="https://repo.example.com",
    )
)
print("registered:", registered.registrationId)

# 6. Read it back — by id and by product id.
fetched = repo.read_dpp_by_id(dpp.dpp_id)
assert repo.read_dpp_by_product_id(dpp.product_id).dpp_id == dpp.dpp_id

# 7. Update a single curated element with its JSON value as the direct body
#    (PATCH /v1/dpps/{id}/elements/{path}).
repo.update_data_element(dpp.dpp_id, "$.characteristics.productName", "ErgoChair Pro 2")

# 8. Soft-delete the passport (DELETE /v1/dpps/{id}).
repo.delete_dpp_by_id(dpp.dpp_id)
```

### Validation and immutable updates

Domain models are frozen. Their contracted collections are immutable tuples in memory, while
the JSON codec continues to emit normal JSON arrays. Construction enforces structural rules;
call `validate_dpp_core()` or `validate_dpp4fun()` explicitly for semantic and cross-object
rules. Validation is **fail-fast**: it raises the first applicable `DppValidationError` and
never repairs, sorts, or mutates the model.

Use `with_updates()` rather than `model_copy(update=...)` for public model changes. It returns a
new frozen instance and structurally revalidates the change:

```python
updated = dpp.with_updates(
    characteristics=dpp.characteristics.with_updates(productName="ErgoChair Pro 2")
)
validate_dpp4fun(updated)
assert dpp.characteristics.productName == "ErgoChair Pro"  # original is unchanged
```

`model_construct()` and unchecked `model_copy(update=...)` are test-only bypass tools. Public
validators guarantee deterministic fail-fast behavior for normally constructed, codec-created,
or revalidating-update objects; they do not promise recovery from arbitrary internal corruption.

The cross-language text contract uses a frozen Unicode White_Space table:
`U+0009–U+000D`, `U+0020`, `U+0085`, `U+00A0`, `U+1680`, `U+2000–U+200A`,
`U+2028`, `U+2029`, `U+202F`, `U+205F`, and `U+3000`. `U+200B` is visible text.
Accepted strings retain their original code points; validation does not trim stored values.

`weight`, all three dimensions, and material `portion` must be finite and non-negative.
The codec rejects `NaN`, positive or negative infinity, and exponent overflow, and never emits
non-standard JSON numeric tokens. A standalone JSON root `null`, missing root, or empty object
is a causal mapping failure rather than a successful nullable result. A JSON `null` inside
`features` or `tags` fails structural mapping; direct defensive list validation reports an
indexed semantic validation failure.

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

### Canonical operations, errors, and compatibility

Current repository and registry operations use their exact `/v1` routes. For example,
`create_dpp()` sends `POST /v1/dpps`; `post_new_dpp_to_registry()` sends
`POST /v1/registerDPP`; and full reads use `GET /v1/dpps/{dppId}?representation=full`.
Registration requests use `uniqueProductIdentifier`, `digitalProductPassportId`,
`uniqueEconomicOperatorIdentifier`, and `dppApiEndpoint`; successful responses expose
`registrationId`.

`read_compressed_dpp_by_id()` returns the compressed representation rather than a full model.
`read_dpp_version_by_id_and_date()` is the canonical versioned history read. The older
`read_dpp_version_by_product_id_and_date()` unversioned product-ID route is **legacy compatibility only** and is not the primary route for new integrations.

`update_data_element(dpp_id, element_path, value)` sends `value` itself as the PATCH JSON body,
including `None` as JSON `null`; it does not wrap the value in a payload object. The retained
`UpdateDataElementRequest` DTO remains importable only for compatibility and cannot change that
canonical direct-body contract.

Dynamic path segments follow the selected Java wire behavior: `*` remains literal, `~` is
`%7E`, spaces are `%20`, and slash, plus, percent, query, fragment, and non-ASCII characters are
UTF-8 percent-encoded. Version timestamps are normalized to UTC and emitted with a trailing `Z`.

Client failures remain categorized: `DppValidationClientError` for local validation,
`DppMappingClientError` for encoding/mapping, `DppNetworkClientError` for timeout or transport,
`DppHttpClientError` for non-2xx responses, and `DppApiClientError` for failed API envelopes.
Use the canonical field names above in new code. Retained legacy registry aliases are input
compatibility only; canonical names are always emitted.

Both SDK clients support `close()` and `with` blocks. A client created by the SDK closes its
own HTTPX resource on `close()` or context exit; an injected `httpx.Client` remains caller-owned.

## Packages

| Package | Purpose |
|---|---|
| `dpp_sdk.core` | Reusable core models, identifiers, errors, and semantic validation |
| `dpp_sdk.dpp4fun` | Furniture-specific aggregate, semantic validation, and flat/nested JSON codec |
| `dpp_sdk.clients` | HTTP clients for the DPP registry & repository APIs |

Dependency direction is `dpp_sdk.clients` and `dpp_sdk.dpp4fun` toward reusable
`dpp_sdk.core`; core never imports either consumer. Java persistence, demo, mock-service,
Spring, Docker, and deployment diagrams are reference provenance, not current Python package
architecture.

Release preparation is documented in [RELEASING.md](RELEASING.md).
