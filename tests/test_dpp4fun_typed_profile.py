from __future__ import annotations

import pytest

from dpp_sdk.core.model import (
    DataElementCollection,
    DigitalProductPassport,
    DppHeader,
    Granularity,
    SingleValuedDataElement,
)
from dpp_sdk.dpp4fun import composites
from dpp_sdk.dpp4fun.characteristics import (
    ChairCharacteristics,
    CribCharacteristics,
    FabricCharacteristics,
    LockerCharacteristics,
    ParticleBoardCharacteristics,
    SofaCharacteristics,
)
from dpp_sdk.dpp4fun.profile import DPP4FUN_PROFILE, profile_definition
from dpp_sdk.dpp4fun.typed_model import BillOfMaterials, Dpp4Fun, Nameplate
from dpp_sdk.dpp4fun.units import Dpp4FunQuantity, LengthUnit, MassUnit


def test_packaged_profile_retains_its_complete_definition_set() -> None:
    assert len(DPP4FUN_PROFILE.definitions) == 488
    assert (
        profile_definition("billOfMaterials.materialSet[*]").repeated_item_policy[
            "elementIdPattern"
        ]
        == "material_%02d"
    )


@pytest.mark.parametrize(
    ("aspect_type", "element_id"),
    [
        (cls, aspect_id)
        for cls, aspect_id in [
            # All general aspects in the Java profile root order.
            ("Nameplate", "nameplate"),
            ("HealthImpact", "healthImpact"),
            ("EnvironmentalImpact", "environmentalImpact"),
            ("Durability", "durability"),
            ("CarbonFootprint", "carbonFootprint"),
            ("BillOfMaterials", "billOfMaterials"),
            ("Refurbishment", "refurbishment"),
            ("Recyclability", "recyclability"),
            ("ProductRelationship", "productRelationship"),
            ("Remanufacturing", "remanufacturing"),
            ("Reliability", "reliability"),
            ("Repairability", "repairability"),
            ("Reusability", "reusability"),
            ("WasteManagement", "wasteManagement"),
            ("Usage", "usage"),
            ("Upgradability", "upgradability"),
            ("Traceability", "traceability"),
            ("Safety", "safety"),
            ("RightOfEndUsers", "rightOfEndUsers"),
        ]
    ],
)
def test_all_general_aspect_types_construct_profiled_empty_collections(
    aspect_type: str, element_id: str
) -> None:
    from dpp_sdk.dpp4fun import typed_model as model

    aspect_class = getattr(model, aspect_type)
    aspect = aspect_class.create()
    assert aspect.element.element_id == element_id
    assert aspect.element.object_type == "DataElementCollection"
    assert (
        aspect.element.dictionary_reference == profile_definition(element_id).dictionary_reference
    )


@pytest.mark.parametrize(
    ("variant_type", "variant"),
    [
        (ChairCharacteristics, "chair"),
        (CribCharacteristics, "crib"),
        (FabricCharacteristics, "fabric"),
        (LockerCharacteristics, "locker"),
        (ParticleBoardCharacteristics, "particleBoard"),
        (SofaCharacteristics, "sofa"),
    ],
)
def test_characteristics_variants_build_typed_semantic_values(variant_type, variant) -> None:
    aspect = variant_type.create()
    assert aspect.variant.value == variant
    with_value = aspect.with_field("color", "oak")
    color = next(e for e in with_value.element.elements if e.element_id == "color")
    assert isinstance(color, SingleValuedDataElement)
    assert color.value_data_type == "xsd:string"
    assert (
        color.dictionary_reference
        == profile_definition("characteristics.color", variant=variant).dictionary_reference
    )
    with pytest.raises(TypeError):
        aspect.with_field("color", 12)


