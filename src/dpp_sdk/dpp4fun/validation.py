"""Semantic validators for the furniture DPP (port of ``dppsdk.dpp4fun.validation``).

Fail-fast: raises :class:`~dpp_sdk.core.errors.DppValidationError` on the first
violation. :func:`validate_dpp4fun` is the top-level entry point; it delegates to
the core validators, the furniture sub-validators, and the two cross-object rules.
"""

from __future__ import annotations

from ..core.errors import DppValidationError
from ..core.validation import validate_dpp_core
from .model import (
    BillOfMaterials,
    Characteristics,
    Component,
    Dimensions,
    Dpp4Fun,
    Material,
    Part,
    ProductClassification,
)


def _has_text(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _require_not_blank(value: str | None, field_name: str) -> None:
    if value is None or not value.strip():
        raise DppValidationError(f"{field_name} must not be blank")


def _require_clean_string_list(items: list[str], list_name: str) -> None:
    """No null, blank, or (case-insensitive, trimmed) duplicate entries."""
    seen: set[str] = set()
    for index, item in enumerate(items):
        if item is None:
            raise DppValidationError(f"{list_name}[{index}] must not be null")
        if not item.strip():
            raise DppValidationError(f"{list_name}[{index}] must not be blank")
        key = item.strip().lower()
        if key in seen:
            raise DppValidationError(f"{list_name} contains duplicate entry: '{item.strip()}'")
        seen.add(key)


def validate_dimensions(dimensions: Dimensions | None) -> None:
    if dimensions is None:
        return
    for value, name in (
        (dimensions.width, "Dimensions.width"),
        (dimensions.height, "Dimensions.height"),
        (dimensions.depth, "Dimensions.depth"),
    ):
        if value is not None and value < 0:
            raise DppValidationError(f"{name} must be non-negative, but got {value}")

    has_any_value = (
        dimensions.width is not None
        or dimensions.height is not None
        or dimensions.depth is not None
    )
    if not has_any_value:
        raise DppValidationError(
            "Dimensions object exists but no dimension values (width/height/depth) are provided"
        )
    _require_not_blank(dimensions.unit, "Dimensions.unit")


def validate_material(material: Material | None) -> None:
    if material is None:
        return
    _require_not_blank(material.name, "Material.name")
    if material.portion < 0:
        raise DppValidationError(
            f"Material.portion must be non-negative, but got {material.portion}"
        )
    if material.reference is not None:
        _require_not_blank(material.reference, "Material.reference")
    if material.mandatory and material.portion <= 0:
        raise DppValidationError(
            f"Material '{material.name}' is mandatory but has zero or no portion"
        )


def validate_component(component: Component | None) -> None:
    if component is None:
        return
    _require_not_blank(component.name, "Component.name")
    if component.reference is not None:
        _require_not_blank(component.reference, "Component.reference")


def validate_part(part: Part | None) -> None:
    if part is None:
        return
    _require_not_blank(part.name, "Part.name")
    if part.reference is not None:
        _require_not_blank(part.reference, "Part.reference")


def _key(name: str, reference: str | None) -> str:
    normalized_name = name.strip().lower() if name else ""
    normalized_reference = reference.strip().lower() if reference else ""
    return f"{normalized_name}|{normalized_reference}"


def validate_bill_of_materials(bom: BillOfMaterials | None) -> None:
    if bom is None:
        return

    material_keys: set[str] = set()
    for material in bom.materials:
        validate_material(material)
        key = _key(material.name, material.reference)
        if key in material_keys:
            raise DppValidationError(f"BillOfMaterials.materials contains duplicate entry: {key}")
        material_keys.add(key)

    component_keys: set[str] = set()
    for component in bom.components:
        validate_component(component)
        key = _key(component.name, component.reference)
        if key in component_keys:
            raise DppValidationError(f"BillOfMaterials.components contains duplicate entry: {key}")
        component_keys.add(key)

    part_keys: set[str] = set()
    for part in bom.parts:
        validate_part(part)
        key = _key(part.name, part.reference)
        if key in part_keys:
            raise DppValidationError(f"BillOfMaterials.parts contains duplicate entry: {key}")
        part_keys.add(key)


def validate_product_classification(classification: ProductClassification | None) -> None:
    if classification is None:
        raise DppValidationError("ProductClassification is required")
    _require_not_blank(classification.sector, "ProductClassification.sector")
    _require_not_blank(classification.category, "ProductClassification.category")
    if classification.group is not None:
        _require_not_blank(classification.group, "ProductClassification.group")
    if classification.subCategory is not None:
        _require_not_blank(classification.subCategory, "ProductClassification.subCategory")

    if _has_text(classification.subCategory) and not _has_text(classification.category):
        raise DppValidationError(
            "ProductClassification.subCategory is set but category is missing"
        )
    if _has_text(classification.group) and not _has_text(classification.sector):
        raise DppValidationError("ProductClassification.group is set but sector is missing")

    if classification.tags:
        _require_clean_string_list(classification.tags, "ProductClassification.tags")


def validate_characteristics(characteristics: Characteristics | None) -> None:
    if characteristics is None:
        raise DppValidationError("Characteristics is required")
    _require_not_blank(characteristics.productName, "Characteristics.productName")
    if characteristics.weight is not None and characteristics.weight < 0:
        raise DppValidationError(
            f"Characteristics.weight must be non-negative, but got {characteristics.weight}"
        )
    validate_dimensions(characteristics.dimensions)
    if characteristics.features:
        _require_clean_string_list(characteristics.features, "Characteristics.features")


def validate_dpp4fun(dpp: Dpp4Fun | None) -> None:
    """Validate a complete furniture DPP. Fail-fast; raises on first violation."""
    if dpp is None:
        raise DppValidationError("Dpp4Fun cannot be null")

    validate_dpp_core(dpp.coreDpp)
    validate_product_classification(dpp.classification)
    validate_characteristics(dpp.characteristics)
    validate_bill_of_materials(dpp.billOfMaterials)

    _validate_cross_rules(dpp)


def _validate_cross_rules(dpp: Dpp4Fun) -> None:
    category = dpp.category
    product_type = dpp.productType
    if _has_text(category) and _has_text(product_type):
        cat_lower = category.strip().lower()
        type_lower = product_type.strip().lower()  # type: ignore[union-attr]
        if cat_lower not in type_lower and type_lower not in cat_lower:
            raise DppValidationError(
                f"Cross-object validation: classification.category '{category}' "
                f"and characteristics.productType '{product_type}' appear inconsistent"
            )

    if dpp.documentation is None and _has_text(dpp.externalDocumentationLink):
        raise DppValidationError(
            "Cross-object validation: PassportMetadata has an externalDocumentationLink "
            "but no Documentation object is present in the DPP"
        )
