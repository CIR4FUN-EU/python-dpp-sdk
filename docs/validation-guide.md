# Validation guide

## Purpose and scope

Construction, semantic validation, and JSON mapping are deliberately separate. Use this guide to
choose the boundary; use the [validation-rule reference](validation-rules.md) for individual rules
and the [model guide](model-guide.md) for fields/defaults/null behavior.

## Construction versus semantic validation

Pydantic construction rejects missing required fields, blank contracted strings, unknown fields,
non-finite or negative constrained numeric values, and invalid nested model shape. It produces
frozen immutable values but does not run every business rule. `validate_dpp_core()` and
`validate_dpp4fun()` are explicit, non-mutating, fail-fast calls: they raise `DppValidationError`
for the first semantic violation and preserve the input object.

The aggregate order is fixed: `validate_dpp4fun()` validates the core, product classification,
characteristics, Bill of Materials, then cross-object rules. Collection failures name the indexed
member, for example `BillOfMaterials.materials[0]` or `ProductClassification.tags[1]`.

## Codec input, output, and failures

`to_json(dpp)` serializes a `Dpp4Fun` aggregate to a flat JSON object and rejects non-finite output
through `DppMappingError` with the underlying `ValueError` as its cause. `from_json(raw)` accepts a
flat object or a nested `coreDpp` object, normalizes to the nested in-memory model, and does not run
semantic validation. When both shapes carry core fields, the nested `coreDpp` values win.

`from_json()` rejects malformed JSON, `null`, non-object roots, non-finite JSON constants, null
string-list members, and Pydantic mapping failures with `DppMappingError`; parser and Pydantic
causes are retained. `from_json_and_validate(raw)` maps first and then invokes semantic validation.
Empty tuple-backed collections serialize as `[]`; present optional model fields serialize as `null`.

```python
from dpp_sdk import DppMappingError, DppValidationError, from_json_and_validate, to_json

try:
    passport = from_json_and_validate(raw_json)
    outgoing_json = to_json(passport)
except DppMappingError:
    # JSON syntax, root, normalization, or structural mapping failure.
    raise
except DppValidationError:
    # Semantically invalid, but structurally representable, passport.
    raise
```

## Immutable updates

`with_updates()` structurally revalidates the changed model and returns a new frozen value. It does
not call semantic validators implicitly. Perform explicit validation after an update when the
application requires a semantically valid aggregate.

## Errors, limitations, and next steps

Validators report the first observed failure only; they do not collect all problems, trim/repair
text, sort/deduplicate collections, or turn mapping errors into validation errors. The transport
codec is specific to DPP4Fun and does not create a generic core JSON codec. See the
[validation-rule reference](validation-rules.md), [model guide](model-guide.md), and
[SDK usage](usage.md) for the consumer workflow.
