# Model guide

## Purpose and scope

This is the normative field reference for public Python models. The [SDK usage guide](usage.md)
owns the walkthrough; the [validation guide](validation-guide.md) owns semantic-rule behavior; and
the [clients guide](../src/dpp_sdk/clients/README.md) owns HTTP payloads. All models are frozen
Pydantic models: unknown fields are rejected, `with_updates()` creates a structurally revalidated
replacement, and public field names are the emitted camelCase JSON names.

## Construction and JSON conventions

Required strings must be non-blank. Optional strings are either `null`/`None` or non-blank when
present; accepted values are not trimmed. UUIDs emit canonical strings, dates emit ISO dates, and
optional model fields emit `null` rather than being omitted. `OrganizationRole` is one of
`MANUFACTURER`, `SUPPLIER`, or `DISTRIBUTOR`.

## Reusable core models

| Model | Required fields | Optional fields and defaults | Nested values / notes |
| --- | --- | --- | --- |
| `Address` | `country: str`, `town: str` | `zipCode`, `region`, `street`: `str | None = None` | All text fields use the construction convention above. |
| `Email` | `emailAddress: str` | `typeOfEmail: str | None = None` | Semantic validation separately requires `@` in the address. |
| `Telephone` | `telephoneNumber: str` | `typeOfTelephone: str | None = None` | No telephone-format parser is supplied. |
| `Contact` | `organization: str` | `address`, `email`, `telephone`: `None` | Nested `Address`, `Email`, and `Telephone`. |
| `Organization` | `name: str` | `gln`, `productDescription`, `productDesignation`, `productFamily`, `productRoot`, `productOrderSuffix`, `uri`, `contact`, `role`: `None` | `contact: Contact | None`; `role: OrganizationRole | None`. |
| `Documentation` | none | `digitalInstructionsLink`, `safetyInstructionsLink`: `None`; `downloadable=False`; `availableForYears=None`; `paperCopyAvailableOnRequest=False` | `availableForYears` is a non-negative integer when present. |
| `Nameplate` | `gtinCode: str` | `internalArticleNumber`, `batchNumber`, `customsTariffNumber`, `uriOfTheProduct`, `manufacturer`, `supplier`: `None` | Manufacturer/supplier are `Organization | None`. |
| `PassportMetadata` | `uniqueProductIdentifier: UUID`, non-empty `passportUpdateDates: tuple[date, ...]` | `qrCodeOrDigitalTag`, `externalDocumentationLink`: `None` | Future dates are structurally accepted but semantically rejected. |
| `DppCore` | `passportMetadata`, `nameplate` | `documentation=None` | Reusable aggregate used as `Dpp4Fun.coreDpp`. |

`Dpp` is the reusable aggregate base. It exposes read-through properties for the core values and
the identifiers `dpp_id` (the UUID as text) and `product_id` (the nameplate GTIN); applications use
a concrete aggregate such as `Dpp4Fun`.

## DPP4Fun models

| Model | Required fields | Optional fields and defaults | Notes |
| --- | --- | --- | --- |
| `Dimensions` | `width`, `height`, `depth`: finite non-negative `float` | `unit=None` | All three values are required at construction; semantic validation also requires a non-blank unit. |
| `ProductClassification` | `sector`, `category`: non-blank `str` | `group=None`, `subCategory=None`, `tags=()` | Tags are immutable tuples in Python and JSON arrays on the wire. |
| `Characteristics` | `productName: str` | `description`, `brand`, `productType`, `dimensions`, `weight`, `color`: `None`; `features=()` | `weight` is finite/non-negative when present; `dimensions: Dimensions | None`. |
| `Material` | `name: str` | `mandatory=False`, `portion=0.0`, `reference=None` | Portion is finite/non-negative; semantic validation adds the mandatory/positive rule. |
| `Component` | `name: str` | `reference=None` | Used in `BillOfMaterials.components`. |
| `Part` | `name: str` | `mandatory=False`, `reference=None` | Used in `BillOfMaterials.parts`. |
| `BillOfMaterials` | none | `materials=()`, `components=()`, `parts=()` | Each collection is a tuple of its typed member and serializes as `[]` when empty. |
| `Dpp4Fun` | `coreDpp: DppCore`, `classification`, `characteristics` | `billOfMaterials=None` | Furniture aggregate; inherits the `Dpp` read-through properties. |

## Construction and serialized JSON example

The following flat transport JSON is valid input to `from_json()` and is the shape produced by
`to_json()`. `coreDpp` is an in-memory model field; transport lifts its `passportMetadata`,
`nameplate`, and `documentation` fields to the root.

```json
{
  "passportMetadata": {
    "uniqueProductIdentifier": "11111111-1111-1111-1111-111111111111",
    "passportUpdateDates": ["2026-06-29"],
    "qrCodeOrDigitalTag": null,
    "externalDocumentationLink": null
  },
  "nameplate": {
    "gtinCode": "04012345678901",
    "internalArticleNumber": null,
    "batchNumber": null,
    "customsTariffNumber": null,
    "uriOfTheProduct": null,
    "manufacturer": {"name": "Cir4Fun Furniture GmbH", "role": "MANUFACTURER"},
    "supplier": null
  },
  "documentation": null,
  "classification": {"sector": "Furniture", "group": null, "category": "Seating", "subCategory": null, "tags": []},
  "characteristics": {"productName": "ErgoChair", "description": null, "brand": null, "productType": null, "dimensions": null, "weight": null, "color": null, "features": []},
  "billOfMaterials": {"materials": [], "components": [], "parts": []}
}
```

## Immutable updates and validation boundary

Use `with_updates()` on the value being replaced; it re-enters structural Pydantic validation and
does not mutate the original value. It does not automatically perform semantic validation, so call
`validate_dpp_core()` or `validate_dpp4fun()` when that boundary matters.

```python
updated = dpp.with_updates(
    characteristics=dpp.characteristics.with_updates(productName="ErgoChair Pro")
)
validate_dpp4fun(updated)
assert dpp.characteristics.productName == "ErgoChair"
```

## Limitations and next steps

This guide does not define generic models for every product sector, service persistence, or an
implicit validation-on-parse mode. See the [validation guide](validation-guide.md) for error stages,
the [validation-rule reference](validation-rules.md) for exact semantic rules, and the
[DPP4Fun module guide](../src/dpp_sdk/dpp4fun/README.md) for the codec workflow.
