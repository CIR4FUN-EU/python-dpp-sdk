"""Typed immutable DPP4Fun views over one canonical core passport."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, ClassVar, Self, TypeAlias, cast

from pydantic import BaseModel, ConfigDict

from ..core.model import (
    DataElement,
    DataElementCollection,
    DigitalProductPassport,
    DppHeader,
    MultiLanguageDataElement,
    MultiLanguageValue,
    MultiValuedDataElement,
    RelatedResource,
    SingleValuedDataElement,
)
from .profile import DPP4FUN_PROFILE, Dpp4FunElementDefinition, profile_definition
from .units import CustomSemanticUnit, Dpp4FunQuantity, UnitDimension, _known_unit

CoreElement: TypeAlias = (
    DataElementCollection
    | SingleValuedDataElement
    | MultiValuedDataElement
    | MultiLanguageDataElement
    | RelatedResource
)


def _children(element: DataElementCollection) -> tuple[CoreElement, ...]:
    return element.elements


def _ordered_children(
    path: str, children: Sequence[CoreElement], *, variant: str | None = None
) -> tuple[CoreElement, ...]:
    definitions = [
        definition
        for definition in DPP4FUN_PROFILE.definitions
        if definition.path.rpartition(".")[0] == path
        and (variant is None or f"characteristics-{variant}" in definition.applies_to)
    ]
    order = {definition.element_id: index for index, definition in enumerate(definitions)}
    return tuple(
        child
        for _, child in sorted(
            enumerate(children),
            key=lambda pair: (order.get(pair[1].element_id or "", len(order)), pair[0]),
        )
    )


def _element_for(definition: Dpp4FunElementDefinition, value: object) -> CoreElement:
    if isinstance(value, DataElement):
        if value.object_type != definition.object_type:
            raise TypeError(
                f"{definition.path} requires {definition.object_type}, got {value.object_type}"
            )
        element = cast(CoreElement, value)
        return element
    if definition.object_type == "SingleValuedDataElement":
        datatype = definition.value_data_type
        if datatype == "xsd:string" and not isinstance(value, str):
            raise TypeError(f"{definition.path} requires a string")
        if datatype == "xsd:boolean" and not isinstance(value, bool):
            raise TypeError(f"{definition.path} requires a boolean")
        if datatype == "xsd:integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise TypeError(f"{definition.path} requires an integer")
        if datatype == "xsd:double":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"{definition.path} requires a number")
            value = float(value)
        if datatype in {"xsd:anyURI", "xsd:dateTime"} and not isinstance(value, str):
            raise TypeError(f"{definition.path} requires a string representation")
        return SingleValuedDataElement(
            element_id=definition.element_id,
            object_type="SingleValuedDataElement",
            dictionary_reference=definition.dictionary_reference,
            value_data_type=definition.value_data_type,
            value=value,
        )
    if definition.object_type == "MultiValuedDataElement":
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise TypeError(f"{definition.path} requires an ordered sequence of DataElements")
        item_definitions = DPP4FUN_PROFILE.by_path.get(f"{definition.path}[*]", ())
        item_definition = item_definitions[0] if item_definitions else None
        if item_definition and item_definition.object_type == "SingleValuedDataElement":
            value = tuple(_element_for(item_definition, item) for item in value)
        if item_definitions and item_definitions[0].repeated_item_policy:
            pattern = item_definitions[0].repeated_item_policy.get("elementIdPattern")
            if pattern:
                normalized: list[CoreElement] = []
                for index, item in enumerate(value):
                    if not isinstance(item, DataElement):
                        raise TypeError(f"{definition.path} items must be DataElements")
                    normalized.append(
                        cast(CoreElement, item.with_updates(element_id=pattern % index))
                    )
                value = normalized
        return MultiValuedDataElement(
            element_id=definition.element_id,
            object_type="MultiValuedDataElement",
            dictionary_reference=definition.dictionary_reference,
            value=tuple(value),
        )
    if definition.object_type == "MultiLanguageDataElement":
        if not isinstance(value, Mapping) or any(
            not isinstance(language, str) or not isinstance(text, str)
            for language, text in value.items()
        ):
            raise TypeError(f"{definition.path} requires a language-to-text mapping")
        return MultiLanguageDataElement(
            element_id=definition.element_id,
            object_type="MultiLanguageDataElement",
            dictionary_reference=definition.dictionary_reference,
            value=tuple(
                MultiLanguageValue(value=text, language=language)
                for language, text in value.items()
            ),
        )
    if definition.object_type == "DataElementCollection":
        if isinstance(value, Mapping):
            entries = tuple(value.values())
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            entries = tuple(value)
        else:
            raise TypeError(
                f"{definition.path} requires DataElements or a mapping of child elements"
            )
        if any(not isinstance(entry, DataElement) for entry in entries):
            raise TypeError(f"{definition.path} children must be DataElements")
        return DataElementCollection(
            element_id=definition.element_id,
            object_type="DataElementCollection",
            dictionary_reference=definition.dictionary_reference,
            elements=entries,
        )
    raise TypeError(f"Unsupported profile DataElement kind {definition.object_type!r}")


class ProfiledAspect(BaseModel):
    """Immutable typed view over a profile collection, with unknown children retained."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True, extra="forbid")

    element: DataElementCollection
    element_id: ClassVar[str] = "characteristics"
    variant: ClassVar[Any | None] = None
    field_aliases: ClassVar[dict[str, str]] = {}

    @classmethod
    def create(cls, **fields: object) -> Self:
        root_definition = profile_definition(
            cls.element_id, variant=getattr(cls.variant, "value", None)
        )
        children = tuple(
            _element_for(
                profile_definition(
                    f"{cls.element_id}.{cls.field_aliases.get(name, name)}",
                    variant=getattr(cls.variant, "value", None),
                ),
                value,
            )
            for name, value in fields.items()
            if value is not None
        )
        children = _ordered_children(
            cls.element_id, children, variant=getattr(cls.variant, "value", None)
        )
        element = DataElementCollection(
            element_id=root_definition.element_id,
            object_type="DataElementCollection",
            dictionary_reference=root_definition.dictionary_reference,
            elements=children,
        )
        return cls(element=element)

    @classmethod
    def from_element(cls, element: DataElementCollection) -> Self:
        if element.element_id != cls.element_id:
            raise ValueError(f"expected aspect {cls.element_id!r}, got {element.element_id!r}")
        return cls(element=element)

    def with_field(self, name: str, value: object | None) -> Self:
        path = f"{self.element_id}.{self.field_aliases.get(name, name)}"
        definition = profile_definition(path, variant=getattr(self.variant, "value", None))
        retained = tuple(
            child for child in _children(self.element) if child.element_id != definition.element_id
        )
        children = retained if value is None else (*retained, _element_for(definition, value))
        children = _ordered_children(
            self.element_id, children, variant=getattr(self.variant, "value", None)
        )
        return type(self)(element=self.element.with_updates(elements=children))

    def field(self, name: str) -> CoreElement | None:
        definition = profile_definition(
            f"{self.element_id}.{self.field_aliases.get(name, name)}",
            variant=getattr(self.variant, "value", None),
        )
        return next(
            (child for child in self.element.elements if child.element_id == definition.element_id),
            None,
        )

    def as_data_element(self) -> DataElementCollection:
        return self.element

    def with_quantity(self, name: str, quantity: Dpp4FunQuantity) -> Self:
        definition = profile_definition(
            f"{self.element_id}.{name}", variant=getattr(self.variant, "value", None)
        )
        if definition.unit_dimension is None or definition.unit_slot_path is None:
            raise ValueError(f"{name!r} is not a quantity field in the DPP4Fun profile")
        expected_dimension = UnitDimension(definition.unit_dimension.upper())
        if quantity.unit.dimension != expected_dimension:
            raise ValueError(
                f"DPP4FUN_UNIT_DIMENSION_MISMATCH: {name} requires {expected_dimension.value}"
            )
        if isinstance(quantity.unit, CustomSemanticUnit):
            raise ValueError("custom semantic units cannot be preserved in DPP4Fun unit slots")
        unit_slot = definition.unit_slot_path
        current_unit = next(
            (child for child in self.element.elements if child.element_id == unit_slot), None
        )
        if (
            current_unit is not None
            and isinstance(current_unit, SingleValuedDataElement)
            and current_unit.value != quantity.unit.symbol
        ):
            raise ValueError(f"DPP4FUN_UNIT_SLOT_CONFLICT: {unit_slot} already has another unit")
        return self.with_field(name, quantity.value).with_field(unit_slot, quantity.unit.symbol)

    def quantity(self, name: str) -> Dpp4FunQuantity | None:
        definition = profile_definition(
            f"{self.element_id}.{name}", variant=getattr(self.variant, "value", None)
        )
        if definition.unit_dimension is None or definition.unit_slot_path is None:
            return None
        by_id = {child.element_id: child for child in self.element.elements}
        value = by_id.get(definition.element_id)
        unit = by_id.get(definition.unit_slot_path)
        if (
            not isinstance(value, SingleValuedDataElement)
            or not isinstance(value.value, (int, float))
            or isinstance(value.value, bool)
        ):
            return None
        if not isinstance(unit, SingleValuedDataElement) or not isinstance(unit.value, str):
            return None
        resolved = _known_unit(unit.value, UnitDimension(definition.unit_dimension.upper()))
        if resolved is None:
            return None
        return Dpp4FunQuantity(value=float(value.value), unit=resolved)


