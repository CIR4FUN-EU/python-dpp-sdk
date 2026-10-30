"""Core DPP domain models (port of ``dppsdk.core.model``).

Each class is a frozen Pydantic v2 model that doubles as the JSON transport
payload: ``UUID`` serializes to its canonical string and ``date`` to ISO
``yyyy-MM-dd``, matching the Java ``*Payload`` POJOs exactly. Python attributes
use snake_case and field aliases preserve the canonical camelCase JSON keys.

Only *structural* rules (the checks performed by the Java ``Builder.build()``
methods) are enforced here on construction. *Semantic* rules (e.g. "no future
dates", cross-object consistency) live in :mod:`dpp_sdk.core.validation` and are
applied explicitly, preserving the Java behavior where ``fromJson`` is lenient.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal, NoReturn, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from .semantic import SemanticPath


class _Base(BaseModel):
    """Shared config: immutable, name-or-alias population, reject unknown keys.

    ``extra='forbid'`` mirrors Jackson's default of failing on unknown
    properties in ``Dpp4FunJsonCodec``.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")

    def with_updates(self, **changes: object) -> Self:
        """Return a structurally revalidated immutable copy with ``changes``."""
        fields = type(self).model_fields
        aliases = {field.alias: name for name, field in fields.items() if field.alias}
        payload = self.model_dump(mode="python", by_alias=True)
        for name, value in changes.items():
            field_name = aliases.get(name, name)
            if field_name not in fields:
                payload[name] = value
            else:
                alias = fields[field_name].alias or field_name
                payload[alias] = value
        return type(self).model_validate(payload)


class Granularity(StrEnum):
    """Passport granularity, with the canonical lowercase JSON values."""

    MODEL = "model"
    BATCH = "batch"
    ITEM = "item"


