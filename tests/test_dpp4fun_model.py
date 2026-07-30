"""Dpp4Fun construction, immutable collections, and update contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dpp_sdk.dpp4fun.model import (
    BillOfMaterials,
    Characteristics,
    Component,
    Dimensions,
    Dpp4Fun,
    Material,
    Part,
    ProductClassification,
)


@pytest.mark.parametrize(
    "contract_id, factory",
    [
        ("MODEL-DPP4FUN-BILL-OF-MATERIALS-CONSTRUCTION", BillOfMaterials),
        (
            "MODEL-DPP4FUN-CHARACTERISTICS-CONSTRUCTION",
            lambda: Characteristics(productName="Chair"),
        ),
        (
            "MODEL-DPP4FUN-CHARACTERISTICS-FIELD-COLOR",
            lambda: Characteristics(productName="Chair", color="red"),
        ),
        (
            "MODEL-DPP4FUN-CHARACTERISTICS-FIELD-DESCRIPTION",
            lambda: Characteristics(productName="Chair", description="oak"),
        ),
        ("MODEL-DPP4FUN-COMPONENT", lambda: Component(name="leg")),
        ("MODEL-DPP4FUN-COMPONENT-CONSTRUCTION", lambda: Component(name="leg")),
        ("MODEL-DPP4FUN-DIMENSIONS", lambda: Dimensions(width=1, height=2, depth=3)),
        ("MODEL-DPP4FUN-DIMENSIONS-CONSTRUCTION", lambda: Dimensions(width=1, height=2, depth=3)),
        ("MODEL-DPP4FUN-DPP4-FUN", lambda: None),
        ("MODEL-DPP4FUN-DPP4-FUN-CONSTRUCTION", lambda: None),
        ("MODEL-DPP4FUN-MATERIAL", lambda: Material(name="steel")),
        ("MODEL-DPP4FUN-MATERIAL-CONSTRUCTION", lambda: Material(name="steel")),
        ("MODEL-DPP4FUN-PART", lambda: Part(name="seat")),
        ("MODEL-DPP4FUN-PART-CONSTRUCTION", lambda: Part(name="seat")),
        (
            "MODEL-DPP4FUN-PRODUCT-CLASSIFICATION-CONSTRUCTION",
            lambda: ProductClassification(sector="Furniture", category="Chair"),
        ),
        (
            "MODEL-DPP4FUN-PRODUCT-CLASSIFICATION-FIELD-SUB-CATEGORY",
            lambda: ProductClassification(
                sector="Furniture", category="Chair", subCategory="Office"
            ),
        ),
    ],
    ids=lambda row: row if isinstance(row, str) else None,
)
def test_remaining_dpp4fun_contract_evidence(
    contract_id: str, factory: object, valid_dpp4fun: Dpp4Fun
) -> None:
    if "DPP4-FUN" in contract_id:
        model = valid_dpp4fun
        assert type(model).model_validate(model.model_dump(mode="json")) == model
        return
    model = factory()  # type: ignore[operator]
    assert type(model).model_validate(model.model_dump(mode="json")) == model


@pytest.mark.parametrize(
    ("contract_id", "model", "field"),
    [
        (
            "MODEL-DPP4FUN-PRODUCT-CLASSIFICATION",
            ProductClassification(sector="Furniture", category="Chair", tags=["a"]),
            "tags",
        ),
        (
            "MODEL-DPP4FUN-CHARACTERISTICS",
            Characteristics(productName="Chair", features=["a"]),
            "features",
        ),
        ("MODEL-DPP4FUN-BILL-OF-MATERIALS", BillOfMaterials(), "materials"),
    ],
)
def test_dpp4fun_collections_are_tuples_and_json_arrays(
    contract_id: str, model: object, field: str
) -> None:
    value = getattr(model, field)
    assert isinstance(value, tuple)
    assert model.model_dump(mode="json")[field] == list(value)  # type: ignore[union-attr]
    with pytest.raises(AttributeError):
        value.append("x")


def test_dpp4fun_empty_collections_are_immutable_defaults() -> None:
    assert BillOfMaterials().materials == ()


@pytest.mark.parametrize(
    "invalid",
    [-1.0, float("nan"), float("inf"), float("-inf")],
    ids=["negative", "nan", "positive-infinity", "negative-infinity"],
)
def test_dec_003_contracted_numbers_are_finite_and_non_negative(invalid: float) -> None:
    with pytest.raises(ValidationError):
        Characteristics(productName="Chair", weight=invalid)
    with pytest.raises(ValidationError):
        Dimensions(width=invalid, height=1.0, depth=1.0, unit="cm")
    with pytest.raises(ValidationError):
        Material(name="Steel", portion=invalid)


def test_dec_003_zero_positive_and_finite_exponent_values_are_accepted() -> None:
    assert Characteristics(productName="Chair", weight=0.0).weight == 0.0
    assert Dimensions(width=1.25e2, height=1.0, depth=1.0, unit="cm").width == 125.0
    assert Material(name="Steel", portion=1.25e-2).portion == 0.0125


@pytest.mark.parametrize(
    ("contract_id", "attribute", "replacement"),
    [
        ("MODEL-DPP4FUN-BILL-OF-MATERIALS-IMMUTABLE-UPDATE", "billOfMaterials", BillOfMaterials()),
        (
            "MODEL-DPP4FUN-CHARACTERISTICS-IMMUTABLE-UPDATE",
            "characteristics",
            Characteristics(productName="Changed"),
        ),
        (
            "MODEL-DPP4FUN-DPP4-FUN-IMMUTABLE-UPDATE",
            "classification",
            ProductClassification(sector="Furniture", category="Changed"),
        ),
    ],
)
def test_dpp4fun_with_updates_preserves_subtype(
    contract_id: str, attribute: str, replacement: object, valid_dpp4fun: object
) -> None:
    updated = valid_dpp4fun.with_updates(**{attribute: replacement})  # type: ignore[union-attr]
    assert type(updated) is type(valid_dpp4fun)
    assert getattr(updated, attribute) == replacement
    with pytest.raises(ValidationError):
        valid_dpp4fun.with_updates(unknown=True)  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("contract_id", "model", "changes"),
    [
        ("MODEL-DPP4FUN-COMPONENT-IMMUTABLE-UPDATE", Component(name="leg"), {"reference": "C-1"}),
        (
            "MODEL-DPP4FUN-DIMENSIONS-IMMUTABLE-UPDATE",
            Dimensions(width=1, height=1, depth=1),
            {"unit": "cm"},
        ),
        ("MODEL-DPP4FUN-MATERIAL-IMMUTABLE-UPDATE", Material(name="steel"), {"portion": 0.5}),
        ("MODEL-DPP4FUN-PART-IMMUTABLE-UPDATE", Part(name="seat"), {"mandatory": True}),
        (
            "MODEL-DPP4FUN-PRODUCT-CLASSIFICATION-IMMUTABLE-UPDATE",
            ProductClassification(sector="Furniture", category="Chair"),
            {"tags": ["office"]},
        ),
    ],
)
def test_product_leaf_with_updates_revalidates(
    contract_id: str, model: object, changes: dict[str, object]
) -> None:
    updated = model.with_updates(**changes)  # type: ignore[union-attr]
    assert type(updated) is type(model)
    with pytest.raises(ValidationError):
        model.with_updates(unknown=True)  # type: ignore[union-attr]


def test_dpp4fun_with_updates_rejects_invalid_known_field_values() -> None:
    """The shared immutable update path revalidates known DPP4Fun fields."""
    classification = ProductClassification(sector="Furniture", category="Chair")

    with pytest.raises(ValidationError, match="must not be blank if provided"):
        classification.with_updates(group=" ")


@pytest.mark.parametrize(
    (
        "contract_id",
        "model",
        "valid_changes",
        "changed_field",
        "expected_value",
        "invalid_changes",
        "invalid_match",
    ),
    [
        pytest.param(
            "MODEL-DPP4FUN-BILL-OF-MATERIALS-IMMUTABLE-UPDATE",
            BillOfMaterials(),
            {"materials": (Material(name="Steel", portion=1.0),)},
            "materials",
            (Material(name="Steel", portion=1.0),),
            {"materials": (None,)},
            "materials.0",
            id="MODEL-DPP4FUN-BILL-OF-MATERIALS-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-DPP4FUN-CHARACTERISTICS-IMMUTABLE-UPDATE",
            Characteristics(productName="Chair"),
            {"productName": "Desk"},
            "productName",
            "Desk",
            {"productName": " "},
            "must not be blank",
            id="MODEL-DPP4FUN-CHARACTERISTICS-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-DPP4FUN-COMPONENT-IMMUTABLE-UPDATE",
            Component(name="Leg"),
            {"reference": "C-1"},
            "reference",
            "C-1",
            {"name": " "},
            "must not be blank",
            id="MODEL-DPP4FUN-COMPONENT-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-DPP4FUN-DIMENSIONS-IMMUTABLE-UPDATE",
            Dimensions(width=1.0, height=2.0, depth=3.0),
            {"unit": "cm"},
            "unit",
            "cm",
            {"width": -1.0},
            "greater than or equal to 0",
            id="MODEL-DPP4FUN-DIMENSIONS-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-DPP4FUN-DPP4-FUN-IMMUTABLE-UPDATE",
            None,
            {
                "classification": ProductClassification(
                    sector="Furniture",
                    category="Desk",
                )
            },
            "classification",
            ProductClassification(sector="Furniture", category="Desk"),
            {"coreDpp": None},
            "coreDpp",
            id="MODEL-DPP4FUN-DPP4-FUN-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-DPP4FUN-MATERIAL-IMMUTABLE-UPDATE",
            Material(name="Steel"),
            {"portion": 0.5},
            "portion",
            0.5,
            {"portion": -1.0},
            "greater than or equal to 0",
            id="MODEL-DPP4FUN-MATERIAL-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-DPP4FUN-PART-IMMUTABLE-UPDATE",
            Part(name="Seat"),
            {"mandatory": True},
            "mandatory",
            True,
            {"name": " "},
            "must not be blank",
            id="MODEL-DPP4FUN-PART-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-DPP4FUN-PRODUCT-CLASSIFICATION-IMMUTABLE-UPDATE",
            ProductClassification(sector="Furniture", category="Chair"),
            {"tags": ("office",)},
            "tags",
            ("office",),
            {"group": " "},
            "must not be blank if provided",
            id="MODEL-DPP4FUN-PRODUCT-CLASSIFICATION-IMMUTABLE-UPDATE",
        ),
    ],
)
def test_dpp4fun_contract_with_updates_revalidates_known_fields_and_preserves_original(
    contract_id: str,
    model: object,
    valid_changes: dict[str, object],
    changed_field: str,
    expected_value: object,
    invalid_changes: dict[str, object],
    invalid_match: str,
    valid_dpp4fun: Dpp4Fun,
) -> None:
    value = valid_dpp4fun if model is None else model
    before = value.model_dump(mode="python")  # type: ignore[union-attr]
    original_field = getattr(value, changed_field)

    updated = value.with_updates(**valid_changes)  # type: ignore[union-attr]

    assert type(updated) is type(value)
    assert getattr(updated, changed_field) == expected_value
    assert getattr(value, changed_field) == original_field
    assert value.model_dump(mode="python") == before  # type: ignore[union-attr]
    with pytest.raises(ValidationError, match=invalid_match):
        value.with_updates(**invalid_changes)  # type: ignore[union-attr]
    assert value.model_dump(mode="python") == before  # type: ignore[union-attr]
