"""Immutable typed views for reusable D4.1 composite DataElement collections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Self

from ..core.model import DataElementCollection
from .profile import profile_definition
from .typed_model import CoreElement, _element_for, _ordered_children


@dataclass(frozen=True, slots=True)
class _Composite:
    element: DataElementCollection
    element_id: ClassVar[str]
    profile_path: ClassVar[str]
    field_aliases: ClassVar[dict[str, str]] = {}

    @classmethod
    def create(cls, **fields: object) -> Self:
        try:
            root = profile_definition(cls.profile_path)
        except KeyError:
            if fields:
                raise
            root = None
        children = tuple(
            _element_for(
                profile_definition(f"{cls.profile_path}.{cls.field_aliases.get(name, name)}"),
                value,
            )
            for name, value in fields.items()
            if value is not None
        )
        children = _ordered_children(cls.profile_path, children)
        return cls(
            element=DataElementCollection(
                element_id=root.element_id if root else cls.element_id,
                object_type="DataElementCollection",
                dictionary_reference=root.dictionary_reference if root else None,
                elements=children,
            )
        )

    @classmethod
    def from_element(cls, element: DataElementCollection) -> Self:
        return cls(element=element)

    def as_data_element(self) -> DataElementCollection:
        return self.element

    def field(self, name: str) -> CoreElement | None:
        definition = profile_definition(f"{self.profile_path}.{self.field_aliases.get(name, name)}")
        return next(
            (child for child in self.element.elements if child.element_id == definition.element_id),
            None,
        )

    def with_field(self, name: str, value: object | None) -> Self:
        definition = profile_definition(f"{self.profile_path}.{self.field_aliases.get(name, name)}")
        retained = tuple(
            child for child in self.element.elements if child.element_id != definition.element_id
        )
        children = retained if value is None else (*retained, _element_for(definition, value))
        children = _ordered_children(self.profile_path, children)
        return type(self)(element=self.element.with_updates(elements=children))


def _composite(name: str, element_id: str, profile_path: str) -> type[_Composite]:
    return type(
        name,
        (_Composite,),
        {"element_id": element_id, "profile_path": profile_path, "__module__": __name__},
    )


Accessory = _composite("Accessory", "accessory", "productRelationship.accessorySet[*]")
Address = _composite("Address", "address", "nameplate.contact.address")
CollectionMember = _composite(
    "CollectionMember", "collectionMember", "productRelationship.collectionMemberSet[*]"
)
Certificate = _composite("Certificate", "certificate", "durability.certificateSet[*]")
CarbonFootprintCalculation = _composite(
    "CarbonFootprintCalculation",
    "carbonFootprintCalculation",
    "carbonFootprint.carbonFootprintCalculationSet[*]",
)
DesignRecord = _composite("DesignRecord", "designRecord", "traceability.designRecordSet[*]")
Contact = _composite("Contact", "contact", "nameplate.contact")
Email = _composite("Email", "email", "nameplate.contact.email")
HealthIndicator = _composite("HealthIndicator", "indicator", "healthImpact.indicatorSet[*]")
Component = _composite("Component", "component", "billOfMaterials.componentSet[*]")
ManufacturingRecord = _composite(
    "ManufacturingRecord", "manufacturingRecord", "traceability.manufacturingRecordSet[*]"
)
Instruction = _composite("Instruction", "assemblyInstruction", "usage.assemblyInstructionSet[*]")
Indicator = _composite("Indicator", "indicator", "healthImpact.indicatorSet[*]")
Part = _composite("Part", "part", "billOfMaterials.partSet[*]")
Material = _composite("Material", "material", "billOfMaterials.materialSet[*]")
Policies = _composite("Policies", "policies", "rightOfEndUsers.policies")
Policies.field_aliases = {"permissions": "permissionSet", "prohibitions": "prohibitionSet"}
PostSaleService = _composite(
    "PostSaleService", "postSaleService", "rightOfEndUsers.postSaleServiceSet[*]"
)
ProductFunction = _composite("ProductFunction", "primaryFunction", "usage.primaryFunction")
TrackingRecord = _composite("TrackingRecord", "trackingRecord", "traceability.trackingRecordSet[*]")
Telephone = _composite("Telephone", "telephone", "nameplate.contact.telephone")
StandardAssessment = _composite(
    "StandardAssessment", "standardAssessment", "durability.standardSet[*]"
)
RepairRecord = _composite("RepairRecord", "repairRecord", "repairability.repairRecordSet[*]")
Scoring = _composite("Scoring", "scoring", "durability.scoringSet[*]")
