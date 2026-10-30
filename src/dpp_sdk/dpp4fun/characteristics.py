"""The six source-specific D4.1 Characteristics profile variants."""

from enum import StrEnum

from .typed_model import ProfiledAspect


class Dpp4FunProductVariant(StrEnum):
    CHAIR = "chair"
    CRIB = "crib"
    FABRIC = "fabric"
    LOCKER = "locker"
    PARTICLE_BOARD = "particleBoard"
    SOFA = "sofa"


class ChairCharacteristics(ProfiledAspect):
    element_id = "characteristics"
    variant = Dpp4FunProductVariant.CHAIR


class CribCharacteristics(ProfiledAspect):
    element_id = "characteristics"
    variant = Dpp4FunProductVariant.CRIB
    field_aliases = {"mattressIncluded": "matelasIncluded"}


class FabricCharacteristics(ProfiledAspect):
    element_id = "characteristics"
    variant = Dpp4FunProductVariant.FABRIC


class LockerCharacteristics(ProfiledAspect):
    element_id = "characteristics"
    variant = Dpp4FunProductVariant.LOCKER


class ParticleBoardCharacteristics(ProfiledAspect):
    element_id = "characteristics"
    variant = Dpp4FunProductVariant.PARTICLE_BOARD


class SofaCharacteristics(ProfiledAspect):
    element_id = "characteristics"
    variant = Dpp4FunProductVariant.SOFA


FurnitureCharacteristics = (
    ChairCharacteristics
    | CribCharacteristics
    | FabricCharacteristics
    | LockerCharacteristics
    | ParticleBoardCharacteristics
    | SofaCharacteristics
)
