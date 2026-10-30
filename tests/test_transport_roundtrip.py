"""Canonical DPP4Fun transport contracts over the shared core codec."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from dpp_sdk.core import (
    DataElementCollection,
    DppHeader,
    Granularity,
    SingleValuedDataElement,
)
from dpp_sdk.core.json_codec import DppJsonException
from dpp_sdk.dpp4fun import Dpp4Fun, Dpp4FunJsonCodec, Nameplate
from dpp_sdk.dpp4fun.characteristics import (
    ChairCharacteristics,
    CribCharacteristics,
    Dpp4FunProductVariant,
    FabricCharacteristics,
    LockerCharacteristics,
    ParticleBoardCharacteristics,
    SofaCharacteristics,
)
from dpp_sdk.dpp4fun.profile import DPP4FUN_PROFILE
from dpp_sdk.dpp4fun.validation import Dpp4FunValidationService


def _value() -> Dpp4Fun:
    header = DppHeader(
        digital_product_passport_id="urn:example:dpp:1",
        unique_product_identifier="urn:example:product:1",
        granularity=Granularity.MODEL,
        dpp_schema_version="1.0",
        dpp_status="active",
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
        economic_operator_id="urn:example:operator:1",
    )
    return Dpp4Fun.create(header, Nameplate.create(manufacturerName="Example"))


def test_full_and_compressed_round_trip() -> None:
    codec = Dpp4FunJsonCodec()
    value = _value()
    expanded = codec.to_expanded_json(value)
    compressed = codec.to_compressed_json(value)
    assert codec.from_expanded_json(expanded).passport == value.passport
    assert codec.from_compressed_json(compressed).passport == value.passport


@pytest.mark.parametrize(
    ("variant", "aspect_type", "surface_text"),
    [
        (Dpp4FunProductVariant.CHAIR, ChairCharacteristics, "Smooth"),
        (Dpp4FunProductVariant.CRIB, CribCharacteristics, "Smooth semi-matte"),
        (Dpp4FunProductVariant.FABRIC, FabricCharacteristics, "Woven matte"),
        (Dpp4FunProductVariant.LOCKER, LockerCharacteristics, "Impregnated decor paper"),
        (
            Dpp4FunProductVariant.PARTICLE_BOARD,
            ParticleBoardCharacteristics,
            "Small-structured chenille fabric",
        ),
        (
            Dpp4FunProductVariant.SOFA,
            SofaCharacteristics,
            "Small-structured chenille fabric, micro-textured metal",
        ),
    ],
)
def test_published_surface_strings_round_trip_through_full_and_compressed(
    variant, aspect_type, surface_text
) -> None:
    header = DppHeader(
        digital_product_passport_id=f"urn:example:passport:{variant.value}",
        unique_product_identifier="urn:example:product:surface",
        granularity="model",
        dpp_schema_version="1.0",
        dpp_status="active",
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
        economic_operator_id="urn:example:operator:surface",
        content_specification_ids=(
            "DPP4FUN_COMMON_V1",
            DPP4FUN_PROFILE.variants[variant.value],
        ),
    )
    aspect = aspect_type.create(surface=surface_text)
    root_extension = SingleValuedDataElement(
        element_id="vendorExtension", object_type="SingleValuedDataElement", value="keep"
    )
    source = Dpp4Fun.create(header, aspect, extensions=(root_extension,))
    codec = Dpp4FunJsonCodec()

    expanded = codec.from_expanded_json(codec.to_expanded_json(source))
    compressed = codec.from_compressed_json(codec.to_compressed_json(source))
    for value in (expanded, compressed):
        canonical = value.passport.data_elements[0].elements[0]
        assert isinstance(canonical, SingleValuedDataElement)
        assert canonical.value == surface_text
        assert isinstance(canonical.value, str)
        assert canonical.value_data_type == "xsd:string"
        assert value.passport.data_elements[1] == root_extension
        typed_root = value.passport.data_elements[0]
        assert isinstance(typed_root, DataElementCollection)
        typed = aspect_type.from_element(typed_root)
        typed_surface = typed.field("surface")
        assert isinstance(typed_surface, SingleValuedDataElement)
        assert typed_surface.value == surface_text
        assert not any(
            issue.path.endswith("surface") and issue.rule == "DPP4FUN_BINDING_DATATYPE_MISMATCH"
            for issue in Dpp4FunValidationService().validate(value).issues
        )
        full_wire = json.loads(codec.to_expanded_json(value))
        full_surface = _find_full_value(full_wire, "surface")
        assert full_surface == surface_text
        assert _find_full_datatype(full_wire, "surface") == "xsd:string"
        compressed_wire = json.loads(codec.to_compressed_json(value))
        assert compressed_wire["characteristics"]["surface"] == surface_text
    assert codec.from_expanded_json(codec.to_expanded_json(expanded)).passport == expanded.passport
    assert (
        codec.from_compressed_json(codec.to_compressed_json(compressed)).passport
        == compressed.passport
    )
    assert source.passport.data_elements[0].elements[0].value == surface_text


def _find_full_value(node: object, element_id: str) -> object:
    if isinstance(node, dict):
        if node.get("elementId") == element_id:
            return node.get("value")
        for value in node.values():
            found = _find_full_value(value, element_id)
            if found is not None:
                return found
    if isinstance(node, list):
        for value in node:
            found = _find_full_value(value, element_id)
            if found is not None:
                return found
    return None


def _find_full_datatype(node: object, element_id: str) -> object:
    if isinstance(node, dict):
        if node.get("elementId") == element_id:
            return node.get("valueDataType")
        for value in node.values():
            found = _find_full_datatype(value, element_id)
            if found is not None:
                return found
    if isinstance(node, list):
        for value in node:
            found = _find_full_datatype(value, element_id)
            if found is not None:
                return found
    return None


def test_python_to_json_names_are_aliases_for_canonical_full_codec() -> None:
    codec = Dpp4FunJsonCodec()
    value = _value()
    assert codec.to_json(value) == codec.to_expanded_json(value)
    assert codec.from_json(codec.to_json(value)).passport == value.passport


@pytest.mark.parametrize("json_text", ["{not-json", "null", "[]"])
def test_malformed_or_non_object_full_payload_is_mapping_error(json_text: str) -> None:
    with pytest.raises(DppJsonException):
        Dpp4FunJsonCodec().from_json(json_text)