class _FrozenDict(dict[str, Any]):
    """A JSON object that prevents mutation after a value model is constructed."""

    def __setitem__(self, key: str, value: Any) -> NoReturn:
        raise TypeError("JSON value is immutable")

    def __delitem__(self, key: str) -> NoReturn:
        raise TypeError("JSON value is immutable")

    def clear(self) -> NoReturn:
        raise TypeError("JSON value is immutable")

    def pop(self, key: str, default: Any = ...) -> Any:
        raise TypeError("JSON value is immutable")

    def popitem(self) -> NoReturn:
        raise TypeError("JSON value is immutable")

    def setdefault(self, key: str, default: Any = None) -> Any:
        raise TypeError("JSON value is immutable")

    def update(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise TypeError("JSON value is immutable")

    # Mypy models dict's `|=` signatures inconsistently with its `|` overloads.
    def __ior__(self, other: Any) -> Self:  # type: ignore[override,misc]
        raise TypeError("JSON value is immutable")


def _freeze_json_value(value: Any, active: set[int] | None = None) -> Any:
    """Copy JSON-compatible values into recursively immutable containers."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("value must be JSON-compatible")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("value must be JSON-compatible")
        return value

    active = set() if active is None else active
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise ValueError("value must not contain cycles")
        if any(not isinstance(key, str) for key in value):
            raise ValueError("value object keys must be strings")
        active.add(identity)
        try:
            return _FrozenDict(
                {key: _freeze_json_value(item, active) for key, item in value.items()}
            )
        finally:
            active.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise ValueError("value must not contain cycles")
        active.add(identity)
        try:
            return tuple(_freeze_json_value(item, active) for item in value)
        finally:
            active.remove(identity)
    raise ValueError("value must be JSON-compatible")


class DataElement(_Base):
    """Common identity fields and FULL-payload subtype selection."""

    element_id: str | None = Field(default=None, alias="elementId")
    object_type: str = Field(alias="objectType")
    dictionary_reference: str | None = Field(default=None, alias="dictionaryReference")


class DataElementCollection(DataElement):
    """Ordered nested DataElements (the FULL JSON field is ``elements``)."""

    object_type: Literal["DataElementCollection"] = Field(
        default="DataElementCollection", alias="objectType"
    )
    elements: tuple[_DataElementUnion, ...] = Field(default_factory=tuple)


class SingleValuedDataElement(DataElement):
    """One JSON-compatible value and its optional declared datatype."""

    object_type: Literal["SingleValuedDataElement"] = Field(
        default="SingleValuedDataElement", alias="objectType"
    )
    value: Any = None
    value_data_type: str | None = Field(default=None, alias="valueDataType")

    @field_validator("value", mode="before")
    @classmethod
    def freeze_value(cls, value: Any) -> Any:
        return _freeze_json_value(value)

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return (
            self.element_id == other.element_id
            and self.object_type == other.object_type
            and self.dictionary_reference == other.dictionary_reference
            and self.value_data_type == other.value_data_type
            and _json_values_equal(self.value, other.value)
        )

    def __hash__(self) -> int:
        return hash(
            (
                type(self),
                self.element_id,
                self.object_type,
                self.dictionary_reference,
                self.value_data_type,
                _json_value_hash(self.value),
            )
        )


def _json_values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float, Decimal)) and isinstance(right, (int, float, Decimal)):
        return Decimal(str(left)) == Decimal(str(right))
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return left.keys() == right.keys() and all(
            _json_values_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(
            _json_values_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return type(left) is type(right) and left == right


def _json_value_hash(value: Any) -> int:
    if isinstance(value, bool):
        return hash((bool, value))
    if isinstance(value, (int, float, Decimal)):
        return hash(("number", Decimal(str(value)).normalize()))
    if isinstance(value, Mapping):
        return hash(frozenset((key, _json_value_hash(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return hash(tuple(_json_value_hash(item) for item in value))
    return hash((type(value), value))


class MultiValuedDataElement(DataElement):
    """Ordered repeated DataElements and their optional common datatype."""

    object_type: Literal["MultiValuedDataElement"] = Field(
        default="MultiValuedDataElement", alias="objectType"
    )
    value_data_type: str | None = Field(default=None, alias="valueDataType")
    value: tuple[_DataElementUnion, ...] = Field(default_factory=tuple)


class MultiLanguageValue(_Base):
    """A nullable text value and language tag, as structurally modeled by Java."""

    value: str | None = None
    language: str | None = None


class MultiLanguageDataElement(DataElement):
    """Ordered language-specific values in the FULL JSON ``value`` array."""

    object_type: Literal["MultiLanguageDataElement"] = Field(
        default="MultiLanguageDataElement", alias="objectType"
    )
    value: tuple[MultiLanguageValue, ...] = Field(default_factory=tuple)


class RelatedResource(DataElement):
    """Resource metadata associated with a data element."""

    object_type: Literal["RelatedResource"] = Field(default="RelatedResource", alias="objectType")
    content_type: str | None = Field(default=None, alias="contentType")
    url: str | None = None
    language: str | None = None
    resource_title: str | None = Field(default=None, alias="resourceTitle")


_DataElementUnion = Annotated[
    DataElementCollection
    | SingleValuedDataElement
    | MultiValuedDataElement
    | MultiLanguageDataElement
    | RelatedResource,
    Field(discriminator="object_type"),
]


for _element_model in (
    DataElementCollection,
    SingleValuedDataElement,
    MultiValuedDataElement,
    MultiLanguageDataElement,
    RelatedResource,
):
    _element_model.model_rebuild(_types_namespace={"_DataElementUnion": _DataElementUnion})


class DppHeader(_Base):
    """Optional header metadata grouped by the SDK for the passport root."""

    digital_product_passport_id: str | None = Field(default=None, alias="digitalProductPassportId")
    unique_product_identifier: str | None = Field(default=None, alias="uniqueProductIdentifier")
    granularity: Granularity | None = None
    dpp_schema_version: str | None = Field(default=None, alias="dppSchemaVersion")
    dpp_status: str | None = Field(default=None, alias="dppStatus")
    last_updated: AwareDatetime | None = Field(default=None, alias="lastUpdated")
    economic_operator_id: str | None = Field(default=None, alias="economicOperatorId")
    facility_id: str | None = Field(default=None, alias="facilityId")
    content_specification_ids: tuple[str, ...] = Field(
        default_factory=tuple, alias="contentSpecificationIds"
    )


class DigitalProductPassport(_Base):
    """Canonical passport aggregate with one required header and ordered elements."""

    dpp_header: DppHeader
    data_elements: tuple[_DataElementUnion, ...] = Field(default_factory=tuple, alias="elements")

    def find_data_element(self, path: Sequence[str] | SemanticPath) -> _DataElementUnion | None:
        """Find an element by its ID path or numeric child indexes."""
        segments = path.segments if isinstance(path, SemanticPath) else path
        if (
            isinstance(segments, str)
            or not segments
            or any(not segment.strip() for segment in segments)
        ):
            raise ValueError("path must contain non-blank segments")

        current = next(
            (element for element in self.data_elements if element.element_id == segments[0]), None
        )
        for segment in segments[1:]:
            if isinstance(current, (DataElementCollection, MultiValuedDataElement)):
                children = (
                    current.elements
                    if isinstance(current, DataElementCollection)
                    else current.value
                )
                if segment.isdecimal():
                    index = int(segment)
                    current = children[index] if index < len(children) else None
                else:
                    current = next(
                        (element for element in children if element.element_id == segment), None
                    )
            else:
                current = None
            if current is None:
                break
        return current
