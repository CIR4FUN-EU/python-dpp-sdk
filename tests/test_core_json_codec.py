from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from dpp_sdk.core import (
    CompressedExpansionResult,
    DataElementCollection,
    DataElementKind,
    DigitalProductPassport,
    DppHeader,
    DppJsonCodec,
    DppJsonException,
    Granularity,
    MultiValuedDataElement,
    RelatedResource,
    SemanticDefinition,
    SemanticPath,
    SingleValuedDataElement,
)


def passport() -> DigitalProductPassport:
    return DigitalProductPassport(
        dpp_header=DppHeader(
            digital_product_passport_id="https://example.test/dpp/1",
            unique_product_identifier="https://example.test/product/1",
            granularity=Granularity.ITEM,
            dpp_schema_version="EN18223:2026",
            dpp_status="active",
            last_updated=datetime(2026, 9, 21, 10, 0, tzinfo=UTC),
            economic_operator_id="urn:example:operator:1",
            content_specification_ids=("SPEC-1",),
        ),
        data_elements=(
            DataElementCollection(
                element_id="details",
                dictionary_reference="urn:dictionary:details",
                elements=(
                    SingleValuedDataElement(
                        element_id="label",
                        dictionary_reference="urn:dictionary:label",
                        value_data_type="xsd:string",
                        value="Chair",
                    ),
                ),
            ),
            MultiValuedDataElement(
                element_id="weights",
                value_data_type="xsd:decimal",
                value=(
                    SingleValuedDataElement(element_id="first", value=1.5),
                    SingleValuedDataElement(element_id="second", value=2.5),
                ),
            ),
        ),
    )


def test_full_codec_preserves_canonical_shape_and_semantic_metadata() -> None:
    codec = DppJsonCodec()
    source = passport()

    encoded = codec.to_expanded_json(source)
    decoded = codec.from_expanded_json(encoded)
    wire = json.loads(encoded)

    assert wire["granularity"] == "item"
    assert list(wire)[-1] == "elements"
    assert wire["elements"][0]["objectType"] == "DataElementCollection"
    assert wire["elements"][0]["elements"][0]["valueDataType"] == "xsd:string"
    assert decoded == source


def test_java_instant_millisecond_precision_is_canonical_on_the_wire() -> None:
    codec = DppJsonCodec()
    source = passport().with_updates(
        dpp_header=passport().dpp_header.with_updates(
            last_updated=datetime(2026, 9, 21, 10, 0, 0, 123_000, tzinfo=UTC)
        )
    )

    encoded = codec.to_expanded_json(source)

    assert json.loads(encoded)["lastUpdated"] == "2026-09-21T10:00:00.123Z"
    assert codec.from_expanded_json(encoded) == source


def test_full_codec_preserves_decimal_value_scale_without_float_conversion() -> None:
    codec = DppJsonCodec()
    source = passport().with_updates(
        data_elements=(
            SingleValuedDataElement(
                element_id="amount",
                value_data_type="xsd:decimal",
                value=Decimal("123.4500"),
            ),
        )
    )

    encoded = codec.to_expanded_json(source)
    decoded = codec.from_expanded_json(encoded)

    assert '"value":123.4500' in encoded
    assert decoded.data_elements[0].value == Decimal("123.4500")


def test_compressed_expansion_reports_missing_metadata_without_inventing_it() -> None:
    codec = DppJsonCodec()
    compressed = codec.to_compressed_json(passport())

    result = codec.expand_compressed_json(compressed)
    expanded = result.passport.data_elements

    assert isinstance(result, CompressedExpansionResult)
    assert isinstance(expanded[0], DataElementCollection)
    assert expanded[0].dictionary_reference is None
    assert isinstance(expanded[0].elements[0], SingleValuedDataElement)
    assert expanded[0].elements[0].value_data_type is None
    assert result.issues
    assert json.loads(codec.to_compressed_json(result.passport)) == json.loads(compressed)


def test_compressed_expansion_uses_previous_passport_to_restore_known_metadata() -> None:
    codec = DppJsonCodec()
    source = passport()

    result = codec.expand_compressed_json(codec.to_compressed_json(source), previous=source)

    assert result.passport == source


