from __future__ import annotations

from uuid import UUID

import pytest
from dpp_sdk import Dpp4Fun, Dpp4FunJsonCodec, validate_dpp4fun
from dpp_sdk.core import SingleValuedDataElement
from dpp_sdk.dpp4fun import (
    DPP4FUN_PROFILE,
    BillOfMaterials,
    ChairCharacteristics,
    DesignRecord,
    Durability,
    Instruction,
    Material,
    Nameplate,
    StandardAssessment,
    Traceability,
    Usage,
)

from dpp_mock_services_demo.fixtures import (
    DemoIdentity,
    build_complete_fixture,
    build_minimal_fixture,
)


@pytest.mark.parametrize("builder", [build_minimal_fixture, build_complete_fixture])
def test_demo_fixtures_are_valid_current_dpp4fun_aggregates(builder) -> None:
    value = builder(DemoIdentity.from_run_id(UUID(int=1)))

    assert isinstance(value, Dpp4Fun)
    assert validate_dpp4fun(value).is_valid
    assert isinstance(value.typed_aspect(Nameplate), Nameplate)
    characteristics = value.selected_characteristics()
    assert isinstance(characteristics, ChairCharacteristics)
    surface = characteristics.field("surface")
    assert isinstance(surface, SingleValuedDataElement)
    assert surface.value in {"Smooth", "Woven matte"}
    codec = Dpp4FunJsonCodec()
    restored = codec.from_json_and_validate(codec.to_json(value))
    assert codec.to_json(restored) == codec.to_json(value)


def test_complete_demo_fixture_has_repeated_materials_and_unique_identity() -> None:
    identity = DemoIdentity.from_run_id(UUID(int=1))
    value = build_complete_fixture(identity)
    bill = value.typed_aspect(BillOfMaterials)

    assert value.header.digital_product_passport_id == str(identity.dpp_id)
    assert value.header.unique_product_identifier == identity.product_id
    assert bill is not None
    repeated = next(item for item in bill.element.elements if item.element_id == "materialSet")
    assert len(repeated.value) >= 2
    assert all(Material.from_element(item).field("name").value for item in repeated.value)


def test_complete_fixture_covers_general_aspects_multilingual_units_and_records() -> None:
    value = build_complete_fixture(DemoIdentity.from_run_id(UUID(int=1)))
    expected = set(DPP4FUN_PROFILE.root_element_ids) | {"characteristics"}
    actual = {element.element_id for element in value.passport.data_elements}
    assert actual == expected

    nameplate = value.typed_aspect(Nameplate)
    assert nameplate is not None
    designation = nameplate.field("manufacturerProductDesignation")
    assert designation is not None
    assert {item.language for item in designation.value} == {"en-US", "de-DE"}

    chair = value.selected_characteristics()
    assert chair.quantity("height") is not None
    assert chair.quantity("height").unit.symbol == "m"

    usage = value.typed_aspect(Usage)
    instruction_set = usage.field("assemblyInstructionSet")
    assert instruction_set is not None and instruction_set.value
    instruction = Instruction.from_element(instruction_set.value[0])
    assert instruction.field("name").value
    assert instruction.field("description").value
    assert instruction.field("reference").value

    standard_set = value.typed_aspect(Durability).field("standardSet")
    assessment = StandardAssessment.from_element(standard_set.value[0])
    assert assessment.field("name").value
    assert assessment.field("description").value

    traceability = value.typed_aspect(Traceability)
    records = traceability.field("designRecordSet")
    record = DesignRecord.from_element(records.value[0])
    assert all(
        record.field(name).value for name in ("name", "description", "operator", "time", "status")
    )
