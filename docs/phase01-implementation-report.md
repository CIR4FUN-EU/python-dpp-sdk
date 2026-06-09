# Phase 01 — Implementation Report: Core Models + Errors

**Step:** 1 of 7 (`core/errors.py`, `core/model.py`)
**Status:** ✅ Complete — imports, JSON round-trip, and structural validation verified
**Ports from Java:** `dppsdk.core.model.*` (+ exception split) in
`../dpp-sdk-platform/dpp-datamodel/dpp-core`

---

## Goal

Reproduce the reusable **core DPP domain model** as idiomatic Pydantic v2, where a
single frozen model per type doubles as both the domain object and the JSON
transport payload — collapsing the Java `model` + `payload` POJO + hand-written
`Mapper` triple into one declarative class.

## Files created

| File | Contents |
|---|---|
| `src/dpp_sdk/core/errors.py` | Exception hierarchy: `DppError` → `DppValidationError`, `DppMappingError` |
| `src/dpp_sdk/core/model.py` | `OrganizationRole` enum, 9 core models, `Dpp` aggregate base, shared annotated field types |

### Models implemented (field names = verbatim camelCase JSON keys)

- `OrganizationRole` — `MANUFACTURER`, `SUPPLIER`, `DISTRIBUTOR` (`StrEnum`)
- `Address` — country, zipCode, region, town, street
- `Email` — emailAddress, typeOfEmail
- `Telephone` — telephoneNumber, typeOfTelephone
- `Contact` — organization, address, email, telephone
- `Organization` — name, gln, productDescription, productDesignation, productFamily, productRoot, productOrderSuffix, uri, contact, role
- `Nameplate` — gtinCode, internalArticleNumber, batchNumber, customsTariffNumber, uriOfTheProduct, manufacturer, supplier
- `Documentation` — digitalInstructionsLink, safetyInstructionsLink, downloadable, availableForYears, paperCopyAvailableOnRequest
- `PassportMetadata` — uniqueProductIdentifier (UUID), passportUpdateDates (list[date]), qrCodeOrDigitalTag, externalDocumentationLink
- `DppCore` — passportMetadata, nameplate, documentation
- `Dpp` — abstract aggregate base: holds `coreDpp`, exposes read-through accessors and `dpp_id` / `product_id`

## Key design decisions applied

1. **One frozen model = domain + wire.** `model_config = ConfigDict(frozen=True,
   populate_by_name=True, extra="forbid")`. `UUID` → canonical string and `date` →
   ISO `yyyy-MM-dd` automatically, matching the Java `*Payload` shapes. No separate
   payload/mapper layer needed.
2. **`extra="forbid"`** mirrors Jackson's default of failing on unknown properties.
3. **Nulls and primitive defaults are emitted** (no `exclude_none`); booleans default
   `False`. This is required for byte-level wire parity, since Jackson has no
   `@JsonInclude(NON_NULL)`.
4. **Two-tier validation — only the *structural* tier here.** The checks performed by
   the Java `Builder.build()` methods are enforced on construction via required fields
   plus two reusable annotated types:
   - `NonBlankStr` — required, rejects blank (`AfterValidator`)
   - `OptionalStr` — optional, rejects blank when present
   - `NonNegativeInt` — `Field(ge=0)` for `availableForYears`
   - `passportUpdateDates` uses `Field(min_length=1)` (non-empty)

   *Semantic* rules (future dates, role-in-slot, cross-object, …) are intentionally
   **deferred to Step 2** (`core/validation.py`), preserving the Java behavior where
   `fromJson` is lenient and only explicit validation rejects them.
5. **Immutability + edits.** Frozen models; the Java `toBuilder()` edit pattern maps to
   Pydantic `model_copy(update=...)`.
6. **Exception naming.** Custom `DppValidationError` avoids clashing with
   `pydantic.ValidationError` (which surfaces structural/construction failures).

## Verification performed

- `import dpp_sdk.core...` succeeds; `DppCore` constructs from nested submodels.
- `model_dump(mode="json")` / `model_dump_json()` emit nulls, stringified UUID
  (`11111111-...`) and ISO dates (`2024-01-01`) — matching the Java payload shape.
- Round-trip `DppCore.model_validate_json(core.model_dump_json()) == core` → **True**.
- Structural failures raise `pydantic.ValidationError`: blank `gtinCode`, empty
  `passportUpdateDates`, blank optional `uri`.
- Future `passportUpdateDates` **construct successfully** (confirming the structural
  tier is lenient, per decision 4).

## Parity notes / deviations

- Field/accessor names keep camelCase to match JSON keys 1:1; the `N802`/`N815` ruff
  rules are intentionally suppressed for `core/model.py` only.
- The Java `DppCore` exposes convenience getters (`getGtinCode()`, etc.); in Python
  those aggregate-level accessors live on the `Dpp` base rather than on `DppCore`,
  keeping `DppCore` lean. Access nested values via `core.nameplate.gtinCode`.

## Downstream dependencies

Steps 2–7 build directly on this module: `core/validation.py` (semantic tier),
`dpp4fun/model.py` (reuses `NonBlankStr` / `OptionalStr` / `_Base` and extends `Dpp`),
and the transport + client layers.