@pytest.mark.parametrize(
    ("variant_type", "field", "value", "datatype"),
    [
        (ChairCharacteristics, "seatingCapacity", 2, "xsd:integer"),
        (CribCharacteristics, "mattressIncluded", True, "xsd:boolean"),
        (FabricCharacteristics, "flameRetardant", True, "xsd:boolean"),
        (LockerCharacteristics, "lockIncluded", True, "xsd:boolean"),
        (ParticleBoardCharacteristics, "carb2Epa", True, "xsd:boolean"),
        (SofaCharacteristics, "headrestIncluded", True, "xsd:boolean"),
    ],
)
def test_all_characteristics_variants_keep_java_public_field_types(
    variant_type, field: str, value: object, datatype: str
) -> None:
    aspect = variant_type.create(**{field: value})
    child = aspect.element.elements[0]
    expected_name = "matelasIncluded" if field == "mattressIncluded" else field
    assert child.element_id == expected_name
    assert child.value_data_type == datatype
    assert child.value is value


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
def test_surface_preserves_published_descriptive_string(variant_type) -> None:
    aspect = variant_type.create(surface="Small-structured chenille fabric")
    surface = aspect.field("surface")
    assert isinstance(surface, SingleValuedDataElement)
    assert surface.value == "Small-structured chenille fabric"
    assert isinstance(surface.value, str)
    assert surface.value_data_type == "xsd:string"


@pytest.mark.parametrize(
    "value",
    [
        1,
        1.25,
        True,
    ],
)
@pytest.mark.parametrize("variant_type", [ChairCharacteristics, SofaCharacteristics])
def test_surface_requires_descriptive_string_input(variant_type, value: object) -> None:
    with pytest.raises(TypeError, match="characteristics.surface requires a string"):
        variant_type.create(surface=value)


def test_surface_numeric_looking_string_is_preserved_without_conversion() -> None:
    surface = ChairCharacteristics.create(surface="1.25").field("surface")
    assert isinstance(surface, SingleValuedDataElement)
    assert surface.value == "1.25"
    assert surface.value_data_type == "xsd:string"


def test_surface_data_element_input_is_not_coerced() -> None:
    source = SingleValuedDataElement(
        element_id="surface",
        object_type="SingleValuedDataElement",
        value="Woven matte",
        value_data_type="xsd:string",
    )
    aspect = ChairCharacteristics.create(surface=source)
    surface = aspect.field("surface")
    assert isinstance(surface, SingleValuedDataElement)
    assert surface.value == "Woven matte"
    assert surface.value_data_type == "xsd:string"
    assert source.value == "Woven matte"
    assert source.value_data_type == "xsd:string"


def test_dpp4fun_has_one_canonical_passport_and_preserves_unknowns_on_edit() -> None:
    header = DppHeader(
        digital_product_passport_id="urn:example:passport:1",
        unique_product_identifier="urn:example:product:1",
        granularity=Granularity.MODEL,
    )
    unknown = DataElementCollection(element_id="extension", object_type="DataElementCollection")
    original = Dpp4Fun.create(
        header, Nameplate.create(gtinCode="00012345678905"), extensions=(unknown,)
    )
    updated = original.with_updates(header=header.with_updates(dpp_status="active"))
    assert original.as_digital_product_passport().data_elements[-1] == unknown
    assert updated.as_digital_product_passport().data_elements[-1] == unknown
    assert updated.as_digital_product_passport().dpp_header.dpp_status == "active"
    assert updated.header.dpp_schema_version == "1.0"
    assert updated.header.last_updated is not None
    assert updated.as_digital_product_passport() is not original.as_digital_product_passport()
    assert set(Dpp4Fun.model_fields) == {"passport"}


def test_dpp4fun_edit_rejects_duplicate_aspect_ids_without_dropping_an_update() -> None:
    header = DppHeader(
        digital_product_passport_id="urn:example:passport:duplicate",
        unique_product_identifier="urn:example:product:duplicate",
        granularity=Granularity.MODEL,
    )
    original = Dpp4Fun.create(header, Nameplate.create(brand="Cir4Fun"))
    with pytest.raises(ValueError, match="unique element IDs"):
        original.with_updates(
            aspects=(Nameplate.create(brand="First"), Nameplate.create(brand="Second"))
        )


def test_profile_field_order_and_variant_access_follow_the_catalog() -> None:
    nameplate = Nameplate.create(brand="Cir4Fun", gtinCode="04012345678901")
    expected = [
        definition.element_id
        for definition in DPP4FUN_PROFILE.definitions
        if definition.path.rpartition(".")[0] == "nameplate"
        and definition.element_id in {"brand", "gtinCode"}
    ]
    assert [field.element_id for field in nameplate.element.elements] == expected
    header = DppHeader(
        digital_product_passport_id="urn:example:passport:3",
        unique_product_identifier="urn:example:product:3",
        granularity=Granularity.MODEL,
    )
    dpp = Dpp4Fun.create(header, ChairCharacteristics.create(color="blue"))
    assert isinstance(dpp.selected_characteristics(), ChairCharacteristics)


