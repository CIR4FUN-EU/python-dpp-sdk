# SDK usage

## Purpose and scope

This is the end-to-end consumer walkthrough. Use the [model guide](model-guide.md) for field and
null semantics and the [validation guide](validation-guide.md) for the semantic-rule boundary.

## Installation

**Purpose:** install the published SDK before following this walkthrough. **Run from:** any
directory. **Prerequisites:** Python 3.11 or newer.

### PowerShell

PowerShell:

```powershell
python -m pip install dpp-sdk
```

### Linux/macOS

```bash
python -m pip install dpp-sdk
```

For a local checkout, use the repository's development environment and run its configured checks
from the repository root through the [release guide](../RELEASING.md). **Expected result:** an
installed `dpp_sdk` import. **Cleanup:** none. The
[Java-services demo](../examples/java-services-demo/README.md) has separate installation
instructions because it is a separate, unpublished consumer package.

## Imports

The top-level package exports the public models, semantic validators, common errors, and DPP4Fun
codec helpers. Clients and client request/response types are exported from `dpp_sdk.clients`.

```python
from dpp_sdk import Dpp4FunJsonCodec, from_json, to_json, validate_dpp4fun
from dpp_sdk.clients import DppRegistryClient, DppRepoClient, RegisterDppRequest
```

## Model construction

Create models with their documented camelCase transport fields. Pydantic construction checks the
structural contract immediately; the following complete example is also the basis of the test
fixtures.

```python
from datetime import date
from uuid import UUID

from dpp_sdk import (
    Address,
    BillOfMaterials,
    Characteristics,
    Contact,
    Dimensions,
    Documentation,
    Dpp4Fun,
    DppCore,
    Email,
    Material,
    Nameplate,
    Organization,
    OrganizationRole,
    PassportMetadata,
    ProductClassification,
)

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
            uniqueProductIdentifier=UUID("11111111-1111-1111-1111-111111111111"),
            passportUpdateDates=[date(2024, 1, 1)],
        ),
        nameplate=Nameplate(gtinCode="GTIN-0001", manufacturer=manufacturer),
        documentation=Documentation(
            digitalInstructionsLink="https://acme.example/docs",
            downloadable=True,
        ),
    ),
    classification=ProductClassification(sector="Furniture", category="Office Chair"),
    characteristics=Characteristics(
        productName="ErgoChair Pro",
        dimensions=Dimensions(width=60.0, height=120.0, depth=60.0, unit="cm"),
    ),
    billOfMaterials=BillOfMaterials(materials=[Material(name="steel", portion=0.6)]),
)
```

`dpp.dpp_id` is the string form of `uniqueProductIdentifier`; `dpp.product_id` is `gtinCode`.

## Validation

Construction is structural. Call the semantic validator explicitly before using a DPP as a valid
domain object or creating it in a repository:

```python
from dpp_sdk import DppValidationError, validate_dpp4fun

try:
    validate_dpp4fun(dpp)
except DppValidationError as exc:
    print(f"DPP semantic validation failed: {exc}")
```

The validators are fail-fast and do not mutate or repair the model. The
[core module guide](../src/dpp_sdk/core/README.md) and
[DPP4Fun module guide](../src/dpp_sdk/dpp4fun/README.md) own the detailed rule descriptions.

## Serialization and deserialization

Use the DPP4Fun helpers when your application exchanges DPP4Fun JSON:

```python
raw_json = to_json(dpp)
decoded = from_json(raw_json)
validate_dpp4fun(decoded)
assert to_json(decoded) == raw_json
```

`from_json()` maps a supported flat or nested payload but does not itself apply semantic
validation. `from_json_and_validate()` is available when an application needs both steps together.

## Immutable updates

Public domain models are frozen. Use `with_updates()` to construct a new, structurally revalidated
instance, then run semantic validation when the change can affect semantic or cross-model rules.

```python
updated = dpp.with_updates(
    characteristics=dpp.characteristics.with_updates(productName="ErgoChair Pro 2")
)
validate_dpp4fun(updated)
assert dpp.characteristics.productName == "ErgoChair Pro"
```

Do not use unchecked `model_copy(update=...)` as a public update mechanism: it can bypass the
structural construction boundary.

## Repository client

The repository client needs a base URL, a codec, and a validator. Context management closes the
internally created HTTPX client:

```python
from dpp_sdk import Dpp4FunJsonCodec, validate_dpp4fun
from dpp_sdk.clients import DppRepoClient

with DppRepoClient(
    "https://repo.example.com",
    codec=Dpp4FunJsonCodec(),
    validator=validate_dpp4fun,
) as repo:
    created = repo.create_dpp(dpp)
    fetched = repo.read_dpp_by_id(created.dppId)
```

See the [clients module guide](../src/dpp_sdk/clients/README.md) for all supported repository
operations and their error behavior.

## Registry client

Register only after the DPP is available at the repository endpoint provided in the request:

```python
from dpp_sdk.clients import DppRegistryClient, RegisterDppRequest

with DppRegistryClient("https://registry.example.com") as registry:
    registration = registry.post_new_dpp_to_registry(
        RegisterDppRequest(
            uniqueProductIdentifier=dpp.product_id,
            digitalProductPassportId=dpp.dpp_id,
            uniqueEconomicOperatorIdentifier="operator-123",
            dppApiEndpoint="https://repo.example.com",
        )
    )
```

The public registry client currently exposes health checking and registration, not registry
read-back or cleanup operations.

## Errors

Catch `DppValidationError` and `DppMappingError` for model/codec work. Client code can catch the
more specific classes exported by `dpp_sdk.clients`, or their common `DppClientError` base. Avoid
collapsing validation, mapping, network, HTTP, and API-envelope failures into one application error
when callers need to decide whether a request was sent.

## Resource ownership

Each client closes an HTTPX client that it created itself when `close()` is called or its context
manager exits. If you inject an `httpx.Client`, it stays caller-owned and is not closed by the SDK.

Next: consult the [clients module guide](../src/dpp_sdk/clients/README.md) for network behavior, the
[core module guide](../src/dpp_sdk/core/README.md) for reusable-model rules, or the
[DPP4Fun module guide](../src/dpp_sdk/dpp4fun/README.md) for aggregate and codec rules.
