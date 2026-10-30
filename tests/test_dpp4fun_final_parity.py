from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from dpp_sdk.core import (
    DataElementCollection,
    DigitalProductPassport,
    DppHeader,
    Granularity,
    MultiValuedDataElement,
    SemanticPath,
    SingleValuedDataElement,
    ValidationSeverity,
)
from dpp_sdk.dpp4fun import (
    DPP4FUN_PROFILE,
    BillOfMaterials,
    CarbonFootprint,
    ChairCharacteristics,
    CribCharacteristics,
    Dpp4Fun,
    Dpp4FunJsonCodec,
    Durability,
    EnvironmentalImpact,
    FabricCharacteristics,
    HealthImpact,
    LockerCharacteristics,
    Nameplate,
    ParticleBoardCharacteristics,
    ProductRelationship,
    Recyclability,
    Refurbishment,
    Reliability,
    Remanufacturing,
    Repairability,
    Reusability,
    RightOfEndUsers,
    Safety,
    SofaCharacteristics,
    Traceability,
    Upgradability,
    Usage,
    WasteManagement,
)
from dpp_sdk.dpp4fun.profile import Dpp4FunSemanticResolver
from dpp_sdk.dpp4fun.validation import validate_dpp4fun


def _single(
    element_id: str, value: object, datatype: str = "xsd:string"
) -> SingleValuedDataElement:
    return SingleValuedDataElement(
        element_id=element_id,
        object_type="SingleValuedDataElement",
        value_data_type=datatype,
        value=value,
    )


def _passport(*elements, specs: tuple[str, ...] = ("DPP4FUN_COMMON_V1",)) -> Dpp4Fun:
    header = DppHeader(
        digital_product_passport_id="urn:example:dpp:1",
        unique_product_identifier="urn:example:product:1",
        granularity=Granularity.MODEL,
        dpp_schema_version="1.0",
        dpp_status="active",
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
        economic_operator_id="urn:example:operator:1",
        content_specification_ids=specs,
    )
    return Dpp4Fun.from_passport(
        DigitalProductPassport(dpp_header=header, data_elements=tuple(elements))
    )


def _issues(value: Dpp4Fun) -> list[tuple[str, str, str]]:
    return [(item.rule, item.path, item.severity.value) for item in validate_dpp4fun(value).issues]


def _profile_issues(value: Dpp4Fun) -> list[tuple[str, str, str]]:
    from dpp_sdk.dpp4fun import Dpp4FunValidator

    return [
        (item.rule, item.path, item.severity.value)
        for item in Dpp4FunValidator().validate(value).issues
    ]


def _aspect(root_id: str, *children, specs=("DPP4FUN_COMMON_V1",)) -> Dpp4Fun:
    return _passport(
        DataElementCollection(
            element_id=root_id, object_type="DataElementCollection", elements=children
        ),
        specs=specs,
    )


def test_dpp4fun_codec_full_compressed_full_uses_profile_resolver() -> None:
    codec = Dpp4FunJsonCodec()
    aspect = DPP4FUN_PROFILE
    # Nameplate has source-backed multilingual fields and ordered children.
    value = Dpp4Fun.create(
        DppHeader(
            digital_product_passport_id="urn:example:dpp:1",
            unique_product_identifier="urn:example:product:1",
            granularity=Granularity.MODEL,
            dpp_schema_version="1.0",
            dpp_status="active",
            last_updated=datetime(2026, 1, 1, tzinfo=UTC),
            economic_operator_id="urn:example:operator:1",
        ),
        Nameplate.create(
            manufacturerProductDesignation={"en": "Chair"}, manufacturerName="Example"
        ),
    )
    full = codec.to_expanded_json(value)
    compressed = codec.to_compressed_json(value)
    restored = codec.from_compressed_json(compressed)
    assert codec.from_expanded_json(full).passport == value.passport
    assert restored.passport == value.passport
    assert json.loads(codec.to_expanded_json(restored)) == json.loads(full)
    assert aspect.metadata["profileVersion"] == "1.0.0"


