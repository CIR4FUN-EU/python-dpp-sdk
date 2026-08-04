# Validation-rule reference

## Purpose and scope

This is the semantic-rule lookup for explicitly invoked validators. Construction constraints and
field defaults belong to the [model guide](model-guide.md). Each public validator is fail-fast and
raises `DppValidationError`; `None` is accepted by leaf validators unless the row says it is
required by that validator.

## Core rules

| Validator | Rule and null behavior | Error path / evidence |
| --- | --- | --- |
| `validate_address` | `None` accepted; country/town and present optional text are non-blank. | `Address.*`; `src/dpp_sdk/core/validation.py`; `test_core_validation.py`. |
| `validate_email` | `None` accepted; address is non-blank and contains `@`; present type is non-blank. | `Email.emailAddress`; `test_email_must_contain_at`. |
| `validate_telephone` | `None` accepted; number and present type are non-blank. | `Telephone.*`; core validation tests. |
| `validate_contact` | `None` accepted; organization is non-blank and at least one address/email/telephone channel exists. | `Contact.*`; `test_contact_requires_a_channel`. |
| `validate_organization` | `None` is an error; name and present URI are non-blank; validates a present contact. | `Organization.*`; `test_organization_is_required`. |
| `validate_nameplate` | `None` is an error; GTIN and present identifiers are non-blank; manufacturer or supplier is required and each supplied slot must have its matching role. | `Nameplate.*`; `test_nameplate_requires_manufacturer_or_supplier`, role tests. |
| `validate_documentation` | `None` accepted; present links are non-blank; `downloadable=True` or present `availableForYears` requires a link. | `Documentation.*`; `test_documentation_downloadable_requires_link`. |
| `validate_passport_metadata` | `None` is an error; identifier and at least one date required; no null or future date; present tag/link text non-blank. | `PassportMetadata.passportUpdateDates[index]`; `test_future_date_rejected`. |
| `validate_dpp_core` | `None` is an error; order is metadata, nameplate, documentation. | `DppCore`; `test_core_aggregate_order_metadata_then_nameplate_then_documentation`. |

## DPP4Fun rules

| Validator | Rule and null behavior | Error path / evidence |
| --- | --- | --- |
| `validate_dimensions` | `None` accepted; supplied dimensions must be finite/non-negative; an existing object requires non-blank unit. | `Dimensions.*`; `test_dimensions_require_unit_when_values_present`. |
| `validate_material` | `None` accepted; name/reference non-blank; portion finite/non-negative; mandatory material requires portion greater than zero. | `Material.*`; `test_material_mandatory_requires_positive_portion`. |
| `validate_component` / `validate_part` | `None` accepted; name and present reference non-blank. | `Component.*` / `Part.*`; Bill-of-Materials tests. |
| `validate_bill_of_materials` | `None` accepted; null members fail with indexed paths; every member is validated before normalized name/reference duplicate detection. | `BillOfMaterials.materials[index]`, `components[index]`, `parts[index]`; duplicate/null-member tests. |
| `validate_product_classification` | `None` is an error; sector/category and present group/subcategory are non-blank; subcategory needs category and group needs sector; tags contain no null, blank, or normalized duplicate member. | `ProductClassification.*`, `tags[index]`; `test_tags_reject_duplicates`. |
| `validate_characteristics` | `None` is an error; product name non-blank; weight finite/non-negative; validates dimensions; features contain no null, blank, or normalized duplicate member. | `Characteristics.*`, `features[index]`; `test_features_reject_blank`. |
| `validate_dpp4fun` | `None` is an error; order is core, classification, characteristics, BOM, then cross rules. | `Dpp4Fun`; `test_dec_005_supported_aggregate_validation_order`. |
| DPP4Fun cross rules | Category and product type must contain one another when both have text; metadata external-documentation link requires a `Documentation` object. | Cross-object error text; `test_cross_rule_category_producttype_inconsistent`, `test_cross_rule_external_link_requires_documentation`. |

## Text, numeric, and collection conventions

The frozen Unicode whitespace table determines blankness; U+200B is visible text rather than
blank. Validation does not normalize input before storing it, but duplicate comparisons use the
contract whitespace normalization and case-insensitive comparison. Non-finite numeric values are
rejected at construction where constrained and are also defensively rejected by semantic validators
when bypassed values are supplied.

## Codec boundary, limitations, and next steps

JSON mapping is not a semantic validator: mapping failures are `DppMappingError`, while these rules
raise `DppValidationError`. See the [validation guide](validation-guide.md) for flat/nested codec
forms, root/null behavior, cause chaining, and round trips; see the [model guide](model-guide.md)
for construction fields and defaults.
