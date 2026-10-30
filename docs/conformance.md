# Standards alignment and validation rules

This page records which standard clauses the SDK follows, where the sources disagree and which
choice the SDK makes, and which validator enforces which rule family. It is reference material for
reviewers and integrators who need to trace behavior to a source. For how to use the models, see
the [model guide](model-guide.md).

This is a scoped alignment. It is not a formal conformance, certification, or legal-compliance
claim.

## Source alignment and source conflicts

Core model and JSON rules are aligned to selected requirements in EN 18223:2026 Clauses
4.1.2.1–4.1.2.9 and 5.2.2–5.2.9. EN 18223:2026 Clause 4.1.1 gives the prose and tables
precedence over conflicting UML/JSON representations. Clause 4.1.2.6 prose requires at least one
item while its table says `[0..*]`; this conflict remains recorded and validation/serialization
enforce the selected prose requirement. API client routes, fields, representations, and response
handling are traced to EN 18222:2026 Clauses 4.2–4.8, 5.2, 6.2–6.3, 7.2, and 8.1–8.4. D4.1
profile rules are traced to v1.0 Sections 3.2.1–3.2.2 and the packaged source-backed catalog. This
is a scoped alignment; it is not a formal conformance or certification claim.

The D4.1 catalog records source conflicts. The six Characteristics AAS templates and populated
examples define descriptive String `Surface`, while D4.1 prose describes numeric total area. The
profile follows the published AAS `xsd:string` binding without an inferred area field or semantic
IRI. `professionalUseOnly` remains Boolean per its published AAS binding despite conflicting D4.1
prose. `ComplianceStatus` remains String per its D4.1 and AAS binding. These values are not coerced
at the DPP4Fun boundary. Identifier validation covers the supported EN 18219:2026 methods through
local syntax/profile checks only, not identifier issuance, global uniqueness, or
external resolution, and unsupported schemes remain unsupported.

## Core rules

| Validator | Rule families | Evidence |
| --- | --- | --- |
| `DppValidator` | Required DPP/header identifiers and metadata, DataElement identity and cardinality, kind/datatype consistency, semantic references, and nested structural consistency. | `tests/test_core_validation_parity.py`; EN 18223 Clauses 4.1.2.3–4.1.2.9. |
| `DataFormatValidator` | EN JSON-native value types, language/resource syntax, URI syntax, and list structure. | `tests/test_core_validation_parity.py`; EN 18223. |
| `IdentifierValidator` | Explicit caller-selected supported EN 18219 identifier profiles and granularity behavior. It does not infer schemes from arbitrary identifier text or prove issuance, uniqueness, or resolution. | `tests/test_core_validation_parity.py`; EN 18219:2026 clauses 4.1–4.6, 5.1–5.6, 6.1–6.5 and Annexes; only the locally implemented methods are covered. |

## DPP4Fun rules

| Validator | Rule and null behavior | Error path / evidence |
| --- | --- | --- |
| `Dpp4FunValidationService` | Ordered composition: core semantics, generic data-format rules, optional caller-context identifier rules, then D4.1 profile rules. Returns `ValidationResult`; `None` produces `DPP4FUN_REQUIRED`. | Core paths, then catalog paths such as `elements.nameplate.gtinCode`; `test_dpp4fun_validation.py`. |
| D4.1 content profile | Unsupported IDs produce `DPP4FUN_CONTENT_SPEC_SUPPORTED`; general aspects require the common binding; at most one Characteristics content profile can be selected. | `contentSpecificationIds`; aggregate construction rejects multiple variants, validator reports unsupported/missing bindings. |
| Catalog structural bindings | Catalogued kinds, element IDs, dictionary references, and resolved datatypes must match. Wrong scalar JSON types, malformed `xsd:anyURI`, and known wrong-dimension unit symbols produce profile findings. | `elements.<aspect>...`; exact stable IDs in `test_dpp4fun_final_parity.py`. |
| Catalog collections | Empty profile containers are omitted; source cardinality and binding occurrence are checked where present; repeated items use their catalogued kind and indexed ID policy. | `elements.<aspect>.<list>[index]`; profile-driven tests and Java catalog validator evidence. |
| Instruction minima | Each Instruction item requires `name`, `description`, and `reference`. | `DPP4FUN_INSTRUCTION_*_REQUIRED`; item field paths. |
| Assessment minima | Certificate, StandardAssessment, Scoring, and Indicator items require `name` and `description`; CarbonFootprintCalculation has no inferred assessment minima. | `DPP4FUN_ASSESSMENT_*_REQUIRED`; item field paths. |
| Record minima | Source-defined Record items require name, description, operator, one time field, and subtype status where present. RepairRecord has no status field. | `DPP4FUN_RECORD_*_REQUIRED`; item field paths. |
| Source-conflicted values | `Surface` uses the published Characteristics AAS descriptive `xsd:string` binding with no inferred area field. Safety `professionalUseOnly` remains Boolean. `ComplianceStatus` remains String. The profile does not coerce these values; source disagreements remain recorded as profile evidence. | Catalog datatype checks; source conflicts are metadata, not runtime warnings. |