def test_aspect_edits_preserve_unknown_children_without_adding_metadata() -> None:
    original = Nameplate.create(brand="Cir4Fun")
    extension = SingleValuedDataElement(
        element_id="vendorCode", object_type="SingleValuedDataElement", value="X-1"
    )
    source = original.element.with_updates(elements=(*original.element.elements, extension))
    edited = Nameplate.from_element(source).with_field("brand", "Example")
    assert edited.field("brand").value == "Example"
    assert (
        next(child for child in edited.element.elements if child.element_id == "vendorCode")
        == extension
    )
    assert extension.dictionary_reference is None


def test_quantity_pairs_numeric_value_with_dimension_checked_unit() -> None:
    length = Dpp4FunQuantity(value=1.25, unit=LengthUnit.METER)
    assert length.value == 1.25
    assert length.unit.symbol == "m"
    with pytest.raises(ValueError):
        Dpp4FunQuantity(value=1, unit=MassUnit.KILOGRAM, dimension="length")


def test_characteristic_quantities_use_profile_unit_slots_and_dimensions() -> None:
    chair = ChairCharacteristics.create().with_quantity(
        "height", Dpp4FunQuantity(value=80.0, unit=LengthUnit.CENTIMETER)
    )
    assert chair.quantity("height") == Dpp4FunQuantity(value=80.0, unit=LengthUnit.CENTIMETER)
    with pytest.raises(ValueError, match="DPP4FUN_UNIT_DIMENSION_MISMATCH"):
        chair.with_quantity("weight", Dpp4FunQuantity(value=5.0, unit=LengthUnit.METER))
    with pytest.raises(ValueError, match="DPP4FUN_UNIT_SLOT_CONFLICT"):
        chair.with_quantity("seatHeight", Dpp4FunQuantity(value=45.0, unit=LengthUnit.METER))


def test_aggregate_rejects_multiple_selected_characteristics_variants() -> None:
    header = DppHeader(
        digital_product_passport_id="urn:example:passport:2",
        unique_product_identifier="urn:example:product:2",
        granularity=Granularity.MODEL,
        content_specification_ids=("DPP4FUN_CHAIR_V1", "DPP4FUN_SOFA_V1"),
    )
    with pytest.raises(ValueError, match="only one Characteristics variant"):
        Dpp4Fun.from_passport(DigitalProductPassport(dpp_header=header))


@pytest.mark.parametrize(
    "composite_name",
    [
        "Accessory",
        "Address",
        "CollectionMember",
        "Certificate",
        "CarbonFootprintCalculation",
        "DesignRecord",
        "Contact",
        "Email",
        "HealthIndicator",
        "Component",
        "ManufacturingRecord",
        "Instruction",
        "Indicator",
        "Part",
        "Material",
        "Policies",
        "PostSaleService",
        "ProductFunction",
        "TrackingRecord",
        "Telephone",
        "StandardAssessment",
        "RepairRecord",
        "Scoring",
    ],
)
def test_all_java_reusable_composite_views_preserve_core_element(composite_name: str) -> None:
    composite_type = getattr(composites, composite_name)
    created = composite_type.create()
    assert created.element.object_type == "DataElementCollection"
    element = DataElementCollection(
        element_id=created.element.element_id, object_type="DataElementCollection"
    )
    composite = composite_type.from_element(element)
    assert composite.as_data_element() is element


def test_material_composite_uses_profile_datatypes_and_dictionary_metadata() -> None:
    material = composites.Material.create(name="Oak", portion=0.75, mandatory=True)
    assert material.element.element_id == "material"
    values = {item.element_id: item for item in material.element.elements}
    assert values["name"].value_data_type == "xsd:string"
    assert values["portion"].value_data_type == "xsd:double"
    assert values["name"].dictionary_reference == "https://schema.org/name"


