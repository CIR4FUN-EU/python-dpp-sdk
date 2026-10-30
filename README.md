# dpp-sdk

`dpp-sdk` is a Python library for Digital Product Passports (DPPs). With it you can:

- describe a product passport in Python and check that it is valid,
- turn it into JSON and back,
- save it in a DPP **repository** and register it in a DPP **registry**.

The clients work with any repository or registry that implements the EN 18222 API. For local
testing, you can start example Java services with one command (see below).

## Install

You need Python 3.11 or newer.

```bash
pip install dpp-sdk
```

## Create, save, and register a passport

### 1. Start a repository and a registry

Skip this step if you already have EN 18222 services. Otherwise, start the example Java services
locally. This needs [Docker](https://docs.docker.com/get-started/get-docker/) (on Windows and macOS:
Docker Desktop, started).

Download the service definition into an empty folder and start it:

**Windows (PowerShell):**

```powershell
curl.exe -O https://raw.githubusercontent.com/CIR4FUN-EU/python-dpp-sdk/main/examples/mock-services-demo/compose.yaml
docker compose up -d --wait
```

**Linux/macOS:**

```bash
curl -O https://raw.githubusercontent.com/CIR4FUN-EU/python-dpp-sdk/main/examples/mock-services-demo/compose.yaml
docker compose up -d --wait
```

When the command finishes, the repository runs at `http://localhost:8080` and the registry at
`http://localhost:8081`.

### 2. Run the workflow

Save this as `workflow.py` in the same folder:

```python
import json
from datetime import UTC, datetime
from uuid import uuid4

from dpp_sdk import Dpp4FunJsonCodec, DppHeader, Granularity, validate_dpp4fun
from dpp_sdk.clients import (
    DppRegistryClient,
    DppRepoClient,
    DppRepresentation,
    RegisterDppRequest,
)
from dpp_sdk.dpp4fun import ChairCharacteristics, Dpp4Fun, Nameplate

# Replace these with your own services. Any EN 18222 repository/registry works.
REPO_URL = "http://localhost:8080"
REGISTRY_URL = "http://localhost:8081"

# 1. Create a passport for a blue chair.
token = uuid4().hex  # unique IDs, so you can run this script more than once
passport = Dpp4Fun.create(
    DppHeader(
        digital_product_passport_id=f"urn:example:dpp:{token}",
        unique_product_identifier=f"urn:example:product:{token}",
        granularity=Granularity.ITEM,
        last_updated=datetime.now(UTC),
        dpp_status="active",
        economic_operator_id="urn:example:operator:demo",
    ),
    Nameplate.create(manufacturerName="Example Furniture"),
    ChairCharacteristics.create(color="blue"),
)

# 2. Check it before sending it anywhere.
report = validate_dpp4fun(passport)
if not report.is_valid:
    raise SystemExit(f"Passport is not valid: {report.issues}")

# 3. Save it in the repository.
full_json = json.loads(Dpp4FunJsonCodec().to_json(passport))
with DppRepoClient(REPO_URL) as repository:
    created = repository.create_dpp(full_json, DppRepresentation.FULL)
passport_id = created.digital_product_passport_id or passport.header.digital_product_passport_id
print("Saved passport:", passport_id)

# 4. Register it, so others can find it.
with DppRegistryClient(REGISTRY_URL) as registry:
    registration = registry.post_new_dpp_to_registry(
        RegisterDppRequest(
            unique_product_identifier=passport.header.unique_product_identifier,
            digital_product_passport_id=passport_id,
            unique_economic_operator_identifier=passport.header.economic_operator_id,
            dpp_api_endpoint=f"{REPO_URL}/v1/dpps",
        )
    )
print("Registered:", registration.registration_id)

# 5. Read it back as a typed passport.
with DppRepoClient(REPO_URL) as repository:
    response = repository.read_dpp_by_id(passport_id, DppRepresentation.FULL)
loaded = Dpp4FunJsonCodec().from_json(json.dumps(response.payload))
print("Manufacturer:", loaded.typed_aspect(Nameplate).field("manufacturerName").value)
```

Run it:

```bash
python workflow.py
```

You should see three lines similar to:

```text
Saved passport: urn:example:dpp:a06675bc10d4439e9b6de17e899c51b1
Registered: e532b61a-d1cb-47dd-8589-ce6a2f387de8
Manufacturer: Example Furniture
```

The clients send and return plain JSON (Python dicts), and the codecs read and write JSON strings.
That is why the script uses `json.loads()` before sending and `json.dumps()` after reading.

Steps 1 and 2 of the script (create and check) work without any service.

To also read, update, look up older versions of, and delete a passport, see the
[full lifecycle example](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/examples/consumer_lifecycle.py).

### 3. Stop the services

Run this in the same folder:

```bash
docker compose down
```

The stored data is kept for next time. To delete it too, run `docker compose down -v`.

## How the SDK is organized

<img src="https://raw.githubusercontent.com/CIR4FUN-EU/python-dpp-sdk/main/docs/architecture/python-sdk-overview.svg" alt="Diagram: your application uses the DPP4Fun profile, the Core models, and the Clients. DPP4Fun builds on Core. The Clients send HTTP requests to repository and registry APIs." width="560">

| Part | What it does |
| --- | --- |
| `dpp_sdk.core` | General passport model, validation, and JSON conversion. |
| `dpp_sdk.dpp4fun` | Ready-made furniture passport (chairs, sofas, …) built on Core. |
| `dpp_sdk.clients` | HTTP clients for repositories and registries. They send and receive plain JSON and don't depend on the models. |

## The DPP4Fun furniture passport

`dpp_sdk.dpp4fun` is a ready-to-use passport for furniture, based on the DPP4Fun profile (D4.1).
You fill it with typed Python objects instead of building raw DataElements yourself.

A passport has a header plus any of these 19 **aspects**:

| Topic | Aspects |
| --- | --- |
| Identity and origin | `Nameplate`, `Traceability`, `ProductRelationship` |
| Environment and health | `EnvironmentalImpact`, `CarbonFootprint`, `BillOfMaterials`, `HealthImpact` |
| Circularity | `Durability`, `Reliability`, `Repairability`, `Refurbishment`, `Remanufacturing`, `Reusability`, `Recyclability`, `Upgradability`, `WasteManagement` |
| Use and rights | `Usage`, `Safety`, `RightOfEndUsers` |

It can also have one **product type** with its own fields: `ChairCharacteristics`,
`CribCharacteristics`, `FabricCharacteristics`, `LockerCharacteristics`,
`ParticleBoardCharacteristics`, or `SofaCharacteristics`.

Reusable **building blocks** go inside the aspects, for example `Material`, `Component`, `Part`,
`Certificate`, `Instruction`, `Contact`, and records such as `ManufacturingRecord` or `RepairRecord`.

What you can do with it:

- **Create and edit** passports with typed fields. Edits return a new copy (`with_field()`).
- **Use units safely:** `Dpp4FunQuantity` pairs a number with a `LengthUnit`, `MassUnit`, or
  `VolumeUnit`. Values with the wrong kind of unit are rejected.
- **Validate** against the D4.1 rules with `validate_dpp4fun()`. You get a list of issues, each
  with the path of the field it concerns.
- **Convert** to and from FULL and COMPRESSED JSON with `Dpp4FunJsonCodec`. The built-in profile
  describes all 488 fields, so COMPRESSED JSON can be expanded again.
- **Keep extra data:** fields that are not part of the profile are kept, not dropped.

Field names are the camelCase IDs used in JSON (`manufacturerName=`, not `manufacturer_name=`).
The [field reference](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/docs/dpp4fun-fields.md)
lists all of them per aspect, and the [model guide](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/docs/model-guide.md)
shows how to build, read, edit, and validate passports.

## Handle errors

Validation never raises; it returns a report (`report.is_valid`, `report.issues`). Everything else
raises a specific exception:

| Exception | Raised when |
| --- | --- |
| `DppNetworkClientError` | The service cannot be reached, or the request times out. |
| `DppApiClientError` | The service answers with an API error, for example `ClientErrorResourceNotFound`. Has the HTTP status and the service messages. |
| `DppHttpClientError` | The service answers with an HTTP error that is not an API error envelope. |
| `DppMappingClientError` | A request cannot be serialized, or a response is not a valid envelope. |
| `DppMappingError` | Passport JSON cannot be read or written (bad JSON, wrong structure, missing header fields). |
| `DppValidationError` | Only from `from_json_and_validate()`: the JSON was read, but the passport is not valid. |