class Nameplate(ProfiledAspect):
    element_id = "nameplate"


class HealthImpact(ProfiledAspect):
    element_id = "healthImpact"


class EnvironmentalImpact(ProfiledAspect):
    element_id = "environmentalImpact"


class Durability(ProfiledAspect):
    element_id = "durability"


class CarbonFootprint(ProfiledAspect):
    element_id = "carbonFootprint"


class BillOfMaterials(ProfiledAspect):
    element_id = "billOfMaterials"


class Refurbishment(ProfiledAspect):
    element_id = "refurbishment"


class Recyclability(ProfiledAspect):
    element_id = "recyclability"


class ProductRelationship(ProfiledAspect):
    element_id = "productRelationship"


class Remanufacturing(ProfiledAspect):
    element_id = "remanufacturing"


class Reliability(ProfiledAspect):
    element_id = "reliability"


class Repairability(ProfiledAspect):
    element_id = "repairability"


class Reusability(ProfiledAspect):
    element_id = "reusability"


class WasteManagement(ProfiledAspect):
    element_id = "wasteManagement"


class Usage(ProfiledAspect):
    element_id = "usage"


class Upgradability(ProfiledAspect):
    element_id = "upgradability"


class Traceability(ProfiledAspect):
    element_id = "traceability"


class Safety(ProfiledAspect):
    element_id = "safety"