@pytest.mark.parametrize(
    "variant_type",
    [
        ChairCharacteristics,
        CribCharacteristics,
        FabricCharacteristics,
        LockerCharacteristics,
        ParticleBoardCharacteristics,
        SofaCharacteristics,
    ],
)
def test_full_compressed_full_round_trip_for_each_characteristics_variant(variant_type) -> None:
    codec = Dpp4FunJsonCodec()
    applicability = f"characteristics-{variant_type.variant.value}"
    definition = next(
        item
        for item in DPP4FUN_PROFILE.definitions
        if item.path.startswith("characteristics.")
        and item.path.count(".") == 1
        and applicability in item.applies_to
        and item.object_type == "SingleValuedDataElement"
    )
    scalar = {
        "xsd:string": "sample",
        "xsd:anyURI": "https://example.org/value",
        "xsd:dateTime": "2026-01-01T00:00:00Z",
        "xsd:boolean": False,
        "xsd:integer": 1,
        "xsd:double": 1.0,
        "xsd:decimal": 1.0,
    }[definition.value_data_type]
    value = Dpp4Fun.create(
        _passport().header, variant_type.create(**{definition.element_id: scalar})
    )
    restored = codec.from_compressed_json(codec.to_compressed_json(value))
    assert restored.passport == value.passport


def test_full_compressed_full_round_trip_preserves_decimal_json_semantics() -> None:
    codec = Dpp4FunJsonCodec()
    value = Dpp4Fun.create(_passport().header, ChairCharacteristics.create(height=0.1))
    restored = codec.from_compressed_json(codec.to_compressed_json(value))

    # Core parsing retains decimal JSON numbers exactly; the DPP4Fun typed constructor uses float.
    assert json.loads(codec.to_expanded_json(restored)) == json.loads(codec.to_expanded_json(value))
    assert restored.passport == value.passport


def test_compressed_unknown_extension_does_not_gain_fabricated_semantics() -> None:
    extension = SingleValuedDataElement(
        element_id="vendorField",
        object_type="SingleValuedDataElement",
        dictionary_reference="urn:vendor:term",
        value_data_type="xsd:string",
        value="present",
    )
    value = _passport(extension)
    codec = Dpp4FunJsonCodec()
    expansion = codec.expand_compressed_json(codec.to_compressed_json(value))
    restored = expansion.passport.data_elements[0]
    assert isinstance(restored, SingleValuedDataElement)
    assert restored.dictionary_reference is None
    assert restored.value_data_type is None
    assert expansion.issues[0].rule == "EN18223_COMPRESSED_SEMANTICS_UNRESOLVED"


def test_profile_resolver_returns_only_selected_authoritative_definition() -> None:
    resolver = Dpp4FunSemanticResolver()
    selected = resolver.resolve(
        ("DPP4FUN_COMMON_V1",), SemanticPath.of("nameplate", "manufacturerName")
    )
    assert selected is not None and selected.element_id == "manufacturerName"
    assert resolver.resolve(("UNKNOWN",), SemanticPath.of("nameplate", "manufacturerName")) is None


@pytest.mark.parametrize(
    ("content_ids", "expected_rule"),
    [
        (("DPP4FUN_COMMON_V1", "UNKNOWN"), "DPP4FUN_CONTENT_SPEC_SUPPORTED"),
    ],
)
def test_content_profile_issues_are_ordered_and_stable(
    content_ids: tuple[str, ...], expected_rule: str
) -> None:
    result = validate_dpp4fun(_passport(specs=content_ids))
    assert any(
        issue.rule == expected_rule and issue.severity is ValidationSeverity.ERROR
        for issue in result.issues
    )


def test_aggregate_rejects_multiple_characteristics_content_profiles() -> None:
    with pytest.raises(ValueError, match="only one Characteristics variant"):
        _passport(specs=("DPP4FUN_COMMON_V1", "DPP4FUN_CHAIR_V1", "DPP4FUN_SOFA_V1"))
    malformed = Dpp4Fun(
        passport=DigitalProductPassport(
            dpp_header=_passport().header.with_updates(
                content_specification_ids=(
                    "DPP4FUN_COMMON_V1",
                    "DPP4FUN_CHAIR_V1",
                    "DPP4FUN_SOFA_V1",
                )
            )
        )
    )
    assert any(
        rule == "DPP4FUN_CHARACTERISTICS_VARIANT_SINGLE"
        for rule, _, _ in _profile_issues(malformed)
    )