The client exceptions are in `dpp_sdk.clients`; the model exceptions are in `dpp_sdk`.

```python
from dpp_sdk.clients import DppApiClientError, DppNetworkClientError

try:
    with DppRepoClient(REPO_URL) as repository:
        repository.read_dpp_by_id(passport_id)
except DppApiClientError as error:
    print("Service returned an error:", error)
except DppNetworkClientError:
    print("Service not reachable")
```

## Documentation

| If you want to… | Read |
| --- | --- |
| build, read, edit, validate, and convert passports | [Model guide](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/docs/model-guide.md) |
| find the field names of a DPP4Fun aspect | [DPP4Fun field reference](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/docs/dpp4fun-fields.md) |
| see every client method and error | [HTTP clients guide](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/docs/clients-guide.md) |
| build passports for another product group | [Building your own profile](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/docs/extending.md) |
| trace behavior to EN 18222/18223/18219 or D4.1 | [Standards alignment and validation rules](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/docs/conformance.md) |
| run the guided demo with test scenarios | [Mock-services demo](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/examples/mock-services-demo/README.md) |
| see what changed, or upgrade from an older version | [Changelog](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/CHANGELOG.md) |
| contribute, run the tests, or work on this repository | [Contributing guide](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/CONTRIBUTING.md) |

## Terms used here

- **DPP (Digital Product Passport):** a structured record about one product, model, or batch.
- **Repository:** a service that stores passports.
- **Registry:** a service that records where a passport is stored, so it can be found.
- **FULL / COMPRESSED:** two JSON forms of a passport. FULL includes type information for every
  field; COMPRESSED is shorter and contains only the values.
- **DataElement:** one field or group of fields inside a passport.
- **DPP4Fun:** a furniture passport profile, defined in the project document D4.1.
- **AAS (Asset Administration Shell):** the template format in which the DPP4Fun fields are published.

## Standards and limitations

The SDK follows selected parts of these standards. This is not a claim of full conformance,
certification, or legal compliance.

- **EN 18222:2026** (repository and registry API): Clauses 4.2–4.8, 5.2, 6.2–6.3, 7.2, 8.1–8.4.
- **EN 18223:2026** (passport model and JSON): Clauses 4.1.2.1–4.1.2.9 and 5.2.2–5.2.9.
- **EN 18219:2026** (identifiers): local syntax checks for GS1 Digital Link, GS1 GLN, and
  Identification Link only. The SDK does not issue, resolve, or prove uniqueness of identifiers.
- **DPP4Fun D4.1 v1.0**, Sections 3.2.1–3.2.2. Where D4.1 contradicts itself, the
  [standards page](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/docs/conformance.md#source-alignment-and-source-conflicts)
  explains which choice the SDK makes.

Not included:

- No authentication, retries, caching, or automatic pagination (you pass `cursor` yourself).
- No complete JSON Merge Patch (RFC 7396) or JSONPath (RFC 9535) implementation. The client sends
  your update as-is, and the service decides how to apply it.
- No registry delete or read-back, no backup-operator support, and no lifecycle-event history.
- COMPRESSED JSON is the JSON API shape used by the Java services, not the XML form in
  EN 18223 Annex B.
- No connection to a real EU registry, and no production hardening.

## Versioning

`dpp-sdk` is in the 0.x phase: a new minor version may contain breaking changes. Every
breaking change is listed in the [changelog](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/CHANGELOG.md) with migration notes. The public API
is what `dpp_sdk`, `dpp_sdk.core`, `dpp_sdk.dpp4fun`, and `dpp_sdk.clients` export; modules and
names starting with `_` are internal.

## Contributing and license

To work on the SDK itself, see the [contributing guide](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/CONTRIBUTING.md). The release steps are
in the [release guide](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/RELEASING.md). The license is in
[LICENSE](https://github.com/CIR4FUN-EU/python-dpp-sdk/blob/main/LICENSE).
