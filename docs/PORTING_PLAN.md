# DPP SDK — Python Port Plan

## Context

This project is the **Python port** of the Java DPP SDK that lives in the sibling repo
`../dpp-sdk-platform`. That Java SDK is a reference implementation for **Digital Product
Passports** (draft prEN-18222-aligned). The goal here is to provide *the same functionality*
as an idiomatic Python SDK.

Scope and fidelity decided with the user:
- **Cover:** the datamodel (`dpp-core` + `dpp4fun`) **and** the HTTP clients
  (`dpp-repo-client`, `dpp-registry-client`). **Exclude** the Spring Boot mock services /
  integration demo (reuse them only as a test oracle, see Verification).
- **Fidelity:** **idiomatic Python using Pydantic v2** — not a literal 1:1 port.

## Verdict (feasibility)

**High confidence, no architectural blockers.** The Java SDK has no code generation, no
annotation processors, no Lombok/MapStruct, and **no SAMM/ESMF/Catena-X or RDF/JSON-LD**.
It is hand-written immutable POJOs, hand-written bidirectional mappers, a validator registry,
Jackson JSON, and plain HTTP clients — all of which have clean (often simpler) Python
equivalents.

**Effort:** Java is ~6.9k LOC (datamodel + clients) + ~3.7k test LOC, but much is boilerplate
Pydantic gives for free. Idiomatic Python should land around **2.5–4k LOC**; realistic budget
**~4–7 focused weeks** to feature + test parity. Time goes into re-encoding validation rules
and reproducing the JSON transport contract — not raw translation.

## Why Pydantic collapses most of the work

The Java SDK is layered: immutable **model** → **Builder** → **Validator** (runtime
`Map<Class,Validator>` registry) → **payload DTO** → **Mapper** → **JsonCodec**. Pydantic v2
collapses these into one declarative class:

| Java layer | Python (Pydantic v2) |
|---|---|
| Immutable model + `private final` + equals/hashCode/toString | `class X(BaseModel)` + `model_config = ConfigDict(frozen=True)` — equality/repr/hash free |
| Nested static `Builder` + `toBuilder()` | keyword constructor + `model_copy(update=...)` |
| `Validator<T>` + `ValidationService` registry | `@field_validator` / `@model_validator` on the model |
| Jackson payload DTO + `@JsonProperty` | same model with `Field(alias=...)`, `populate_by_name=True` |
| `Mapper.toPayload/toDomain` | `model_dump(by_alias=True)` / `model_validate(...)` |
| `Dpp4FunJsonCodec` | `model_dump_json()` / `model_validate_json()` |

UUID → `uuid.UUID`, `LocalDate` → `datetime.date`, `OrganizationRole` → `enum.Enum`/`StrEnum`.

## Real challenges (where the time goes)

1. **Flat vs. nested transport (the tricky part).** The Java codec emits *flattened* outbound
   JSON (lifts `coreDpp`'s passportMetadata/nameplate/documentation to the root) but accepts
   *both* flat and nested inbound. Implement with a `@model_serializer` for flattening on
   output and a `@model_validator(mode="before")` to normalize flat-or-nested on input. Pin
   byte-for-byte wire compatibility with the Java output via golden-file round-trip tests —
   real consumers depend on the wire shape.
2. **~20 validators with cross-object/conditional rules** (externalDocumentationLink ⇒
   documentation required; category ↔ productType case-insensitive contains; mandatory
   material ⇒ portion > 0; BOM uniqueness by name+reference; update dates not in the future;
   dimensions present ⇒ unit required). Map to `@model_validator(mode="after")`; transcribe
   and test each against the Java `VALIDATION_RULES.md`.
3. **Fail-fast vs. collect-all.** Java throws on first violation (`ValidationException`);
   Pydantic aggregates all errors into one `ValidationError`. Decide and document the chosen
   contract (recommend adopting Pydantic's multi-error behavior; note the intentional diff).
4. **Immutability nuance.** `frozen=True` blocks reassignment but not in-place list mutation.
   Use `tuple`/`frozenset` for collection fields, or document the trade-off.
5. **HTTP clients.** `HttpDppRepoClient<T>` is generic over codec+validator and supports
   fine-grained element updates via **RFC 6902 JSON Patch**. Port with `httpx`; use the
   `jsonpatch` library; `<T>` → `TypeVar`/`Generic[T]` or a `type[BaseModel]` arg. The API
   wrapper DTOs (statusCode/payload/messages) become small Pydantic models.
6. **Packaging.** Ship a proper PyPI package: `pyproject.toml` (PEP 621), `src/` layout,
   `py.typed` marker, `ruff` + `mypy` + `pytest`. Flatten the Maven 7-module split into one
   package: `dpp_sdk.core`, `dpp_sdk.dpp4fun`, `dpp_sdk.clients`.

## Execution outline

1. **Package skeleton:** `pyproject.toml`, `src/dpp_sdk/{core,dpp4fun,clients}/`, `py.typed`,
   ruff/mypy/pytest config.
2. **Core models** (`dpp_sdk/core/model.py`): Pydantic models for PassportMetadata, Nameplate,
   Documentation, Organization, Contact, Address, Email, Telephone, DppCore; `OrganizationRole`
   enum. Field aliases mirror Jackson `@JsonProperty`.
3. **Core validation:** `@field_validator`/`@model_validator` encoding the core subset of
   `VALIDATION_RULES.md`.
4. **dpp4fun models + validation** (`dpp_sdk/dpp4fun/model.py`): Dpp4Fun, ProductClassification,
   Characteristics, Dimensions, BillOfMaterials/Material/Component/Part, plus cross-object rules.
5. **Transport:** `@model_serializer` (flatten out) + `@model_validator(mode="before")` (accept
   flat or nested) on Dpp4Fun, replacing `Dpp4FunJsonCodec`. Provide thin
   `to_json()/from_json()/from_json_and_validate()` helpers for API familiarity.
6. **HTTP clients** (`dpp_sdk/clients/`): `httpx`-based `DppRepoClient` / `DppRegistryClient`,
   generic over a model type; JSON-Patch updates via `jsonpatch`; API-wrapper response models.
7. **Tests:** port `TestDataFactory`/`CoreTestDataFactory` as pytest fixtures; replicate the
   Java round-trip, edge-case, inbound-validation, and end-to-end scenario suites.

## Verification

- **Wire compatibility (most important):** capture canonical JSON outputs from the Java SDK for
  the demo fixtures, commit them as golden files, and assert Python `model_dump_json()` matches
  (modulo key order). Round-trip both flat and nested inbound payloads.
- **Validation parity:** for every rule in `VALIDATION_RULES.md`, a passing case and a failing
  case; assert the failing case raises.
- **Client parity:** run the Python clients against the existing Java Spring Boot mock
  repo/registry in `../dpp-sdk-platform/dpp-sdk-demo` (reuse as a conformance oracle, do not
  port). Exercise create / read / update (JSON Patch) / register flows.
- `pytest` green, `mypy` clean, `ruff` clean.