def test_resolver_supplies_only_explicit_semantics_at_complete_paths() -> None:
    codec = DppJsonCodec()
    source = passport()
    compressed = codec.to_compressed_json(source)

    class Resolver:
        def resolve(self, content_specification_ids: tuple[str, ...], path: SemanticPath):
            assert content_specification_ids == ("SPEC-1",)
            definitions = {
                SemanticPath(("details",)): SemanticDefinition(
                    kind=DataElementKind.COLLECTION,
                    element_id="details",
                    dictionary_reference="urn:dictionary:details",
                ),
                SemanticPath(("details", "label")): SemanticDefinition(
                    kind=DataElementKind.SINGLE,
                    element_id="label",
                    dictionary_reference="urn:dictionary:label",
                    value_data_type="xsd:string",
                ),
                SemanticPath(("weights",)): SemanticDefinition(
                    kind=DataElementKind.MULTI_VALUED,
                    element_id="weights",
                    value_data_type="xsd:decimal",
                    dictionary_reference_resolved=True,
                ),
                SemanticPath(("weights", "0")): SemanticDefinition(
                    kind=DataElementKind.SINGLE,
                    element_id="first",
                    value_data_type="xsd:decimal",
                    dictionary_reference_resolved=True,
                ),
                SemanticPath(("weights", "1")): SemanticDefinition(
                    kind=DataElementKind.SINGLE,
                    element_id="second",
                    value_data_type="xsd:decimal",
                    dictionary_reference_resolved=True,
                ),
            }
            return definitions.get(path)

    result = codec.expand_compressed_json_with_resolver(compressed, Resolver())

    resolved_weights = result.passport.data_elements[1]
    assert isinstance(resolved_weights, MultiValuedDataElement)
    assert resolved_weights.value_data_type == "xsd:decimal"
    assert all(
        isinstance(item, SingleValuedDataElement) and item.value_data_type == "xsd:decimal"
        for item in resolved_weights.value
    )
    assert result.passport.dpp_header == source.dpp_header
    assert result.issues == ()


def test_resolved_absence_conflicts_with_metadata_in_the_previous_passport() -> None:
    codec = DppJsonCodec()
    source = passport()
    compressed = codec.to_compressed_json(source)

    class Resolver:
        def resolve(self, content_specification_ids: tuple[str, ...], path: SemanticPath):
            if path == SemanticPath(("details", "label")):
                return SemanticDefinition(
                    kind=DataElementKind.SINGLE,
                    element_id="label",
                    dictionary_reference_resolved=True,
                )
            return None

    with pytest.raises(DppJsonException, match="conflicts with stored dictionaryReference"):
        codec.expand_compressed_json(compressed, previous=source, resolver=Resolver())


@pytest.mark.parametrize("bad_json", ["{", "[]", '{"x": 1, "x": 2}'])
def test_compressed_codec_rejects_malformed_roots_and_duplicate_keys(bad_json: str) -> None:
    with pytest.raises(DppJsonException):
        DppJsonCodec().expand_compressed_json(bad_json)


def test_full_codec_rejects_incomplete_headers_and_unknown_element_types() -> None:
    codec = DppJsonCodec()
    valid_json = codec.to_expanded_json(passport())

    with pytest.raises(DppJsonException, match="dppStatus"):
        codec.from_expanded_json(valid_json.replace('"dppStatus":"active",', ""))
    with pytest.raises(DppJsonException, match="unknown objectType 'FutureType'"):
        codec.from_expanded_json(valid_json.replace("DataElementCollection", "FutureType"))
    with pytest.raises(DppJsonException, match="digitalProductPassportId is required"):
        codec.to_expanded_json(DigitalProductPassport(dpp_header=DppHeader()))


def test_arbitrary_compressed_element_id_does_not_gain_semantic_metadata() -> None:
    codec = DppJsonCodec()
    root = json.loads(codec.to_compressed_json(passport()))
    root["unregistered-extension"] = "value"

    expanded = codec.expand_compressed_json(json.dumps(root)).passport
    extension = expanded.data_elements[-1]

    assert extension.element_id == "unregistered-extension"
    assert isinstance(extension, SingleValuedDataElement)
    assert extension.dictionary_reference is None
    assert extension.value_data_type is None


def test_element_codec_and_header_inspection_follow_the_java_operations() -> None:
    codec = DppJsonCodec()
    element = passport().data_elements[0]

    expanded = codec.to_expanded_element_json(element)
    restored = codec.from_expanded_element_json(expanded)
    compressed = codec.to_compressed_element_json(element)
    header = codec.read_header(codec.to_expanded_json(passport()))

    assert restored == element
    assert json.loads(compressed) == {"label": "Chair"}
    assert header == passport().dpp_header
    assert (
        codec.expand_compressed_element_json("label", '"Seat"', element.elements[0]).value == "Seat"
    )


def test_related_resource_field_order_matches_java_transport() -> None:
    codec = DppJsonCodec()
    resource = RelatedResource(
        element_id="manual",
        content_type="application/pdf",
        url="https://example.test/manual.pdf",
        language="en",
        resource_title="Manual",
    )

    full_fields = list(json.loads(codec.to_expanded_element_json(resource)))
    compressed_fields = list(json.loads(codec.to_compressed_element_json(resource)))

    assert full_fields == [
        "elementId",
        "objectType",
        "contentType",
        "url",
        "language",
        "resourceTitle",
    ]
    assert compressed_fields == ["resourceTitle", "contentType", "url", "language"]


def test_codec_types_are_exported_from_the_package_root() -> None:
    import dpp_sdk

    assert dpp_sdk.DppJsonCodec is DppJsonCodec
    assert dpp_sdk.SemanticResolver is not None
    assert dpp_sdk.CompressedExpansionResult is CompressedExpansionResult
