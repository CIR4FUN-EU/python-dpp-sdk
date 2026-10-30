"""Immutable view of the reviewed, packaged DPP4Fun semantic profile."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.resources import files
from types import MappingProxyType
from typing import Any

from ..core.semantic import DataElementKind, SemanticDefinition, SemanticPath


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class Dpp4FunElementDefinition:
    path: str
    element_id: str
    object_type: str
    dictionary_reference: str | None
    value_data_type: str | None
    source_cardinality: Mapping[str, int | None] | None
    binding_occurrence: Mapping[str, int | None]
    unit_dimension: str | None
    unit_slot_path: str | None
    applies_to: tuple[str, ...]
    aliases: tuple[str, ...]
    source: Mapping[str, Any]
    java_concept: str
    source_references: tuple[Mapping[str, Any], ...]
    validation_rules: tuple[str, ...]
    repeated_item_policy: Mapping[str, Any] | None
    resolution_status: str
    conflict_resolution: Mapping[str, Any] | None
    explicit_requiredness: str


@dataclass(frozen=True, slots=True)
class Dpp4FunSemanticProfile:
    metadata: Mapping[str, Any]
    definitions: tuple[Dpp4FunElementDefinition, ...]
    variants: Mapping[str, str]
    conflicts: tuple[Mapping[str, Any], ...]
    by_path: Mapping[str, tuple[Dpp4FunElementDefinition, ...]]

    @classmethod
    def load(cls) -> Dpp4FunSemanticProfile:
        resource = files("dpp_sdk.dpp4fun").joinpath("semantic/dpp4fun-semantic-profile-v1.json")
        raw = json.loads(resource.read_text(encoding="utf-8"))
        definitions = tuple(
            Dpp4FunElementDefinition(
                path=item["path"],
                element_id=item["elementId"],
                object_type=item["objectType"],
                dictionary_reference=item["dictionaryReference"],
                value_data_type=item["valueDataType"],
                source_cardinality=_freeze(item["sourceCardinality"]),
                binding_occurrence=_freeze(item["bindingOccurrence"]),
                unit_dimension=item["unitDimension"],
                unit_slot_path=item["unitSlotPath"],
                applies_to=tuple(item["appliesTo"]),
                aliases=tuple(item["aliases"]),
                source=_freeze(item["source"]),
                java_concept=item["javaConcept"],
                source_references=tuple(_freeze(ref) for ref in item["sourceReferences"]),
                validation_rules=tuple(item["validationRules"]),
                repeated_item_policy=_freeze(item["repeatedItemPolicy"]),
                resolution_status=item["resolutionStatus"],
                conflict_resolution=_freeze(item["conflictResolution"]),
                explicit_requiredness=item["explicitRequiredness"],
            )
            for item in raw["definitions"]
        )
        grouped: dict[str, list[Dpp4FunElementDefinition]] = {}
        for definition in definitions:
            grouped.setdefault(definition.path, []).append(definition)
        return cls(
            metadata=_freeze({key: value for key, value in raw.items() if key != "definitions"}),
            definitions=definitions,
            variants=MappingProxyType(dict(raw["variantContentSpecificationIds"])),
            conflicts=tuple(_freeze(item) for item in raw["conflictDecisions"]),
            by_path=MappingProxyType({key: tuple(items) for key, items in grouped.items()}),
        )

    @property
    def root_element_ids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                definition.element_id
                for definition in self.definitions
                if "." not in definition.path
            )
        )


DPP4FUN_PROFILE = Dpp4FunSemanticProfile.load()


def profile_definition(path: str, *, variant: str | None = None) -> Dpp4FunElementDefinition:
    candidates = DPP4FUN_PROFILE.by_path.get(path, ())
    if variant is not None:
        key = f"characteristics-{variant}"
        candidates = tuple(item for item in candidates if key in item.applies_to)
    elif len(candidates) > 1:
        candidates = tuple(item for item in candidates if "general" in item.applies_to)
    if len(candidates) != 1:
        raise KeyError(f"No unique DPP4Fun profile definition for {path!r} (variant={variant!r})")
    return candidates[0]


class Dpp4FunSemanticResolver:
    """Resolve only metadata explicitly present in the selected DPP4Fun profile."""

    def resolve(
        self, content_specification_ids: Sequence[str], path: SemanticPath
    ) -> SemanticDefinition | None:
        ids = set(content_specification_ids)
        applicability = (
            {"general"} if DPP4FUN_PROFILE.metadata["contentSpecificationId"] in ids else set()
        )
        applicability.update(
            f"characteristics-{variant}"
            for variant, identifier in DPP4FUN_PROFILE.variants.items()
            if identifier in ids
        )
        match = next(
            (
                definition
                for definition in DPP4FUN_PROFILE.definitions
                if definition.applies_to
                and applicability.intersection(definition.applies_to)
                and _profile_path_matches(definition.path, path.segments)
            ),
            None,
        )
        if match is None:
            return None
        item_pattern = (
            match.repeated_item_policy.get("elementIdPattern")
            if match.repeated_item_policy
            else None
        )
        element_id = match.element_id
        if item_pattern:
            index = next(int(segment) for segment in path.segments if segment.isdecimal())
            element_id = item_pattern % index
        kind = {
            "DataElementCollection": DataElementKind.COLLECTION,
            "SingleValuedDataElement": DataElementKind.SINGLE,
            "MultiValuedDataElement": DataElementKind.MULTI_VALUED,
            "MultiLanguageDataElement": DataElementKind.MULTI_LANGUAGE,
            "RelatedResource": DataElementKind.RELATED_RESOURCE,
        }[match.object_type]
        return SemanticDefinition(
            kind=kind,
            element_id=element_id,
            dictionary_reference=match.dictionary_reference,
            value_data_type=match.value_data_type,
            dictionary_reference_resolved=match.resolution_status
            not in {"UNRESOLVED_DICTIONARY_REFERENCE", "RESOLVED_WITHOUT_DICTIONARY_REFERENCE"},
            value_data_type_resolved=match.resolution_status != "UNRESOLVED_VALUE_DATA_TYPE",
        )


def _profile_path_matches(pattern: str, segments: tuple[str, ...]) -> bool:
    expected = pattern.split(".")
    actual_index = 0
    for segment in expected:
        if actual_index >= len(segments):
            return False
        if segment.endswith("[*]"):
            if segment[:-3] != segments[actual_index] or actual_index + 1 >= len(segments):
                return False
            if not segments[actual_index + 1].isdecimal():
                return False
            actual_index += 2
        elif segment != segments[actual_index]:
            return False
        else:
            actual_index += 1
    return actual_index == len(segments)
