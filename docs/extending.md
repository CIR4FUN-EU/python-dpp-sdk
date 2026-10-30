# Building your own profile

`dpp_sdk.dpp4fun` is one profile built on `dpp_sdk.core`. You can build passports for other product
groups the same way: Core gives you the passport model, JSON conversion, and the standard
validation, and you add three things for your product group:

1. **Element IDs and types:** which DataElements your passports contain.
2. **A semantic resolver:** where COMPRESSED JSON gets its types back from.
3. **Profile checks:** rules that apply on top of `DppValidator`.

The code blocks on this page build on each other and run in order. They use a small battery
profile as the example.

## 1. Build the passport from core elements

Give your profile a content-specification ID and put it in the header. Resolvers and validators use
it to recognise which profile a passport follows.

```python
from datetime import UTC, datetime

from dpp_sdk.core import (
    DataElementCollection,
    DigitalProductPassport,
    DppHeader,
    Granularity,
    SingleValuedDataElement,
)

PROFILE_ID = "urn:example:profile:battery:v1"

passport = DigitalProductPassport(
    dpp_header=DppHeader(
        digital_product_passport_id="urn:example:dpp:battery-1",
        unique_product_identifier="urn:example:product:battery-1",
        granularity=Granularity.ITEM,
        dpp_schema_version="1.0",
        dpp_status="active",
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
        economic_operator_id="urn:example:operator:acme",
        content_specification_ids=(PROFILE_ID,),
    ),
    data_elements=(
        DataElementCollection(
            element_id="battery",
            dictionary_reference="https://example.com/battery#Battery",
            elements=(
                SingleValuedDataElement(
                    element_id="chemistry",
                    value="LFP",
                    value_data_type="xsd:string",
                ),
                SingleValuedDataElement(
                    element_id="capacityKwh",
                    value=12.5,
                    value_data_type="xsd:double",
                ),
            ),
        ),
    ),
)
```

A small helper per aspect (like `Nameplate.create()` in DPP4Fun) is usually all the typing you
need. Start without one.

## 2. Resolve COMPRESSED JSON

COMPRESSED JSON drops `objectType`, datatypes, and dictionary references. To read it back into a
typed passport, implement `SemanticResolver`. It is a protocol with one method: given the
passport's content-specification IDs and an element path, return a `SemanticDefinition` or `None`
for "unknown".

```python
from collections.abc import Sequence

from dpp_sdk.core import DataElementKind, DppJsonCodec, SemanticDefinition, SemanticPath

BATTERY_FIELDS = {
    ("battery",): SemanticDefinition(
        kind=DataElementKind.COLLECTION,
        element_id="battery",
        dictionary_reference="https://example.com/battery#Battery",
    ),
    ("battery", "chemistry"): SemanticDefinition(
        kind=DataElementKind.SINGLE,
        element_id="chemistry",
        value_data_type="xsd:string",
        dictionary_reference_resolved=True,  # no dictionary reference, on purpose
    ),
    ("battery", "capacityKwh"): SemanticDefinition(
        kind=DataElementKind.SINGLE,
        element_id="capacityKwh",
        value_data_type="xsd:double",
        dictionary_reference_resolved=True,  # no dictionary reference, on purpose
    ),
}


class BatteryResolver:
    def resolve(
        self, content_specification_ids: Sequence[str], path: SemanticPath
    ) -> SemanticDefinition | None:
        if PROFILE_ID not in content_specification_ids:
            return None
        return BATTERY_FIELDS.get(path.segments)


codec = DppJsonCodec()
compressed = codec.to_compressed_json(passport)
result = codec.expand_compressed_json_with_resolver(compressed, BatteryResolver())
assert result.issues == ()
assert result.passport.data_elements[0].element_id == "battery"
assert codec.to_expanded_json(result.passport) == codec.to_expanded_json(passport)
```

Return a complete definition for each path:

- Set `element_id` to the field's element ID.
- Resolve every metadata item, even when the answer is "none": set
  `dictionary_reference_resolved=True` (or `value_data_type_resolved=True`) for a field that
  deliberately has no dictionary reference (or datatype). Otherwise the codec reports it as
  missing.

Fields the resolver does not know keep their value and appear in `result.issues`; the codec never
invents metadata. If you have the previous version of a passport, pass it as
`codec.expand_compressed_json(json_text, previous=old_passport, resolver=...)` and its metadata is
reused as well.

`dpp_sdk.dpp4fun.Dpp4FunSemanticResolver` is the DPP4Fun implementation of the same protocol, driven
by the bundled JSON profile. Look at it if your profile grows beyond a dictionary.

## 3. Add profile checks

Run `DppValidator` for the standard rules, then add your own findings as `ValidationIssue`s and
combine them into one `ValidationResult`:

```python
from dpp_sdk.core import DppValidator, ValidationIssue, ValidationResult


def validate_battery(dpp: DigitalProductPassport) -> ValidationResult:
    issues = list(DppValidator().validate(dpp).issues)
    battery = next((e for e in dpp.data_elements if e.element_id == "battery"), None)
    capacity = None
    if isinstance(battery, DataElementCollection):
        capacity = next((e for e in battery.elements if e.element_id == "capacityKwh"), None)
    if capacity is None:
        issues.append(
            ValidationIssue(
                path="elements.battery.capacityKwh",
                rule="BATTERY_CAPACITY_REQUIRED",
                message="battery capacity is required",
            )
        )
    return ValidationResult(issues)


assert validate_battery(passport).is_valid
assert not validate_battery(passport.with_updates(data_elements=())).is_valid
```

Use the same path style as the built-in validators (`header.<jsonField>`,
`elements.<elementId>...`) so that callers can handle all findings the same way.

## What you get for free

- FULL and COMPRESSED JSON in the shape the EN 18222 repository API uses, through `DppJsonCodec`.
- The HTTP clients, which take any JSON passport: `json.loads(codec.to_expanded_json(passport))`.
- Data-format and identifier checks (`DataFormatValidator`, `IdentifierValidator`); see the
  [model guide](model-guide.md#validate).
