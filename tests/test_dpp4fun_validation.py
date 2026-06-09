"""Semantic validation of the furniture model, including cross-object rules."""

from __future__ import annotations

import pytest

from dpp_sdk.core.errors import DppValidationError
from dpp_sdk.dpp4fun.model import (
    BillOfMaterials,
    Characteristics,
    Component,
    Dimensions,
    Dpp4Fun,
    Material,
    ProductClassification,
)
from dpp_sdk.dpp4fun.validation import (
    validate_bill_of_materials,
    validate_characteristics,
    validate_dimensions,
    validate_dpp4fun,
    validate_material,
    validate_product_classification,
)


def test_valid_dpp_passes(valid_dpp4fun: Dpp4Fun) -> None:
    validate_dpp4fun(valid_dpp4fun)  # no raise


def test_dimensions_require_unit_when_values_present() -> None:
    with pytest.raises(DppValidationError, match="Dimensions.unit"):
        validate_dimensions(Dimensions(width=1.0, height=1.0, depth=1.0))


def test_material_mandatory_requires_positive_portion() -> None:
    with pytest.raises(DppValidationError, match="mandatory"):
        validate_material(Material(name="glue", mandatory=True, portion=0.0))


def test_bom_duplicate_by_name_and_reference_rejected() -> None:
    bom = BillOfMaterials(
        materials=[
            Material(name="steel", portion=0.5, reference="R1"),
            Material(name="Steel", portion=0.5, reference="r1"),  # case-insensitive dup
        ]
    )
    with pytest.raises(DppValidationError, match="duplicate"):
        validate_bill_of_materials(bom)


def test_bom_distinct_references_ok() -> None:
    bom = BillOfMaterials(
        components=[Component(name="leg", reference="L1"), Component(name="leg", reference="L2")]
    )
    validate_bill_of_materials(bom)  # no raise


def test_tags_reject_duplicates() -> None:
    classification = ProductClassification(sector="F", category="Chair", tags=["a", "A"])
    with pytest.raises(DppValidationError, match="duplicate"):
        validate_product_classification(classification)


def test_features_reject_blank() -> None:
    characteristics = Characteristics(productName="X", features=["ok", "  "])
    with pytest.raises(DppValidationError, match="features"):
        validate_characteristics(characteristics)


def test_cross_rule_category_producttype_inconsistent(valid_dpp4fun: Dpp4Fun) -> None:
    bad = valid_dpp4fun.model_copy(
        update={
            "characteristics": valid_dpp4fun.characteristics.model_copy(
                update={"productType": "Table"}
            )
        }
    )
    with pytest.raises(DppValidationError, match="inconsistent"):
        validate_dpp4fun(bad)


def test_cross_rule_external_link_requires_documentation(valid_dpp4fun: Dpp4Fun) -> None:
    core = valid_dpp4fun.coreDpp
    core_no_doc = core.model_copy(
        update={
            "documentation": None,
            "passportMetadata": core.passportMetadata.model_copy(
                update={"externalDocumentationLink": "https://x.example"}
            ),
        }
    )
    bad = valid_dpp4fun.model_copy(update={"coreDpp": core_no_doc})
    with pytest.raises(DppValidationError, match="externalDocumentationLink"):
        validate_dpp4fun(bad)
