"""Furniture-specific DPP models (port of ``dppsdk.dpp4fun.model``).

Frozen Pydantic v2 models that double as JSON transport payloads. List fields
(``tags``, ``features``, BOM lists) default to ``[]`` and are always emitted —
mirroring the Java domain objects, which store empty lists rather than null, so
the wire shape carries ``[]`` not ``null``.

``Dimensions`` requires all three of width/height/depth (the Java builder rejects
any missing value, and the mapper only succeeds when all are present).

Only structural rules are enforced here; semantic rules live in
:mod:`dpp_sdk.dpp4fun.validation`.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..core.model import (
    Dpp,
    DppCore,
    NonBlankStr,
    OptionalStr,
    _Base,
)

# A non-negative float, used for dimensions, weight, and material portion.
NonNegativeFloat = Annotated[float, Field(ge=0)]


class Dimensions(_Base):
    width: NonNegativeFloat
    height: NonNegativeFloat
    depth: NonNegativeFloat
    unit: OptionalStr = None


class Material(_Base):
    name: NonBlankStr
    mandatory: bool = False
    portion: NonNegativeFloat = 0.0
    reference: OptionalStr = None


class Component(_Base):
    name: NonBlankStr
    reference: OptionalStr = None


class Part(_Base):
    name: NonBlankStr
    mandatory: bool = False
    reference: OptionalStr = None


class BillOfMaterials(_Base):
    materials: list[Material] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    parts: list[Part] = Field(default_factory=list)


class ProductClassification(_Base):
    sector: NonBlankStr
    group: OptionalStr = None
    category: NonBlankStr
    subCategory: OptionalStr = None
    tags: list[str] = Field(default_factory=list)


class Characteristics(_Base):
    productName: NonBlankStr
    description: OptionalStr = None
    brand: OptionalStr = None
    productType: OptionalStr = None
    dimensions: Dimensions | None = None
    weight: NonNegativeFloat | None = None
    color: OptionalStr = None
    features: list[str] = Field(default_factory=list)


class Dpp4Fun(Dpp):
    """Complete furniture Digital Product Passport (port of ``Dpp4Fun``)."""

    coreDpp: DppCore
    classification: ProductClassification
    characteristics: Characteristics
    billOfMaterials: BillOfMaterials | None = None

    @property
    def passport_type(self) -> str:
        return "Dpp4Fun Furniture"

    # --- read-through accessors (classification) --------------------------------
    @property
    def sector(self) -> str:
        return self.classification.sector

    @property
    def group(self) -> str | None:
        return self.classification.group

    @property
    def category(self) -> str:
        return self.classification.category

    @property
    def subCategory(self) -> str | None:
        return self.classification.subCategory

    @property
    def tags(self) -> list[str]:
        return self.classification.tags

    # --- read-through accessors (characteristics) -------------------------------
    @property
    def productName(self) -> str:
        return self.characteristics.productName

    @property
    def description(self) -> str | None:
        return self.characteristics.description

    @property
    def brand(self) -> str | None:
        return self.characteristics.brand

    @property
    def productType(self) -> str | None:
        return self.characteristics.productType

    @property
    def dimensions(self) -> Dimensions | None:
        return self.characteristics.dimensions

    @property
    def weight(self) -> float | None:
        return self.characteristics.weight

    @property
    def color(self) -> str | None:
        return self.characteristics.color

    @property
    def features(self) -> list[str]:
        return self.characteristics.features
