# Models and validation

## Model boundary

The SDK models are frozen Pydantic v2 models. They preserve the camelCase field names used on the
JSON wire, reject unknown fields, and expose immutable tuples for contracted collections. Their
`with_updates()` method creates a structurally revalidated replacement; it does not mutate the
original instance.

The editable validation-flow diagram is [python-model-validation.mmd](diagrams/python-model-validation.mmd).

## Model families

| Family | Purpose | Key types |
| --- | --- | --- |
| Core | Reusable identity, organization, contact, nameplate, metadata, and documentation | `DppCore`, `PassportMetadata`, `Nameplate`, `Organization` |
| DPP aggregate | Read-through core properties and stable identifiers | `Dpp` |
| DPP4Fun | Furniture classification, characteristics, and Bill of Materials | `Dpp4Fun`, `ProductClassification`, `Characteristics`, `BillOfMaterials` |
| BOM members | Materials, components, parts, dimensions | `Material`, `Component`, `Part`, `Dimensions` |

The DPP identifier is `str(passportMetadata.uniqueProductIdentifier)`. The product identifier is
the nameplate `gtinCode`. Contracted lists are immutable tuples in memory and JSON arrays on the
wire.

## Construction and validated updates

Construction enforces structural rules: required nested models, required non-blank values, optional
text that is non-blank when present, enum shape, unknown fields, collection shape, and configured
numeric bounds. `with_updates()` reruns that structural construction boundary:

```python
new_nameplate = dpp.nameplate.with_updates(gtinCode="GTIN-0002")
updated = dpp.with_updates(coreDpp=dpp.coreDpp.with_updates(nameplate=new_nameplate))
```

Use normal construction and `with_updates()` for public application code. `model_construct()` and
unchecked `model_copy(update=...)` bypass structural construction and are unsuitable for public
validated updates.

## Structural and semantic validation

Structural checks happen during model construction and codec mapping. Semantic checks are explicit:

```python
from dpp_sdk import validate_dpp_core, validate_dpp4fun

validate_dpp_core(dpp.coreDpp)
validate_dpp4fun(dpp)
```

Validators are fail-fast: the first applicable breach raises `DppValidationError`; they do not trim,
sort, fill missing values, or mutate the supplied model. `DppMappingError` identifies mapping or
codec failure rather than a semantic-rule violation.

## Rule reference

This guide owns the documented semantic-rule summary. Field-by-field structural constraints remain
owned by the typed model definitions.

| Contract area | Behavior |
| --- | --- |
| Text | Required text must not be null or contract-blank. Optional text can be null but not contract-blank when present. Accepted text is not trimmed. |
| Unicode whitespace | The contract recognizes the frozen Unicode whitespace set used by `dpp_sdk.core._text`; U+200B is visible text, not blank. |
| Numeric values | Dimensions, material portion, and weight are finite and non-negative. Non-standard JSON numeric values are rejected by the codec. |
| Lists | `tags` and `features` require clean string members. A JSON null member is a structural mapping failure; defensive semantic validation reports an indexed error. |
| Aggregates | DPP4Fun checks core, classification, characteristics, Bill of Materials, and cross-rules in validator order. |
| Bill of Materials | Each member is validated; duplicate/reference and aggregate rules are enforced by the BOM validator. |

The validator's ordering is observable because it is fail-fast. Consumers should not depend on it to
accumulate every problem in a malformed object.

## Codec contracts

`to_json(dpp)` emits flattened DPP4Fun JSON. `from_json(raw)` accepts the supported flattened or
nested forms and returns `Dpp4Fun`; `from_json_and_validate(raw)` maps and then applies semantic
validation. A JSON root `null`, absent root value, or empty object is a mapping failure, not a
successful nullable result.

The codec rejects `NaN`, infinities, and exponent overflow. It also preserves the distinction
between a JSON list with a null member and an invalid list encountered by defensive validation.

## Failure stages

1. **Construction** — Pydantic raises a structural validation error for an invalid model shape.
2. **Semantic validation** — `validate_dpp_core()` or `validate_dpp4fun()` raises
   `DppValidationError` for a semantic rule.
3. **Codec mapping** — JSON normalization or model mapping raises `DppMappingError`.
4. **Client use** — public clients translate local validation/mapping, network, HTTP, and API
   envelope failures to distinct client error classes; see [Clients](clients.md).

For construction examples, start with [SDK usage](usage.md).
Next: [Clients](clients.md) for request-time validation, mapping, and transport failures.