class RightOfEndUsers(ProfiledAspect):
    element_id = "rightOfEndUsers"


class Dpp4Fun(BaseModel):
    """Typed facade whose sole passport state is one immutable core aggregate."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True, extra="forbid")

    passport: DigitalProductPassport
    SCHEMA_VERSION: ClassVar[str] = "1.0"

    @classmethod
    def from_passport(cls, passport: DigitalProductPassport) -> Self:
        seen: set[str] = set()
        for element in passport.data_elements:
            if element.element_id in DPP4FUN_PROFILE.root_element_ids:
                if element.element_id in seen:
                    raise ValueError(f"duplicate reserved DPP4Fun aspect {element.element_id!r}")
                if not isinstance(element, DataElementCollection):
                    raise ValueError(
                        f"reserved DPP4Fun aspect {element.element_id!r} must be a collection"
                    )
                seen.add(element.element_id or "")
        selected_variants = [
            variant_id
            for variant_id in DPP4FUN_PROFILE.variants.values()
            if variant_id in passport.dpp_header.content_specification_ids
        ]
        if len(selected_variants) > 1:
            raise ValueError("a Dpp4Fun passport can select only one Characteristics variant")
        characteristics = next(
            (
                element
                for element in passport.data_elements
                if element.element_id == "characteristics"
            ),
            None,
        )
        if characteristics is not None and not isinstance(characteristics, DataElementCollection):
            raise ValueError("reserved Dpp4Fun Characteristics must be a collection")
        return cls(passport=passport)

    @classmethod
    def create(
        cls,
        header: DppHeader,
        *aspects: ProfiledAspect,
        extensions: Sequence[CoreElement] = (),
    ) -> Self:
        selected = [aspect.as_data_element() for aspect in aspects]
        ids = [element.element_id for element in selected]
        if len(ids) != len(set(ids)):
            raise ValueError("Dpp4Fun aspects must have unique element IDs")
        if any(element.element_id in DPP4FUN_PROFILE.root_element_ids for element in extensions):
            raise ValueError("extensions cannot replace a reserved Dpp4Fun aspect")
        variant_ids = {
            DPP4FUN_PROFILE.variants[aspect.variant.value]
            for aspect in aspects
            if aspect.variant is not None
        }
        reserved_ids = set(DPP4FUN_PROFILE.variants.values()) | {"DPP4FUN_COMMON_V1"}
        specs = tuple(spec for spec in header.content_specification_ids if spec not in reserved_ids)
        has_catalog_aspect = any(
            element.element_id in DPP4FUN_PROFILE.root_element_ids for element in selected
        )
        if has_catalog_aspect:
            specs = tuple(dict.fromkeys((*specs, "DPP4FUN_COMMON_V1", *variant_ids)))
        header_data = header.model_dump(mode="json", by_alias=True)
        header_data["contentSpecificationIds"] = specs
        header_data["dppSchemaVersion"] = cls.SCHEMA_VERSION
        header_data["lastUpdated"] = header.last_updated or datetime.now(UTC)
        header = DppHeader.model_validate(header_data)
        order = {
            element_id: index for index, element_id in enumerate(DPP4FUN_PROFILE.root_element_ids)
        }
        elements = tuple(
            sorted(selected, key=lambda element: order.get(element.element_id or "", len(order)))
        ) + tuple(extensions)
        return cls.from_passport(DigitalProductPassport(dpp_header=header, data_elements=elements))

    def as_digital_product_passport(self) -> DigitalProductPassport:
        return self.passport

    @property
    def header(self) -> DppHeader:
        return self.passport.dpp_header

    def get_aspect(self, element_id: str) -> DataElementCollection | None:
        value = self.passport.find_data_element((element_id,))
        if value is None:
            return None
        if not isinstance(value, DataElementCollection):
            raise ValueError(f"reserved Dpp4Fun aspect {element_id!r} must be a collection")
        return value

    def typed_aspect(self, aspect_type: type[ProfiledAspect]) -> ProfiledAspect | None:
        element = self.get_aspect(aspect_type.element_id)
        return None if element is None else aspect_type.from_element(element)

    def selected_characteristics(self) -> ProfiledAspect | None:
        from .characteristics import (
            ChairCharacteristics,
            CribCharacteristics,
            Dpp4FunProductVariant,
            FabricCharacteristics,
            LockerCharacteristics,
            ParticleBoardCharacteristics,
            SofaCharacteristics,
        )

        selected = {
            DPP4FUN_PROFILE.variants[variant.value]: variant
            for variant in Dpp4FunProductVariant
            if DPP4FUN_PROFILE.variants[variant.value] in self.header.content_specification_ids
        }
        if not selected:
            return None
        variant = next(iter(selected.values()))
        types = {
            Dpp4FunProductVariant.CHAIR: ChairCharacteristics,
            Dpp4FunProductVariant.CRIB: CribCharacteristics,
            Dpp4FunProductVariant.FABRIC: FabricCharacteristics,
            Dpp4FunProductVariant.LOCKER: LockerCharacteristics,
            Dpp4FunProductVariant.PARTICLE_BOARD: ParticleBoardCharacteristics,
            Dpp4FunProductVariant.SOFA: SofaCharacteristics,
        }
        return self.typed_aspect(types[variant])

    def with_updates(
        self,
        *,
        header: DppHeader | None = None,
        aspects: Sequence[ProfiledAspect] = (),
    ) -> Self:
        aspect_ids = [aspect.element_id for aspect in aspects]
        if len(aspect_ids) != len(set(aspect_ids)):
            raise ValueError("Dpp4Fun aspect updates must have unique element IDs")
        replacements = {aspect.element_id: aspect.as_data_element() for aspect in aspects}
        current = list(self.passport.data_elements)
        for element_id, replacement in replacements.items():
            for index, old in enumerate(current):
                if old.element_id == element_id:
                    current[index] = replacement
                    break
            else:
                current.append(replacement)
        order = {
            element_id: index for index, element_id in enumerate(DPP4FUN_PROFILE.root_element_ids)
        }
        current.sort(key=lambda element: order.get(element.element_id or "", len(order)))
        updated_header = header or self.passport.dpp_header
        if any(aspect.variant is not None for aspect in aspects):
            known_variant_ids = set(DPP4FUN_PROFILE.variants.values())
            selected_ids = tuple(
                DPP4FUN_PROFILE.variants[aspect.variant.value]
                for aspect in aspects
                if aspect.variant is not None
            )
            specs = (
                tuple(
                    spec
                    for spec in updated_header.content_specification_ids
                    if spec not in known_variant_ids
                )
                + selected_ids
            )
            updated_header = updated_header.with_updates(
                content_specification_ids=tuple(dict.fromkeys(specs))
            )
        header_data = updated_header.model_dump(mode="json", by_alias=True)
        header_data["dppSchemaVersion"] = self.SCHEMA_VERSION
        header_data["lastUpdated"] = updated_header.last_updated or datetime.now(UTC)
        updated_header = DppHeader.model_validate(header_data)
        passport = self.passport.with_updates(
            dpp_header=updated_header,
            elements=tuple(current),
        )
        return type(self).from_passport(passport)