@pytest.mark.parametrize(
    ("composite_name", "fields"),
    [
        ("Address", {"country": "DE", "town": "Berlin"}),
        (
            "Contact",
            {
                "organization": "Support",
                "address": composites.Address.create(country="DE", town="Berlin").element,
            },
        ),
        ("Email", {"emailAddress": "help@example.test"}),
        ("Telephone", {"telephoneNumber": "+4930123"}),
        ("Component", {"name": "Frame", "mandatory": False}),
        ("Part", {"name": "Leg", "mandatory": True}),
        ("Certificate", {"name": "EN test", "issueDate": "2026-01-01T00:00:00Z"}),
        ("HealthIndicator", {"name": "Formaldehyde", "value": "low"}),
        ("Instruction", {"name": "Assembly", "targetAudience": "professional"}),
        ("ProductFunction", {"name": "seating", "status": "primary"}),
        ("StandardAssessment", {"name": "EN test", "complianceStatus": "compliant"}),
        ("Policies", {"permissions": ["repair", "reuse"]}),
    ],
)
def test_reusable_composites_construct_profile_typed_fields(
    composite_name: str, fields: dict[str, object]
) -> None:
    composite = getattr(composites, composite_name).create(**fields)
    expected = [
        profile_definition(
            f"{composite.profile_path}.{composite.field_aliases.get(name, name)}"
        ).element_id
        for name in fields
    ]
    assert [element.element_id for element in composite.element.elements] == expected


def test_composite_field_edits_are_immutable_and_keep_sibling_values() -> None:
    original = composites.Material.create(name="Oak", portion=0.75)
    updated = original.with_field("name", "Beech")
    assert original.field("name").value == "Oak"
    assert updated.field("name").value == "Beech"
    assert updated.field("portion").value == 0.75


def test_repeated_composite_item_ids_and_input_order_follow_profile() -> None:
    first = composites.Material.create(name="Oak")
    second = composites.Material.create(name="Beech")
    aspect = BillOfMaterials.create(materialSet=(first.element, second.element))
    repeated = next(item for item in aspect.element.elements if item.element_id == "materialSet")
    assert [item.element_id for item in repeated.value] == ["material_00", "material_01"]
    assert [item.elements[0].value for item in repeated.value] == ["Oak", "Beech"]


def test_surface_profile_matches_corrected_java_binding_metadata() -> None:
    assert DPP4FUN_PROFILE.metadata["sources"]["d4Version"] == "1.0"
    conflicts = {item["id"]: item for item in DPP4FUN_PROFILE.conflicts}
    assert {
        "CHARACTERISTICS_SURFACE",
        "CHARACTERISTICS_SURFACE_DICTIONARY",
    } <= conflicts.keys()
    assert conflicts["CHARACTERISTICS_SURFACE"]["status"] == "RESOLVED_WITH_SOURCE_CONFLICT"
    assert "published AAS String binding" in conflicts["CHARACTERISTICS_SURFACE"]["note"]
    assert (
        "Do not add a SurfaceArea field or semantic IRI"
        in conflicts["CHARACTERISTICS_SURFACE_DICTIONARY"]["note"]
    )
    aas_templates = {
        "chair": "CIR4FUN.ChairCharacteristics.json",
        "crib": "CIR4FUN.CribCharacteristics.json",
        "fabric": "CIR4FUN.FabricCharacteristics.json",
        "locker": "CIR4FUN.LockerCharacteristics.json",
        "particleBoard": "CIR4FUN.ParticleBoardCharacteristics.json",
        "sofa": "CIR4FUN.SofaCharacteristics.json",
    }
    for variant, template in aas_templates.items():
        surface = profile_definition("characteristics.surface", variant=variant)
        assert surface.value_data_type == "xsd:string"
        assert surface.dictionary_reference is None
        assert surface.source["aasValueType"] == "xs:string"
        assert surface.source["dpp4funCommit"] == "2007a574b0e35eae5997c9460bf4cf531588405b"
        assert surface.source_references[0]["aasTemplate"] == template
        assert surface.resolution_status == "RESOLVED_WITHOUT_DICTIONARY_REFERENCE"
        assert surface.conflict_resolution is not None
        assert "published AAS" in surface.conflict_resolution["note"]
    assert profile_definition("safety.professionalUseOnly").value_data_type == "xsd:boolean"
    for path in (
        "durability.standardSet[*].complianceStatus",
        "recyclability.standardSet[*].complianceStatus",
        "reliability.standardSet[*].complianceStatus",
        "safety.standardSet[*].complianceStatus",
    ):
        assert profile_definition(path).value_data_type == "xsd:string"
