"""Semantic context used to restore information omitted by compressed JSON."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class DataElementKind(StrEnum):
    COLLECTION = "COLLECTION"
    SINGLE = "SINGLE"
    MULTI_VALUED = "MULTI_VALUED"
    MULTI_LANGUAGE = "MULTI_LANGUAGE"
    RELATED_RESOURCE = "RELATED_RESOURCE"


@dataclass(frozen=True)
class SemanticPath:
    """Immutable element path, including numeric positions in compressed arrays."""

    segments: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "segments", tuple(self.segments))
        if not self.segments or any(not part.strip() for part in self.segments):
            raise ValueError("semantic path segments must not be blank")

    @classmethod
    def of(cls, first: str, *remaining: str) -> SemanticPath:
        return cls((first, *remaining))

    def child(self, segment: str) -> SemanticPath:
        return SemanticPath((*self.segments, segment))


@dataclass(frozen=True)
class SemanticDefinition:
    """Authoritative metadata resolved for one complete semantic path.

    A resolved flag may be true with a ``None`` value to state that the
    semantic profile intentionally defines no metadata for that field.
    """

    kind: DataElementKind | None = None
    element_id: str | None = None
    dictionary_reference: str | None = None
    value_data_type: str | None = None
    dictionary_reference_resolved: bool = False
    value_data_type_resolved: bool = False

    def __post_init__(self) -> None:
        for name in ("element_id", "dictionary_reference", "value_data_type"):
            value = getattr(self, name)
            if value is not None and not value.strip():
                raise ValueError(f"{name} must not be blank")
        if self.dictionary_reference is not None and not self.dictionary_reference_resolved:
            object.__setattr__(self, "dictionary_reference_resolved", True)
        if self.value_data_type is not None and not self.value_data_type_resolved:
            object.__setattr__(self, "value_data_type_resolved", True)


class SemanticResolver(Protocol):
    """Optional source of semantics omitted from a compressed document."""

    def resolve(
        self, content_specification_ids: Sequence[str], path: SemanticPath
    ) -> SemanticDefinition | None: ...