@pytest.mark.parametrize(
    ("record_id", "children", "expected"),
    [
        (
            "repairRecordSet",
            (
                _single("name", "repair"),
                _single("description", "fixed"),
                _single("operator", "shop"),
                _single("time", "2026-01-01T00:00:00Z"),
            ),
            [],
        ),
        (
            "designRecordSet",
            (
                _single("name", "release"),
                _single("description", "released"),
                _single("operator", "team"),
                _single("time", "2026-01-01T00:00:00Z"),
            ),
            [("DPP4FUN_RECORD_STATUS_REQUIRED", "traceability.designRecordSet[0].status", "ERROR")],
        ),
    ],
)
def test_record_minimums_preserve_repair_status_exception(record_id, children, expected) -> None:
    root_id = "repairability" if record_id == "repairRecordSet" else "traceability"
    records = MultiValuedDataElement(
        element_id=record_id,
        object_type="MultiValuedDataElement",
        value=(
            DataElementCollection(
                element_id=f"{record_id[:-3]}_00",
                object_type="DataElementCollection",
                elements=children,
            ),
        ),
    )
    value = _passport(
        DataElementCollection(
            element_id=root_id, object_type="DataElementCollection", elements=(records,)
        )
    )
    assert [item for item in _issues(value) if item[0].startswith("DPP4FUN_RECORD_")] == expected


def test_unknown_extensions_are_retained_and_do_not_receive_guessed_profile_rules() -> None:
    extension = _single("documentation", "custom")
    value = _passport(extension)
    result = validate_dpp4fun(value)
    assert result.is_valid
    assert value.passport.data_elements == (extension,)


@pytest.mark.parametrize(
    "aspect_type",
    [
        Nameplate,
        HealthImpact,
        EnvironmentalImpact,
        Durability,
        CarbonFootprint,
        BillOfMaterials,
        Refurbishment,
        Recyclability,
        ProductRelationship,
        Remanufacturing,
        Reliability,
        Repairability,
        Reusability,
        WasteManagement,
        Usage,
        Upgradability,
        Traceability,
        Safety,
        RightOfEndUsers,
    ],
)
def test_each_general_aspect_uses_its_catalog_binding(aspect_type) -> None:
    value = Dpp4Fun.create(_passport().header, aspect_type.create())
    assert any(rule == "DPP4FUN_EXPLICIT_CARDINALITY" for rule, _, _ in _profile_issues(value))


@pytest.mark.parametrize(
    "variant_type",
    [
        ChairCharacteristics,
        CribCharacteristics,
        FabricCharacteristics,
        LockerCharacteristics,
        ParticleBoardCharacteristics,
        SofaCharacteristics,
    ],
)
def test_each_characteristics_variant_uses_its_selected_profile(variant_type) -> None:
    value = Dpp4Fun.create(_passport().header, variant_type.create())
    assert any(rule == "DPP4FUN_EXPLICIT_CARDINALITY" for rule, _, _ in _profile_issues(value))


@pytest.mark.parametrize(
    ("present", "expected"),
    [
        ({"description", "reference"}, "DPP4FUN_INSTRUCTION_NAME_REQUIRED"),
        ({"name", "reference"}, "DPP4FUN_INSTRUCTION_DESCRIPTION_REQUIRED"),
        ({"name", "description"}, "DPP4FUN_INSTRUCTION_REFERENCE_REQUIRED"),
    ],
)
def test_instruction_minimum_fields(present, expected) -> None:
    item = DataElementCollection(
        element_id="repairInstruction_00",
        object_type="DataElementCollection",
        elements=tuple(
            _single(key, "https://example.org/x" if key == "reference" else key)
            for key in ("name", "description", "reference")
            if key in present
        ),
    )
    value = _aspect(
        "repairability",
        MultiValuedDataElement(
            element_id="repairInstructionSet", object_type="MultiValuedDataElement", value=(item,)
        ),
    )
    assert any(rule == expected for rule, _, _ in _profile_issues(value))


