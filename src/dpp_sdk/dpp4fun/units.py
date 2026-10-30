"""Semantic units and finite quantities used by DPP4Fun Characteristics."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Protocol
from urllib.parse import urlparse

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


class UnitDimension(StrEnum):
    LENGTH = "LENGTH"
    MASS = "MASS"
    VOLUME = "VOLUME"


class SemanticUnit(Protocol):
    @property
    def symbol(self) -> str: ...

    @property
    def semantic_id(self) -> str: ...

    @property
    def dimension(self) -> UnitDimension: ...


class _Unit(StrEnum):
    @property
    def symbol(self) -> str:
        return self.value.split("|", 1)[0]

    @property
    def semantic_id(self) -> str:
        return self.value.split("|", 1)[1]

    @property
    def dimension(self) -> UnitDimension:
        return {
            "LengthUnit": UnitDimension.LENGTH,
            "MassUnit": UnitDimension.MASS,
            "VolumeUnit": UnitDimension.VOLUME,
        }[type(self).__name__]


class LengthUnit(_Unit):
    MILLIMETER = "mm|http://qudt.org/vocab/unit/MilliM"
    CENTIMETER = "cm|http://qudt.org/vocab/unit/CentiM"
    METER = "m|http://qudt.org/vocab/unit/M"
    INCH = "in|http://qudt.org/vocab/unit/IN"


class MassUnit(_Unit):
    KILOGRAM = "kg|http://qudt.org/vocab/unit/KiloGM"
    GRAM = "g|http://qudt.org/vocab/unit/GM"
    POUND = "lb|http://qudt.org/vocab/unit/LB_M"


class VolumeUnit(_Unit):
    CUBIC_METER = "m³|http://qudt.org/vocab/unit/M3"
    LITER = "L|http://qudt.org/vocab/unit/L"


KnownSemanticUnit = LengthUnit | MassUnit | VolumeUnit


def _known_unit(symbol: str, dimension: UnitDimension) -> KnownSemanticUnit | None:
    units: tuple[KnownSemanticUnit, ...] = (*LengthUnit, *MassUnit, *VolumeUnit)
    return next(
        (unit for unit in units if unit.symbol == symbol and unit.dimension == dimension),
        None,
    )


def _absolute_uri(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme:
        raise ValueError("semantic_id must be an absolute URI")
    return value


class CustomSemanticUnit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: Annotated[str, Field(min_length=1)]
    semantic_id: Annotated[str, AfterValidator(_absolute_uri)]
    dimension: UnitDimension

    @model_validator(mode="after")
    def non_blank_symbol(self) -> CustomSemanticUnit:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        return self


class Dpp4FunQuantity(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True, extra="forbid")

    value: float = Field(strict=True, allow_inf_nan=False)
    unit: LengthUnit | MassUnit | VolumeUnit | CustomSemanticUnit
    dimension: UnitDimension | None = None

    @model_validator(mode="after")
    def unit_dimension_matches(self) -> Dpp4FunQuantity:
        if self.dimension is not None and self.unit.dimension != self.dimension:
            raise ValueError("unit dimension does not match quantity dimension")
        return self
