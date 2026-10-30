"""Core model construction, immutability, structural rules, and JSON round-trip."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from dpp_sdk.core.model import (
    DataElementCollection,
    DigitalProductPassport,
    DppHeader,
    Granularity,
    RelatedResource,
    SingleValuedDataElement,
)
from dpp_sdk.core.semantic import SemanticPath


def test_dpp_header_preserves_optional_fields_and_ordered_immutable_specs() -> None:
    specifications = ["spec-a", "spec-b"]
    header = DppHeader.model_validate(
        {
            "digitalProductPassportId": "passport-id",
            "uniqueProductIdentifier": "product-id",
            "granularity": "item",
            "dppSchemaVersion": "2026",
            "dppStatus": "active",
            "lastUpdated": "2026-01-02T03:04:05Z",
            "economicOperatorId": "operator-id",
            "facilityId": "facility-id",
            "contentSpecificationIds": specifications,
        }
    )
    specifications.append("late")

    assert header.digital_product_passport_id == "passport-id"
    assert header.unique_product_identifier == "product-id"
    assert header.granularity is Granularity.ITEM
    assert header.dpp_schema_version == "2026"
    assert header.dpp_status == "active"
    assert header.last_updated == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert header.economic_operator_id == "operator-id"
    assert header.facility_id == "facility-id"
    assert header.content_specification_ids == ("spec-a", "spec-b")
    assert header == DppHeader(**header.model_dump())
    assert header.with_updates(facility_id=None).facility_id is None
    assert header.facility_id == "facility-id"
    with pytest.raises(ValidationError):
        header.content_specification_ids += ("changed",)  # type: ignore[misc]


@pytest.mark.parametrize(
    "updates",
    [
        {"content_specification_ids": None},
        {"content_specification_ids": ("valid", None)},
        {"last_updated": datetime(2026, 1, 2)},
        {"unknown": "field"},
    ],
)
def test_dpp_header_rejects_structurally_invalid_updates(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DppHeader().with_updates(**updates)


def test_digital_product_passport_requires_header_and_parses_nested_full_elements() -> None:
    full_elements = [
        {
            "objectType": "DataElementCollection",
            "elementId": "identity",
            "elements": [
                {
                    "objectType": "SingleValuedDataElement",
                    "elementId": "name",
                    "dictionaryReference": "dictionary:name",
                    "value": "chair",
                    "valueDataType": "xsd:string",
                }
            ],
        },
        {
            "objectType": "RelatedResource",
            "elementId": "manual",
            "contentType": "application/pdf",
            "url": "https://example.com/manual.pdf",
            "language": "en",
            "resourceTitle": "Manual",
        },
    ]
    passport = DigitalProductPassport.model_validate(
        {
            "dpp_header": {"digitalProductPassportId": "passport"},
            "elements": full_elements,
        }
    )

    assert passport.dpp_header.digital_product_passport_id == "passport"
    assert isinstance(passport.data_elements[0], DataElementCollection)
    nested = passport.data_elements[0].elements[0]
    assert isinstance(nested, SingleValuedDataElement)
    assert nested.object_type == "SingleValuedDataElement"
    assert nested.dictionary_reference == "dictionary:name"
    assert nested.value == "chair"
    assert isinstance(passport.data_elements[1], RelatedResource)
    assert passport.data_elements[1].resource_title == "Manual"
    assert len(passport.data_elements) == 2
    assert DigitalProductPassport(dpp_header=passport.dpp_header) == DigitalProductPassport(
        dpp_header=passport.dpp_header, data_elements=()
    )


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"dpp_header": None},
        {"dpp_header": {}, "elements": [{"objectType": "UnknownElement"}]},
        {
            "dpp_header": {},
            "elements": [{"objectType": "SingleValuedDataElement", "extensionId": "unsupported"}],
        },
        {
            "dpp_header": {},
            "elements": [{"objectType": "SingleValuedDataElement", "value": object()}],
        },
    ],
)
def test_digital_product_passport_rejects_missing_header_and_invalid_elements(
    data: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        DigitalProductPassport.model_validate(data)


def test_digital_product_passport_copies_order_and_revalidates_immutable_updates() -> None:
    header = DppHeader(digital_product_passport_id="passport")
    first = SingleValuedDataElement(element_id="first", value="one")
    second = SingleValuedDataElement(element_id="second", value="two")
    source = [first, second]
    passport = DigitalProductPassport(dpp_header=header, data_elements=source)
    source.clear()

    updated = passport.with_updates(data_elements=[second])
    assert passport.data_elements == (first, second)
    assert updated.data_elements == (second,)
    assert updated.dpp_header == header
    assert updated == DigitalProductPassport(dpp_header=header, data_elements=[second])
    assert updated != passport
    with pytest.raises(ValidationError):
        passport.with_updates(dpp_header=None)
    with pytest.raises(ValidationError):
        passport.with_updates(data_elements=[{"objectType": "UnknownElement"}])


def test_digital_product_passport_finds_nested_elements_by_id_or_child_index() -> None:
    leaf = SingleValuedDataElement(element_id="name", value="chair")
    inner = DataElementCollection(element_id="details", elements=[leaf])
    outer = DataElementCollection(element_id="product", elements=[inner])
    passport = DigitalProductPassport(dpp_header=DppHeader(), data_elements=[outer])

    assert passport.find_data_element(("product", "details", "name")) == leaf
    assert passport.find_data_element(("product", "0", "0")) == leaf
    assert passport.find_data_element(SemanticPath.of("product", "details", "name")) == leaf
    assert passport.find_data_element(SemanticPath.of("product", "0", "0")) == leaf
    assert passport.find_data_element(("product", "5")) is None
    assert passport.find_data_element(("product", "name")) is None
    with pytest.raises(ValueError, match="non-blank"):
        passport.find_data_element(())


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (0.1, Decimal("0.1")),
        (1, Decimal("1.00")),
        ([0.1, {"nested": 2}], [Decimal("0.1"), {"nested": Decimal("2.0")}]),
    ],
)
def test_single_value_numeric_equality_matches_java_recursively(left, right) -> None:
    first = SingleValuedDataElement(element_id="value", value=left)
    second = SingleValuedDataElement(element_id="value", value=right)

    assert first == second
    assert hash(first) == hash(second)
    assert DigitalProductPassport(dpp_header=DppHeader(), data_elements=[first]) == (
        DigitalProductPassport(dpp_header=DppHeader(), data_elements=[second])
    )


def test_new_aggregate_models_are_publicly_exported() -> None:
    from dpp_sdk import DigitalProductPassport as RootPassport
    from dpp_sdk import DppHeader as RootDppHeader
    from dpp_sdk.core import DigitalProductPassport as CorePassport
    from dpp_sdk.core import DppHeader as CoreDppHeader

    assert RootDppHeader is CoreDppHeader is DppHeader
    assert RootPassport is CorePassport is DigitalProductPassport
