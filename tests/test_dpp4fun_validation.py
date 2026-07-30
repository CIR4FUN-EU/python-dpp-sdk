"""Semantic validation of the furniture model, including cross-object rules."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from dpp_sdk.core.errors import DppValidationError
from dpp_sdk.core.model import PassportMetadata
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
from dpp_sdk.dpp4fun.validation import (
    validate_bill_of_materials,
    validate_characteristics,
    validate_component,
    validate_dimensions,
    validate_dpp4fun,
    validate_material,
    validate_part,
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
        materials=(
            Material(name="steel", portion=0.5, reference="R1"),
            Material(name="Steel", portion=0.5, reference="r1"),  # case-insensitive dup
        )
    )
    with pytest.raises(DppValidationError, match="duplicate"):
        validate_bill_of_materials(bom)


def test_bom_distinct_references_ok() -> None:
    bom = BillOfMaterials(
        components=(Component(name="leg", reference="L1"), Component(name="leg", reference="L2"))
    )
    validate_bill_of_materials(bom)  # no raise


def test_tags_reject_duplicates() -> None:
    classification = ProductClassification(sector="F", category="Chair", tags=("a", "A"))
    with pytest.raises(DppValidationError, match="duplicate"):
        validate_product_classification(classification)


def test_features_reject_blank() -> None:
    characteristics = Characteristics(productName="X", features=("ok", "  "))
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


@pytest.mark.parametrize(
    ("contract_id", "validator", "value", "context"),
    [
        pytest.param(
            "VALIDATION-CORE-VALIDATION-UTILS--A517C1",
            validate_product_classification,
            ProductClassification.model_construct(sector="F", category="Chair", tags=(None,)),
            r"tags\[0\] must not be null",
            id="VALIDATION-CORE-VALIDATION-UTILS--A517C1",
        ),
        pytest.param(
            "VALIDATION-CORE-VALIDATION-UTILS--E376BD",
            validate_characteristics,
            Characteristics.model_construct(productName="Chair", features=(" ",)),
            r"features\[0\] must not be blank",
            id="VALIDATION-CORE-VALIDATION-UTILS--E376BD",
        ),
        pytest.param(
            "VALIDATION-CORE-VALIDATION-UTILS-CONTAINS-DUPLICATE-ENTRY-2E8F79",
            validate_product_classification,
            ProductClassification(sector="F", category="Chair", tags=("a", " A ")),
            "duplicate",
            id="VALIDATION-CORE-VALIDATION-UTILS-CONTAINS-DUPLICATE-ENTRY-2E8F79",
        ),
        pytest.param(
            "VALIDATION-DPP4FUN-COMPONENT-COMPONENT-VALIDATOR-CBB620",
            validate_bill_of_materials,
            BillOfMaterials(components=(Component.model_construct(name=""),)),
            "Component.name",
            id="VALIDATION-DPP4FUN-COMPONENT-COMPONENT-VALIDATOR-CBB620",
        ),
        pytest.param(
            "VALIDATION-DPP4FUN-PART-PART-VALIDATOR-247ACF",
            validate_part,
            Part.model_construct(name=""),
            "Part.name",
            id="VALIDATION-DPP4FUN-PART-PART-VALIDATOR-247ACF",
        ),
        pytest.param(
            "VALIDATION-CORE-VALIDATION-UTILS-IS-REQUIRED-868AB4",
            validate_product_classification,
            None,
            "ProductClassification is required",
            id="VALIDATION-CORE-VALIDATION-UTILS-IS-REQUIRED-868AB4",
        ),
        pytest.param(
            "VALIDATION-CORE-VALIDATION-UTILS-MUST-BE-NON-NEGATIVE-BUT-GOT-4EE214",
            validate_characteristics,
            Characteristics.model_construct(productName="Chair", weight=-1.0),
            "Characteristics.weight",
            id="VALIDATION-CORE-VALIDATION-UTILS-MUST-BE-NON-NEGATIVE-BUT-GOT-4EE214",
        ),
        pytest.param(
            "VALIDATION-CORE-VALIDATION-UTILS-MUST-BE-NON-NEGATIVE-BUT-GOT-C12841",
            validate_dimensions,
            Dimensions.model_construct(width=-1.0, height=1.0, depth=1.0, unit="cm"),
            "Dimensions.width",
            id="VALIDATION-CORE-VALIDATION-UTILS-MUST-BE-NON-NEGATIVE-BUT-GOT-C12841",
        ),
        pytest.param(
            "VALIDATION-CORE-VALIDATION-UTILS-MUST-BE-NON-NEGATIVE-BUT-GOT-C93495",
            validate_material,
            Material.model_construct(name="Steel", portion=-1.0),
            "Material.portion",
            id="VALIDATION-CORE-VALIDATION-UTILS-MUST-BE-NON-NEGATIVE-BUT-GOT-C93495",
        ),
        pytest.param(
            "VALIDATION-CORE-VALIDATION-UTILS-MUST-NOT-BE-BLANK-281609",
            validate_component,
            Component.model_construct(name=None),
            "Component.name",
            id="VALIDATION-CORE-VALIDATION-UTILS-MUST-NOT-BE-BLANK-281609",
        ),
        pytest.param(
            "VALIDATION-CORE-VALIDATION-UTILS-VALIDATION-RULE-DPP-DATAMODEL-DPPSDK-CORE-VALIDATION-VA-C54B7E",
            validate_material,
            Material(name="Glue", mandatory=True, portion=0.0),
            "mandatory",
            id="VALIDATION-CORE-VALIDATION-UTILS-VALIDATION-RULE-DPP-DATAMODEL-DPPSDK-CORE-VALIDATION-VA-C54B7E",
        ),
        pytest.param(
            "VALIDATION-DPP4FUN-COMPONENT-COMPONENT-NAME-FDA338",
            validate_component,
            Component.model_construct(name=""),
            "Component.name",
            id="VALIDATION-DPP4FUN-COMPONENT-COMPONENT-NAME-FDA338",
        ),
        pytest.param(
            "VALIDATION-DPP4FUN-COMPONENT-COMPONENT-REFERENCE-0E636A",
            validate_component,
            Component.model_construct(name="Leg", reference=" "),
            "Component.reference",
            id="VALIDATION-DPP4FUN-COMPONENT-COMPONENT-REFERENCE-0E636A",
        ),
        pytest.param(
            "VALIDATION-DPP4FUN-PART-PART-NAME-B844F5",
            validate_part,
            Part.model_construct(name=""),
            "Part.name",
            id="VALIDATION-DPP4FUN-PART-PART-NAME-B844F5",
        ),
        pytest.param(
            "VALIDATION-DPP4FUN-PART-PART-REFERENCE-98E9BF",
            validate_part,
            Part.model_construct(name="Foot", reference=" "),
            "Part.reference",
            id="VALIDATION-DPP4FUN-PART-PART-REFERENCE-98E9BF",
        ),
    ],
)
def test_dpp4fun_public_validators_reject_collection_and_component_errors(
    contract_id: str, validator: Callable[[Any], None], value: Any, context: str
) -> None:
    before = value.model_dump() if value is not None else None
    with pytest.raises(DppValidationError, match=context):
        validator(value)
    if value is not None:
        assert value.model_dump() == before


@pytest.mark.parametrize(
    ("contract_id", "validator", "value"),
    [
        pytest.param(
            "VALIDATION-CORE-VALIDATION-UTILS-VALIDATION-UTILS-B535AB",
            validate_bill_of_materials,
            BillOfMaterials(materials=(Material(name="Steel", portion=1.0),)),
            id="VALIDATION-CORE-VALIDATION-UTILS-VALIDATION-UTILS-B535AB",
        ),
        pytest.param(
            "VALIDATION-DPP4FUN-BILL-OF-MATERIALS-BILL-OF-MATERIALS-VALIDATOR-177D8A",
            validate_bill_of_materials,
            BillOfMaterials(
                materials=(Material(name="Steel", portion=1.0),),
                components=(Component(name="Leg", reference="L1"),),
                parts=(Part(name="Foot", reference="F1"),),
            ),
            id="VALIDATION-DPP4FUN-BILL-OF-MATERIALS-BILL-OF-MATERIALS-VALIDATOR-177D8A",
        ),
        pytest.param(
            "VALIDATION-DPP4FUN-DIMENSIONS-DIMENSIONS-VALIDATOR-E905DD",
            validate_dimensions,
            Dimensions(width=1.0, height=2.0, depth=3.0, unit="cm"),
            id="VALIDATION-DPP4FUN-DIMENSIONS-DIMENSIONS-VALIDATOR-E905DD",
        ),
        pytest.param(
            "VALIDATION-DPP4FUN-MATERIAL-MATERIAL-VALIDATOR-3525B6",
            validate_material,
            Material(name="Steel", portion=1.0),
            id="VALIDATION-DPP4FUN-MATERIAL-MATERIAL-VALIDATOR-3525B6",
        ),
    ],
)
def test_dpp4fun_public_validators_accept_tuple_backed_values_repeatedly(
    contract_id: str, validator: Callable[[Any], None], value: Any
) -> None:
    before = value.model_dump()
    validator(value)
    validator(value)
    assert value.model_dump() == before


def test_dpp4fun_order_core_then_product_then_cross(valid_dpp4fun: Dpp4Fun) -> None:
    invalid_core = valid_dpp4fun.with_updates(
        coreDpp=valid_dpp4fun.coreDpp.with_updates(
            passportMetadata=PassportMetadata.model_construct(
                uniqueProductIdentifier=None, passportUpdateDates=()
            )
        )
    )
    with pytest.raises(DppValidationError, match="PassportMetadata"):
        validate_dpp4fun(invalid_core)
    invalid_product = valid_dpp4fun.with_updates(
        classification=ProductClassification.model_construct(sector="", category="Chair", tags=())
    )
    with pytest.raises(DppValidationError, match="ProductClassification.sector"):
        validate_dpp4fun(invalid_product)
    invalid_cross_only = valid_dpp4fun.with_updates(
        characteristics=valid_dpp4fun.characteristics.with_updates(productType="Table")
    )
    with pytest.raises(DppValidationError, match="inconsistent"):
        validate_dpp4fun(invalid_cross_only)


@pytest.mark.parametrize(
    "contract_id",
    [
        pytest.param(
            "VALIDATION-DPP4FUN-CHARACTERISTICS-CHARACTERISTICS-VALIDATOR-CDD0A7",
            id="VALIDATION-DPP4FUN-CHARACTERISTICS-CHARACTERISTICS-VALIDATOR-CDD0A7",
        ),
        pytest.param(
            "VALIDATION-DPP4FUN-PRODUCT-CLASSIFICATION-PRODUCT-CLASSIFICATION-VALIDATOR-247411",
            id="VALIDATION-DPP4FUN-PRODUCT-CLASSIFICATION-PRODUCT-CLASSIFICATION-VALIDATOR-247411",
        ),
    ],
)
def test_product_subobject_validators_accept_valid_subobjects_repeatedly(
    contract_id: str, valid_dpp4fun: Dpp4Fun
) -> None:
    value: Any
    validator: Callable[[Any], None]
    if contract_id.endswith("CDD0A7"):
        value = valid_dpp4fun.characteristics
        validator = validate_characteristics
    else:
        value = valid_dpp4fun.classification
        validator = validate_product_classification
    before = value.model_dump()
    validator(value)
    validator(value)
    assert value.model_dump() == before


@pytest.mark.parametrize(
    "contract_id",
    [
        pytest.param(
            "VALIDATION-DPP4FUN-DPP4-FUN-DPP4-FUN-VALIDATION-SERVICE-C8F833",
            id="VALIDATION-DPP4FUN-DPP4-FUN-DPP4-FUN-VALIDATION-SERVICE-C8F833",
        ),
        pytest.param(
            "VALIDATION-DPP4FUN-DPP4-FUN-DPP4-FUN-VALIDATOR-C84912",
            id="VALIDATION-DPP4FUN-DPP4-FUN-DPP4-FUN-VALIDATOR-C84912",
        ),
    ],
)
def test_dpp4fun_public_validator_accepts_valid_dpp_repeatedly(
    contract_id: str, valid_dpp4fun: Dpp4Fun
) -> None:
    before = valid_dpp4fun.model_dump()
    validate_dpp4fun(valid_dpp4fun)
    validate_dpp4fun(valid_dpp4fun)
    assert valid_dpp4fun.model_dump() == before