@pytest.mark.parametrize(
    ("present", "expected"),
    [
        ({"description"}, "DPP4FUN_ASSESSMENT_NAME_REQUIRED"),
        ({"name"}, "DPP4FUN_ASSESSMENT_DESCRIPTION_REQUIRED"),
    ],
)
def test_assessment_minimum_fields(present, expected) -> None:
    item = DataElementCollection(
        element_id="scoring_00",
        object_type="DataElementCollection",
        elements=tuple(_single(key, key) for key in ("name", "description") if key in present),
    )
    value = _aspect(
        "durability",
        MultiValuedDataElement(
            element_id="scoringSet", object_type="MultiValuedDataElement", value=(item,)
        ),
    )
    assert any(rule == expected for rule, _, _ in _profile_issues(value))


def test_semantic_binding_uri_unit_surface_and_professional_use_rules() -> None:
    bad_gtin = SingleValuedDataElement(
        element_id="gtinCode",
        object_type="SingleValuedDataElement",
        dictionary_reference="urn:wrong:dictionary",
        value_data_type="xsd:integer",
        value=42,
    )
    issues = _profile_issues(_aspect("nameplate", bad_gtin))
    assert {rule for rule, _, _ in issues} >= {
        "DPP4FUN_RESERVED_PATH_DICTIONARY_REFERENCE",
        "DPP4FUN_RESERVED_PATH_VALUE_DATATYPE",
        "DPP4FUN_BINDING_DATATYPE_MISMATCH",
    }

    material = DataElementCollection(
        element_id="material_wrong",
        object_type="DataElementCollection",
        elements=(_single("reference", "bad uri", "xsd:anyURI"),),
    )
    bom = DataElementCollection(
        element_id="billOfMaterials",
        object_type="DataElementCollection",
        elements=(
            MultiValuedDataElement(
                element_id="materialSet",
                object_type="MultiValuedDataElement",
                value_data_type="xsd:string",
                value=(material,),
            ),
        ),
    )
    assert bom.elements[0].element_id == "materialSet"
    assert len(bom.elements[0].value) == 1
    issues = _profile_issues(_passport(bom))
    assert {rule for rule, _, _ in issues} >= {
        "DPP4FUN_LIST_ITEM_ID_CANONICAL",
        "DPP4FUN_URI_FIELD_RFC3986",
        "DPP4FUN_RESERVED_PATH_VALUE_DATATYPE",
    }, issues

    safety = _aspect("safety", _single("professionalUseOnly", "yes"))
    assert any(
        rule == "DPP4FUN_BINDING_DATATYPE_MISMATCH" for rule, _, _ in _profile_issues(safety)
    )
    boolean_safety = Dpp4Fun.create(_passport().header, Safety.create(professionalUseOnly=True))
    assert not any(
        rule == "DPP4FUN_BINDING_DATATYPE_MISMATCH"
        for rule, _, _ in _profile_issues(boolean_safety)
    )

    specs = ("DPP4FUN_COMMON_V1", "DPP4FUN_CHAIR_V1")
    chair = _aspect("characteristics", _single("lengthUnit", "kg"), specs=specs)
    assert any(rule == "DPP4FUN_UNIT_DIMENSION_MISMATCH" for rule, _, _ in _profile_issues(chair))
    surface = _aspect("characteristics", _single("surface", 1.5, "xsd:double"), specs=specs)
    assert surface.passport.data_elements[0].elements[0].value == 1.5
    assert {rule for rule, _, _ in _profile_issues(surface)} >= {
        "DPP4FUN_RESERVED_PATH_VALUE_DATATYPE",
        "DPP4FUN_BINDING_DATATYPE_MISMATCH",
    }


def test_carbon_calculation_is_not_given_assessment_minima() -> None:
    calculation = DataElementCollection(
        element_id="carbonFootprintCalculation_00",
        object_type="DataElementCollection",
        elements=(_single("phase", "manufacturing"),),
    )
    value = _aspect(
        "carbonFootprint",
        MultiValuedDataElement(
            element_id="carbonFootprintCalculationSet",
            object_type="MultiValuedDataElement",
            value=(calculation,),
        ),
    )
    assert not any(rule.startswith("DPP4FUN_ASSESSMENT_") for rule, _, _ in _profile_issues(value))
