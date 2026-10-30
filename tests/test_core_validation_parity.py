"""Source-backed core validation contract tests for final Java parity."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dpp_sdk.core.model import (
    DataElementCollection,
    DigitalProductPassport,
    DppHeader,
    Granularity,
    MultiLanguageDataElement,
    MultiLanguageValue,
    MultiValuedDataElement,
    RelatedResource,
    SingleValuedDataElement,
)
from dpp_sdk.core.validation import (
    DataFormatValidator,
    DppValidator,
    EconomicOperatorIdentifierMethod,
    FacilityIdentifierMethod,
    IdentifierValidationContext,
    IdentifierValidator,
    ProductIdentifierMethod,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    ValidationStatus,
)


def header(**changes: object) -> DppHeader:
    values: dict[str, object] = {
        "digital_product_passport_id": "urn:example:dpp:1",
        "unique_product_identifier": "free-form-product-id",
        "granularity": Granularity.MODEL,
        "dpp_schema_version": "2026",
        "dpp_status": "future-open-status",
        "last_updated": datetime(2026, 1, 1, tzinfo=UTC),
        "economic_operator_id": "free-form-operator-id",
    }
    values.update(changes)
    return DppHeader(**values)


def passport(*elements: object, **header_changes: object) -> DigitalProductPassport:
    return DigitalProductPassport(dpp_header=header(**header_changes), data_elements=elements)


def normalized(result: ValidationResult) -> list[tuple[str, str, str]]:
    return [(issue.rule, issue.path, issue.severity.value) for issue in result.issues]


@pytest.mark.parametrize(
    ("field", "rule"),
    [
        ("digital_product_passport_id", "EN18223_HEADER_DPP_ID_REQUIRED"),
        ("unique_product_identifier", "EN18223_HEADER_PRODUCT_ID_REQUIRED"),
        ("granularity", "EN18223_HEADER_GRANULARITY_REQUIRED"),
        ("dpp_schema_version", "EN18223_HEADER_SCHEMA_VERSION_REQUIRED"),
        ("dpp_status", "EN18223_HEADER_STATUS_REQUIRED"),
        ("last_updated", "EN18223_HEADER_LAST_UPDATED_REQUIRED"),
        ("economic_operator_id", "EN18223_HEADER_ECONOMIC_OPERATOR_ID_REQUIRED"),
    ],
)
def test_required_header_presence_is_aggregated(field: str, rule: str) -> None:
    result = DppValidator().validate(passport(**{field: None}))
    wire_field = {
        "digital_product_passport_id": "digitalProductPassportId",
        "unique_product_identifier": "uniqueProductIdentifier",
        "dpp_schema_version": "dppSchemaVersion",
        "dpp_status": "dppStatus",
        "last_updated": "lastUpdated",
        "economic_operator_id": "economicOperatorId",
    }.get(field, field)
    assert normalized(result) == [(rule, f"header.{wire_field}", "ERROR")]


def test_header_warning_is_non_failing_and_ids_are_not_overrestricted() -> None:
    result = DppValidator().validate(passport(digital_product_passport_id="plain-id"))
    assert normalized(result) == [
        ("EN18223_HEADER_DPP_ID_URI_RECOMMENDED", "header.digitalProductPassportId", "WARNING")
    ]
    assert result.status is ValidationStatus.VALID
    assert result.is_valid


def test_content_specification_values_are_nonblank_but_optional() -> None:
    assert DppValidator().validate(passport(content_specification_ids=())).is_valid
    result = DppValidator().validate(passport(content_specification_ids=("spec", " ")))
    assert normalized(result) == [
        ("EN18223_HEADER_CONTENT_SPEC_ID_NONBLANK", "header.contentSpecificationIds", "ERROR")
    ]


@pytest.mark.parametrize(
    ("element", "expected"),
    [
        (
            SingleValuedDataElement(element_id=" ", value="ok"),
            ("EN18223_ELEMENT_ID_REQUIRED", "elements[0].elementId"),
        ),
        (
            DataElementCollection(element_id="e"),
            ("EN18223_COLLECTION_NON_EMPTY", "elements[0].elements"),
        ),
        (
            SingleValuedDataElement(element_id="e"),
            ("EN18223_SINGLE_VALUE_REQUIRED", "elements[0].value"),
        ),
        (
            MultiValuedDataElement(element_id="e"),
            ("EN18223_MULTI_NON_EMPTY", "elements[0].elements"),
        ),
        (
            RelatedResource(element_id="e"),
            ("EN18223_RELATED_RESOURCE_CONTENT_TYPE_REQUIRED", "elements[0].contentType"),
        ),
        (
            MultiLanguageDataElement(element_id="e"),
            ("EN18223_MULTILANGUAGE_NON_EMPTY", "elements[0].values"),
        ),
    ],
)
def test_required_and_cardinality_rule_families(element: object, expected: tuple[str, str]) -> None:
    result = DppValidator().validate(passport(element))
    assert (result.issues[0].rule, result.issues[0].path) == expected


def test_all_element_issue_order_and_nested_paths_are_deterministic() -> None:
    values = MultiLanguageDataElement(
        element_id="names", value=(MultiLanguageValue(value=None, language=None),)
    )
    repeated = MultiValuedDataElement(
        element_id="list",
        value=(
            SingleValuedDataElement(element_id="x", value=1),
            SingleValuedDataElement(element_id="x", value="s"),
        ),
    )
    result = DppValidator().validate(passport(values, repeated, RelatedResource(element_id="r")))
    assert normalized(result) == [
        ("EN18223_ABSOLUTE_PATH_UNIQUE", "elements[1].elements[1].elementId", "ERROR"),
        ("EN18223_MULTILANGUAGE_VALUE_REQUIRED", "elements[0].values[0].value", "ERROR"),
        ("EN18223_MULTILANGUAGE_LANGUAGE_REQUIRED", "elements[0].values[0].language", "ERROR"),
        ("EN18223_JSON_NATIVE_TYPE_MATCHES_XSD", "elements[1].elements[1]", "ERROR"),
        ("EN18223_ELEMENT_ID_UNIQUE_WITHIN_LOCATION", "elements[1].elements[1].elementId", "ERROR"),
        ("EN18223_RELATED_RESOURCE_CONTENT_TYPE_REQUIRED", "elements[2].contentType", "ERROR"),
        ("EN18223_RELATED_RESOURCE_URL_REQUIRED", "elements[2].url", "ERROR"),
    ]


def test_identifier_uniqueness_is_sibling_local_and_absolute_paths_are_unique() -> None:
    tree = DataElementCollection(
        element_id="a", elements=(SingleValuedDataElement(element_id="b", value="nested"),)
    )
    flat = SingleValuedDataElement(element_id="a.b", value="flat")
    siblings = (
        SingleValuedDataElement(element_id="same", value=1),
        SingleValuedDataElement(element_id="same", value=2),
    )
    result = DppValidator().validate(
        passport(tree, flat, DataElementCollection(element_id="left", elements=siblings))
    )
    assert normalized(result) == [
        ("EN18223_ABSOLUTE_PATH_UNIQUE", "elements[1].elementId", "ERROR"),
        ("EN18223_ABSOLUTE_PATH_UNIQUE", "elements[2].elements[1].elementId", "ERROR"),
        ("EN18223_ELEMENT_ID_UNIQUE_WITHIN_LOCATION", "elements[2].elements[1].elementId", "ERROR"),
    ]


def test_mixed_concrete_kinds_emit_rule_and_children_still_validate() -> None:
    value = MultiValuedDataElement(
        element_id="list",
        value=(
            SingleValuedDataElement(element_id="one", value=1),
            DataElementCollection(element_id="two"),
        ),
    )
    result = DppValidator().validate(passport(value))
    assert normalized(result) == [
        ("EN18223_MULTI_HOMOGENEOUS_KIND", "elements[0].elements[1]", "ERROR"),
        ("EN18223_COLLECTION_NON_EMPTY", "elements[0].elements[1].elements", "ERROR"),
    ]


def test_malformed_python_shape_remains_a_construction_error() -> None:
    with pytest.raises(ValidationError):
        DppHeader.model_validate({"granularity": "not-a-granularity"})
    with pytest.raises(ValidationError):
        DigitalProductPassport.model_validate({"elements": [{"objectType": "unknown"}]})


def test_unknown_runtime_subtype_is_a_semantic_issue_only_after_structural_bypass() -> None:
    @dataclass
    class UnknownElement:
        element_id: str = "custom"

    aggregate = DigitalProductPassport.model_construct(
        dpp_header=header(), data_elements=(UnknownElement(),)
    )
    result = DppValidator().validate(aggregate)  # type: ignore[arg-type]
    assert normalized(result) == [
        ("EN18223_OBJECT_TYPE_MATCHES_RUNTIME_KIND", "elements[0]", "ERROR")
    ]


def test_null_passport_and_issue_result_contracts() -> None:
    result = DppValidator().validate(None)
    assert result.status is ValidationStatus.INVALID
    assert normalized(result) == [("DPP_REQUIRED", "dpp", "ERROR")]
    assert not result.is_valid
    issue = ValidationIssue("x", "X", "message")
    assert issue.severity is ValidationSeverity.ERROR
    assert ValidationIssue.Severity.WARNING is ValidationSeverity.WARNING
    assert ValidationResult.of([issue]).issues == (issue,)
    with pytest.raises(AttributeError):
        result.issues.append(issue)  # type: ignore[attr-defined]
    with pytest.raises(FrozenInstanceError):
        result._status = ValidationStatus.VALID  # type: ignore[misc]


def test_format_validation_covers_datatype_vocabulary_values_and_references() -> None:
    items = (
        SingleValuedDataElement(element_id="ok", value="hi", value_data_type="xsd:string"),
        SingleValuedDataElement(element_id="bad-type", value="opaque", value_data_type="xsd:token"),
        SingleValuedDataElement(element_id="bad-value", value="1e2", value_data_type="xsd:decimal"),
        SingleValuedDataElement(
            element_id="bad-uri", value="relative", value_data_type="xsd:anyURI"
        ),
        MultiValuedDataElement(
            element_id="mixed-types",
            value_data_type="xsd:string",
            value=(
                SingleValuedDataElement(element_id="v", value="ok", value_data_type="xsd:integer"),
            ),
        ),
    )
    result = DataFormatValidator().validate(passport(*items))
    assert normalized(result) == [
        ("EN18223_VALUE_DATATYPE_SUPPORTED", "elements[1].valueDataType", "ERROR"),
        ("EN18223_VALUE_MATCHES_DATATYPE", "elements[2].value", "ERROR"),
        ("EN18223_VALUE_MATCHES_DATATYPE", "elements[3].value", "ERROR"),
        ("EN18223_MULTI_HOMOGENEOUS_DATATYPE", "elements[4].elements[0].valueDataType", "ERROR"),
        ("EN18223_VALUE_MATCHES_DATATYPE", "elements[4].elements[0].value", "ERROR"),
    ]


@pytest.mark.parametrize(
    ("value_type", "value", "expected_rule"),
    [
        ("xsd:madeUpType", "opaque", "EN18223_VALUE_DATATYPE_SUPPORTED"),
        ("xsd:boolean", "true", "EN18223_VALUE_MATCHES_DATATYPE"),
        ("xsd:integer", 1.5, "EN18223_VALUE_MATCHES_DATATYPE"),
        ("xsd:date", "2026-02-30", "EN18223_VALUE_MATCHES_DATATYPE"),
        ("xsd:dateTime", "2026-01-01T12:00:00+00:00", "EN18223_VALUE_MATCHES_DATATYPE"),
        ("xsd:base64Binary", "not base64!", "EN18223_VALUE_MATCHES_DATATYPE"),
        ("xsd:positiveInteger", 0, "EN18223_VALUE_MATCHES_DATATYPE"),
    ],
)
def test_datatype_failure_families_have_canonical_rule_path_and_severity(
    value_type: str, value: object, expected_rule: str
) -> None:
    result = DataFormatValidator().validate(
        passport(SingleValuedDataElement(element_id="v", value=value, value_data_type=value_type))
    )
    path = (
        "elements[0].value"
        if expected_rule == "EN18223_VALUE_MATCHES_DATATYPE"
        else "elements[0].valueDataType"
    )
    assert normalized(result) == [(expected_rule, path, "ERROR")]


def test_all_java_xsd_datatype_categories_and_integer_boundaries_are_accounted_for() -> None:
    type_values = {
        "anySimpleType": {"opaque": True},
        "duration": {"opaque": True},
        "time": {"opaque": True},
        "gYearMonth": {"opaque": True},
        "gYear": {"opaque": True},
        "gMonthDay": {"opaque": True},
        "gDay": {"opaque": True},
        "gMonth": {"opaque": True},
        "hexBinary": {"opaque": True},
        "integer": 1,
        "nonPositiveInteger": 0,
        "negativeInteger": -1,
        "long": 1,
        "int": 1,
        "short": 1,
        "byte": 1,
        "nonNegativeInteger": 0,
        "unsignedLong": 1,
        "unsignedInt": 1,
        "unsignedShort": 1,
        "unsignedByte": 1,
        "positiveInteger": 1,
    }
    elements = tuple(
        SingleValuedDataElement(
            element_id=f"allowed-{kind}", value=value, value_data_type=f"xsd:{kind}"
        )
        for kind, value in type_values.items()
    )
    assert DataFormatValidator().validate(passport(*elements)).is_valid

    prohibited = (
        "ENTITIES",
        "IDREFS",
        "NMTOKENS",
        "normalizedString",
        "token",
        "language",
        "NMTOKEN",
        "Name",
        "NCName",
        "ID",
        "IDREF",
        "ENTITY",
        "NOTATION",
        "QName",
    )
    rejected = tuple(
        SingleValuedDataElement(
            element_id=f"prohibited-{kind}", value="opaque", value_data_type=f"xsd:{kind}"
        )
        for kind in prohibited
    )
    assert len(DataFormatValidator().validate(passport(*rejected)).issues) == len(prohibited)
    assert normalized(
        DataFormatValidator().validate(
            passport(
                SingleValuedDataElement(
                    element_id="min", value=255, value_data_type="xsd:unsignedByte"
                ),
                SingleValuedDataElement(
                    element_id="over", value=256, value_data_type="xsd:unsignedByte"
                ),
            )
        )
    ) == [("EN18223_VALUE_MATCHES_DATATYPE", "elements[1].value", "ERROR")]


def test_multivalue_declared_datatypes_conflict_and_untyped_siblings_must_match() -> None:
    conflict = MultiValuedDataElement(
        element_id="declared",
        value_data_type="xsd:string",
        value=(
            SingleValuedDataElement(element_id="child", value=1, value_data_type="xsd:integer"),
        ),
    )
    mismatch = MultiValuedDataElement(
        element_id="inferred",
        value=(
            SingleValuedDataElement(element_id="first", value=1, value_data_type="xsd:integer"),
            SingleValuedDataElement(element_id="second", value=1.0, value_data_type="xsd:double"),
        ),
    )
    assert normalized(DataFormatValidator().validate(passport(conflict, mismatch))) == [
        ("EN18223_MULTI_HOMOGENEOUS_DATATYPE", "elements[0].elements[0].valueDataType", "ERROR"),
        ("EN18223_MULTI_HOMOGENEOUS_DATATYPE", "elements[1].elements[1].valueDataType", "ERROR"),
    ]


def test_format_validation_resource_media_language_and_no_semantic_duplicates() -> None:
    resource = RelatedResource(
        element_id="r", url="relative", content_type="application/", language="en"
    )
    core = passport(
        resource,
        MultiLanguageDataElement(
            element_id="m", value=(MultiLanguageValue(value="name", language="zz-ZZ"),)
        ),
    )
    assert normalized(DataFormatValidator().validate(core)) == [
        ("EN18223_RELATED_RESOURCE_URL_RFC3986", "elements[0].url", "ERROR"),
        ("EN18223_RELATED_RESOURCE_CONTENT_TYPE_SYNTAX", "elements[0].contentType", "ERROR"),
        ("EN18223_RELATED_RESOURCE_LANGUAGE_TAG", "elements[0].language", "ERROR"),
        ("EN18223_MULTILANGUAGE_LANGUAGE_TAG", "elements[1].values[0].language", "ERROR"),
    ]
    assert (
        DataFormatValidator()
        .validate(passport(SingleValuedDataElement(element_id="missing")))
        .is_valid
    )
    assert DppValidator().validate(core).is_valid


def test_identifier_profiles_are_explicit_and_granularity_checked() -> None:
    context = IdentifierValidationContext(
        ProductIdentifierMethod.GS1_DIGITAL_LINK,
        EconomicOperatorIdentifierMethod.GS1_GLN,
    )
    valid = header(
        unique_product_identifier="https://id.gs1.org/01/09506000134352/10/LOT-1",
        granularity=Granularity.BATCH,
        economic_operator_id="4171234567890128",
    )
    assert IdentifierValidator().validate(valid, context).is_valid
    invalid = valid.with_updates(granularity=Granularity.MODEL)
    result = IdentifierValidator().validate(invalid, context)
    assert normalized(result) == [
        ("IDENTIFIER_GRANULARITY_MISMATCH", "header.granularity", "ERROR")
    ]
    bad_gtin = valid.with_updates(
        unique_product_identifier="https://id.gs1.org/01/09506000134353/10/LOT-1"
    )
    assert normalized(IdentifierValidator().validate(bad_gtin, context))[0] == (
        "GS1_DIGITAL_LINK_KEY_INVALID",
        "header.uniqueProductIdentifier",
        "ERROR",
    )


@pytest.mark.parametrize(
    ("operator", "facility", "method", "expected"),
    [
        ("4171234567890129", None, None, ("GS1_GLN_INVALID", "header.economicOperatorId")),
        ("4141234567890128", None, None, ("GS1_GLN_ROLE_MISMATCH", "header.economicOperatorId")),
        (
            "4171234567890128",
            "bad",
            FacilityIdentifierMethod.GS1_GLN,
            ("GS1_GLN_INVALID", "header.facilityId"),
        ),
        (
            "4171234567890128",
            "4171234567890128",
            FacilityIdentifierMethod.GS1_GLN,
            ("GS1_GLN_ROLE_MISMATCH", "header.facilityId"),
        ),
    ],
)
def test_gln_syntax_and_role_rule_family(
    operator: str,
    facility: str | None,
    method: FacilityIdentifierMethod | None,
    expected: tuple[str, str],
) -> None:
    value = header(
        unique_product_identifier="https://example.test/item/1",
        granularity=Granularity.ITEM,
        economic_operator_id=operator,
        facility_id=facility,
    )
    context = IdentifierValidationContext(
        ProductIdentifierMethod.IDENTIFICATION_LINK,
        EconomicOperatorIdentifierMethod.GS1_GLN,
        method,
    )
    result = IdentifierValidator().validate(value, context)
    assert normalized(result) == [(expected[0], expected[1], "ERROR")]


@pytest.mark.parametrize(
    ("identifier", "granularity", "expected_rule", "status"),
    [
        (
            "https://example.test/product?.1P",
            Granularity.MODEL,
            "IDENTIFICATION_LINK_STRUCTURED_SYNTAX_INVALID",
            ValidationStatus.INVALID,
        ),
        (
            "https://example.test/product?.1T=LOT",
            Granularity.BATCH,
            "IDENTIFICATION_LINK_REQUIRED_IDENTIFIER_MISSING",
            ValidationStatus.INVALID,
        ),
        (
            "https://example.test/product?.2Q=VALUE",
            Granularity.MODEL,
            "IDENTIFICATION_LINK_DI_UNSUPPORTED",
            ValidationStatus.UNSUPPORTED,
        ),
    ],
)
def test_identification_link_rule_families(
    identifier: str, granularity: Granularity, expected_rule: str, status: ValidationStatus
) -> None:
    value = header(
        unique_product_identifier=identifier,
        granularity=granularity,
        economic_operator_id="4171234567890128",
    )
    context = IdentifierValidationContext(
        ProductIdentifierMethod.IDENTIFICATION_LINK,
        EconomicOperatorIdentifierMethod.GS1_GLN,
    )
    result = IdentifierValidator().validate(value, context)
    assert normalized(result) == [(expected_rule, "header.uniqueProductIdentifier", "ERROR")]
    assert result.status is status


def test_identifier_unsupported_plus_invalid_is_invalid_and_warnings_do_not_fail() -> None:
    context = IdentifierValidationContext(
        ProductIdentifierMethod.UNSUPPORTED,
        EconomicOperatorIdentifierMethod.GS1_GLN,
    )
    mixed = IdentifierValidator().validate(header(economic_operator_id="bad"), context)
    assert mixed.status is ValidationStatus.INVALID
    warning_and_error = DppValidator().validate(
        passport(SingleValuedDataElement(element_id="e"), digital_product_passport_id="relative")
    )
    assert warning_and_error.status is ValidationStatus.INVALID
    assert normalized(warning_and_error) == [
        ("EN18223_HEADER_DPP_ID_URI_RECOMMENDED", "header.digitalProductPassportId", "WARNING"),
        ("EN18223_SINGLE_VALUE_REQUIRED", "elements[0].value", "ERROR"),
    ]


def test_identifier_api_missing_inputs_and_granularity_required() -> None:
    validator = IdentifierValidator()
    assert normalized(validator.validate(None, None)) == [
        ("IDENTIFIER_HEADER_REQUIRED", "header", "ERROR")
    ]
    assert normalized(validator.validate(header(), None)) == [
        ("IDENTIFIER_VALIDATION_CONTEXT_REQUIRED", "context", "ERROR")
    ]
    context = IdentifierValidationContext(
        ProductIdentifierMethod.GS1_DIGITAL_LINK, EconomicOperatorIdentifierMethod.GS1_GLN
    )
    missing_granularity = header(
        unique_product_identifier="https://example.test/01/09506000134352",
        granularity=None,
        economic_operator_id="4171234567890128",
    )
    result = validator.validate(missing_granularity, context)
    assert normalized(result) == [
        ("IDENTIFIER_GRANULARITY_REQUIRED", "header.granularity", "ERROR")
    ]


def test_identification_link_and_unsupported_profile_semantics() -> None:
    valid = header(
        unique_product_identifier="https://example.test/p?.P=MODEL&.T=LOT",
        granularity=Granularity.BATCH,
        economic_operator_id="4171234567890128",
    )
    context = IdentifierValidationContext(
        ProductIdentifierMethod.IDENTIFICATION_LINK,
        EconomicOperatorIdentifierMethod.GS1_GLN,
    )
    assert IdentifierValidator().validate(valid, context).is_valid
    unsupported = IdentifierValidationContext(
        ProductIdentifierMethod.UNSUPPORTED,
        EconomicOperatorIdentifierMethod.UNSUPPORTED,
    )
    result = IdentifierValidator().validate(valid, unsupported)
    assert result.status is ValidationStatus.UNSUPPORTED
    assert {issue.rule for issue in result.issues} == {"IDENTIFIER_METHOD_UNSUPPORTED"}


def test_identifier_facility_requires_explicit_profile_and_gln_role() -> None:
    valid = header(
        unique_product_identifier="https://example.test/item/one",
        granularity=Granularity.ITEM,
        economic_operator_id="4171234567890128",
        facility_id="41412345678909",
    )
    context = IdentifierValidationContext(
        ProductIdentifierMethod.IDENTIFICATION_LINK,
        EconomicOperatorIdentifierMethod.GS1_GLN,
    )
    result = IdentifierValidator().validate(valid, context)
    assert normalized(result) == [("IDENTIFIER_METHOD_UNSUPPORTED", "header.facilityId", "ERROR")]
    facility_context = IdentifierValidationContext(
        ProductIdentifierMethod.IDENTIFICATION_LINK,
        EconomicOperatorIdentifierMethod.GS1_GLN,
        FacilityIdentifierMethod.GS1_GLN,
    )
    assert not IdentifierValidator().validate(valid, facility_context).is_valid


@pytest.mark.parametrize(
    ("identifier", "granularity", "rule", "status"),
    [
        (
            "http://example.test/01/09506000134352",
            Granularity.MODEL,
            "GS1_DIGITAL_LINK_URL_INVALID",
            ValidationStatus.INVALID,
        ),
        (
            "https://example.test/01/09506000134353",
            Granularity.MODEL,
            "GS1_DIGITAL_LINK_KEY_INVALID",
            ValidationStatus.INVALID,
        ),
        (
            "https://example.test/8013/model",
            Granularity.MODEL,
            "GS1_DIGITAL_LINK_KEY_UNSUPPORTED",
            ValidationStatus.UNSUPPORTED,
        ),
        (
            "https://example.test/01/09506000134352/10/A/10/B",
            Granularity.BATCH,
            "GS1_DIGITAL_LINK_QUALIFIER_INVALID",
            ValidationStatus.INVALID,
        ),
        (
            "https://example.test/01/09506000134352?17=260101",
            Granularity.MODEL,
            "GS1_DIGITAL_LINK_QUERY_UNSUPPORTED",
            ValidationStatus.UNSUPPORTED,
        ),
    ],
)
def test_gs1_identifier_profile_java_rule_samples(
    identifier: str, granularity: Granularity, rule: str, status: ValidationStatus
) -> None:
    value = header(
        unique_product_identifier=identifier,
        granularity=granularity,
        economic_operator_id="4171234567890128",
    )
    context = IdentifierValidationContext(
        ProductIdentifierMethod.GS1_DIGITAL_LINK, EconomicOperatorIdentifierMethod.GS1_GLN
    )
    result = IdentifierValidator().validate(value, context)
    assert result.status is status
    assert result.issues[0].rule == rule


def test_gs1_xchar_encoding_and_identification_link_boundaries() -> None:
    context = IdentifierValidationContext(
        ProductIdentifierMethod.GS1_DIGITAL_LINK, EconomicOperatorIdentifierMethod.GS1_GLN
    )
    for qualifier in ("LOT%2F1",):
        value = header(
            unique_product_identifier=f"https://example.test/01/09506000134352/10/{qualifier}",
            granularity=Granularity.BATCH,
            economic_operator_id="4171234567890128",
        )
        assert IdentifierValidator().validate(value, context).is_valid
    for qualifier in ("LOT%41", "LOT&1"):
        value = header(
            unique_product_identifier=f"https://example.test/01/09506000134352/10/{qualifier}",
            granularity=Granularity.BATCH,
            economic_operator_id="4171234567890128",
        )
        assert (
            IdentifierValidator().validate(value, context).issues[0].rule
            == "GS1_DIGITAL_LINK_QUALIFIER_INVALID"
        )

    identification = IdentifierValidationContext(
        ProductIdentifierMethod.IDENTIFICATION_LINK, EconomicOperatorIdentifierMethod.GS1_GLN
    )
    for text in ("example.test:8443/item/one", "www.example.test/item/one"):
        value = header(
            unique_product_identifier=text,
            granularity=Granularity.ITEM,
            economic_operator_id="4171234567890128",
        )
        assert IdentifierValidator().validate(value, identification).is_valid
    for text in ("https://xn--name.test/item", "not a url", "https://example.test/item%2Fpart"):
        value = header(
            unique_product_identifier=text,
            granularity=Granularity.ITEM,
            economic_operator_id="4171234567890128",
        )
        assert (
            IdentifierValidator().validate(value, identification).issues[0].rule
            == "IDENTIFICATION_LINK_URL_INVALID"
        )


def test_identifier_profiles_keep_operator_and_facility_roles_distinct() -> None:
    value = header(
        unique_product_identifier="https://example.test/item/one",
        granularity=Granularity.ITEM,
        economic_operator_id="4141234567890128",
        facility_id="4171234567890128",
    )
    context = IdentifierValidationContext(
        ProductIdentifierMethod.IDENTIFICATION_LINK,
        EconomicOperatorIdentifierMethod.GS1_GLN,
        FacilityIdentifierMethod.GS1_GLN,
    )
    result = IdentifierValidator().validate(value, context)
    assert normalized(result) == [
        ("GS1_GLN_ROLE_MISMATCH", "header.economicOperatorId", "ERROR"),
        ("GS1_GLN_ROLE_MISMATCH", "header.facilityId", "ERROR"),
    ]
