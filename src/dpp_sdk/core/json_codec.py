"""Canonical FULL and COMPRESSED JSON transport for the shared DPP model."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, TypeAlias, cast

from .errors import DppMappingError
from .model import (
    DataElement,
    DataElementCollection,
    DigitalProductPassport,
    DppHeader,
    Granularity,
    MultiLanguageDataElement,
    MultiLanguageValue,
    MultiValuedDataElement,
    RelatedResource,
    SingleValuedDataElement,
)
from .semantic import DataElementKind, SemanticDefinition, SemanticPath, SemanticResolver

_DataElementModel: TypeAlias = (
    DataElementCollection
    | SingleValuedDataElement
    | MultiValuedDataElement
    | MultiLanguageDataElement
    | RelatedResource
)


class DppJsonException(DppMappingError):  # noqa: N818 - preserve the Java public type name
    """Raised when canonical DPP JSON cannot be written or interpreted."""


@dataclass(frozen=True)
class ExpansionIssue:
    path: str
    reason: str

    @property
    def rule(self) -> str:
        return "EN18223_COMPRESSED_SEMANTICS_UNRESOLVED"

    @property
    def severity(self) -> str:
        return "WARNING"


@dataclass(frozen=True)
class CompressedExpansionResult:
    passport: DigitalProductPassport
    issues: tuple[ExpansionIssue, ...] = ()


@dataclass(frozen=True)
class CompressedElementExpansionResult:
    element: _DataElementModel
    issues: tuple[ExpansionIssue, ...] = ()


_HEADER_FIELDS = (
    "digitalProductPassportId",
    "uniqueProductIdentifier",
    "granularity",
    "dppSchemaVersion",
    "dppStatus",
    "lastUpdated",
    "economicOperatorId",
    "facilityId",
    "contentSpecificationIds",
)
_HEADER_ATTRS = {
    "digitalProductPassportId": "digital_product_passport_id",
    "uniqueProductIdentifier": "unique_product_identifier",
    "granularity": "granularity",
    "dppSchemaVersion": "dpp_schema_version",
    "dppStatus": "dpp_status",
    "lastUpdated": "last_updated",
    "economicOperatorId": "economic_operator_id",
    "facilityId": "facility_id",
    "contentSpecificationIds": "content_specification_ids",
}
_RESOURCE_FIELDS = {"contentType", "url", "language", "resourceTitle"}


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON property '{key}'")
        result[key] = value
    return result


def _parse_json(text: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON number {value}")

    return json.loads(
        text,
        object_pairs_hook=_object_pairs,
        parse_float=Decimal,
        parse_constant=reject_constant,
    )


def _dump_json(value: Any) -> str:
    if value is None or isinstance(value, (str, bool, int)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise DppJsonException("number must be finite")
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DppJsonException("number must be finite")
        return json.dumps(value, allow_nan=False, separators=(",", ":"))
    if isinstance(value, Mapping):
        return (
            "{"
            + ",".join(_dump_json(str(key)) + ":" + _dump_json(item) for key, item in value.items())
            + "}"
        )
    if isinstance(value, (tuple, list)):
        return "[" + ",".join(_dump_json(item) for item in value) + "]"
    raise DppJsonException(f"unsupported JSON value type {type(value).__name__}")


def _ordered_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _ordered_json(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_ordered_json(item) for item in value]
    return value


def _required_text(obj: Mapping[str, Any], field: str, path: str) -> str:
    value = obj.get(field)
    if not isinstance(value, str):
        raise DppJsonException(f"{path}.{field} must be a string")
    return value


def _optional_text(obj: Mapping[str, Any], field: str, path: str) -> str | None:
    value = obj.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise DppJsonException(f"{path}.{field} must be a string when present")
    return value


def _instant_text(value: datetime) -> str:
    utc_value = value.astimezone(UTC)
    text = utc_value.strftime("%Y-%m-%dT%H:%M:%S")
    micros = utc_value.microsecond
    if micros:
        fraction = f"{micros // 1000:03d}" if micros % 1000 == 0 else f"{micros:06d}"
        text += f".{fraction}"
    return text + "Z"


class DppJsonCodec:
    """Translate canonical FULL and operational COMPRESSED representations."""

    def to_expanded_json(self, dpp: DigitalProductPassport) -> str:
        try:
            root = self._header_json(dpp.dpp_header)
            root["elements"] = [
                self._expanded_element(element, "$.elements") for element in dpp.data_elements
            ]
            return _dump_json(root)
        except DppJsonException:
            raise
        except Exception as exc:
            raise DppJsonException("Failed to serialize expanded DPP JSON") from exc

    def from_expanded_json(self, json_text: str) -> DigitalProductPassport:
        try:
            root = _parse_json(json_text)
            if not isinstance(root, dict):
                raise DppJsonException("Expanded DPP JSON root must be an object")
            self._known(root, {*_HEADER_FIELDS, "elements"}, "$")
            header = self._read_header(root)
            elements_value = root.get("elements", [])
            if not isinstance(elements_value, list):
                raise DppJsonException("$.elements must be an array")
            elements = tuple(
                self._read_element(value, f"$.elements[{index}]")
                for index, value in enumerate(elements_value)
            )
            return DigitalProductPassport(dpp_header=header, data_elements=elements)
        except DppJsonException:
            raise
        except Exception as exc:
            raise DppJsonException("Failed to deserialize expanded DPP JSON") from exc

    def read_header(self, dpp_json: str | Mapping[str, Any]) -> DppHeader:
        """Read only flattened header fields from FULL or COMPRESSED JSON."""
        try:
            root = _parse_json(dpp_json) if isinstance(dpp_json, str) else dpp_json
            if not isinstance(root, Mapping):
                raise DppJsonException("$ DPP JSON root must be an object")
            return self._read_header(root)
        except DppJsonException:
            raise
        except Exception as exc:
            raise DppJsonException("Failed to read DPP header") from exc

    def to_compressed_json(self, dpp: DigitalProductPassport) -> str:
        try:
            root = self._header_json(dpp.dpp_header)
            for element in dpp.data_elements:
                element_id = self._required_id(element, "$")
                if element_id in _HEADER_FIELDS:
                    raise DppJsonException(
                        f"$.{element_id} compressed element key collides with "
                        "an existing root property"
                    )
                root[element_id] = self._compressed_value(element, f"$.{element_id}")
            return _dump_json(root)
        except DppJsonException:
            raise
        except Exception as exc:
            raise DppJsonException("Failed to serialize compressed DPP JSON") from exc

    def expand_compressed_json(
        self,
        json_text: str,
        previous: DigitalProductPassport | None = None,
        resolver: SemanticResolver | None = None,
    ) -> CompressedExpansionResult:
        """Expand operational JSON, optionally using prior values and a resolver."""
        try:
            root = _parse_json(json_text)
            if not isinstance(root, dict):
                raise DppJsonException("$ compressed DPP JSON root must be an object")
            header = self._read_header(root)
            old = (
                {element.element_id: element for element in previous.data_elements}
                if previous
                else {}
            )
            issues: list[ExpansionIssue] = []
            elements: list[_DataElementModel] = []
            for key, value in root.items():
                if key in _HEADER_FIELDS:
                    continue
                path = f"$.'{key}'"
                elements.append(
                    self._expand_element(
                        key,
                        value,
                        path,
                        SemanticPath.of(key),
                        header.content_specification_ids,
                        resolver,
                        old.get(key),
                        issues,
                    )
                )
            return CompressedExpansionResult(
                DigitalProductPassport(dpp_header=header, data_elements=tuple(elements)),
                tuple(issues),
            )
        except DppJsonException:
            raise
        except Exception as exc:
            raise DppJsonException("Failed to expand compressed DPP JSON") from exc

    def expand_compressed_json_with_resolver(
        self, json_text: str, resolver: SemanticResolver
    ) -> CompressedExpansionResult:
        return self.expand_compressed_json(json_text, resolver=resolver)

    def to_compressed_element_json(self, element: DataElement) -> str:
        return _dump_json(self._compressed_value(element, f"$.'{self._required_id(element, '$')}'"))

    def to_expanded_element_json(self, element: DataElement) -> str:
        return _dump_json(self._expanded_element(element, "$element"))

    def from_expanded_element_json(self, json_text: str) -> _DataElementModel:
        try:
            return self._read_element(_parse_json(json_text), "$element")
        except DppJsonException:
            raise
        except Exception as exc:
            raise DppJsonException("Failed to parse expanded DataElement JSON") from exc

    def expand_compressed_element_json(
        self, element_id: str, json_text: str, previous: DataElement | None = None
    ) -> _DataElementModel:
        return self.expand_compressed_element_json_with_issues(
            element_id, json_text, previous
        ).element

    def expand_compressed_element_json_with_issues(
        self,
        element_id: str,
        json_text: str,
        previous: DataElement | None = None,
        content_specification_ids: Sequence[str] = (),
        resolver: SemanticResolver | None = None,
        semantic_path: SemanticPath | None = None,
    ) -> CompressedElementExpansionResult:
        if not element_id.strip():
            raise DppJsonException("$element elementId must not be blank")
        path = semantic_path or SemanticPath.of(element_id)
        try:
            issues: list[ExpansionIssue] = []
            element = self._expand_element(
                element_id,
                _parse_json(json_text),
                f"$.'{element_id}'",
                path,
                tuple(content_specification_ids),
                resolver,
                previous,
                issues,
            )
            return CompressedElementExpansionResult(element, tuple(issues))
        except DppJsonException:
            raise
        except Exception as exc:
            raise DppJsonException("Failed to parse compressed DataElement JSON") from exc

    def _header_json(self, header: DppHeader) -> dict[str, Any]:
        root: dict[str, Any] = {}
        for field in _HEADER_FIELDS:
            value = getattr(header, _HEADER_ATTRS[field])
            if field == "facilityId" and value is None:
                continue
            if value is None:
                if field == "granularity":
                    raise DppJsonException("$.granularity is required")
                if field == "lastUpdated":
                    raise DppJsonException("$.lastUpdated is required")
                if field == "contentSpecificationIds":
                    value = ()
                else:
                    raise DppJsonException(f"$.{field} is required")
            if field == "granularity":
                value = value.value
            elif field == "lastUpdated":
                value = _instant_text(value)
            elif field == "contentSpecificationIds":
                value = list(value)
            root[field] = value
        return root

    def _read_header(self, root: Mapping[str, Any]) -> DppHeader:
        values: dict[str, Any] = {}
        for field in (
            "digitalProductPassportId",
            "uniqueProductIdentifier",
            "dppSchemaVersion",
            "dppStatus",
            "economicOperatorId",
        ):
            values[_HEADER_ATTRS[field]] = _required_text(root, field, "$")
        granularity_text = _required_text(root, "granularity", "$")
        try:
            values["granularity"] = Granularity(granularity_text.lower())
        except ValueError as exc:
            raise DppJsonException(
                f"$.granularity has an unknown value '{granularity_text}'"
            ) from exc
        timestamp = _required_text(root, "lastUpdated", "$")
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError
            if parsed.utcoffset() != UTC.utcoffset(parsed):
                raise ValueError
        except ValueError as exc:
            raise DppJsonException(
                "$.lastUpdated must be a canonical UTC ISO-8601 instant"
            ) from exc
        canonical = _instant_text(parsed)
        if canonical != timestamp:
            raise DppJsonException(
                "$.lastUpdated must use canonical UTC ISO-8601 Instant representation"
            )
        values["last_updated"] = parsed
        values["facility_id"] = _optional_text(root, "facilityId", "$")
        specs = root.get("contentSpecificationIds", [])
        if not isinstance(specs, list) or any(not isinstance(item, str) for item in specs):
            raise DppJsonException("$.contentSpecificationIds must be an array of strings")
        values["content_specification_ids"] = tuple(specs)
        return DppHeader(**values)

    def _expanded_element(self, element: DataElement, path: str) -> dict[str, Any]:
        element_id = self._required_id(element, path)
        result: dict[str, Any] = {"elementId": element_id, "objectType": element.object_type}
        if element.dictionary_reference is not None:
            result["dictionaryReference"] = element.dictionary_reference
        if isinstance(element, DataElementCollection):
            if not element.elements:
                raise DppJsonException(f"{path} must contain at least one item")
            result["elements"] = [
                self._expanded_element(child, path + ".elements") for child in element.elements
            ]
        elif isinstance(element, SingleValuedDataElement):
            if element.value_data_type is not None:
                result["valueDataType"] = element.value_data_type
            result["value"] = _ordered_json(element.value)
        elif isinstance(element, MultiValuedDataElement):
            if not element.value:
                raise DppJsonException(f"{path}.value must contain at least one item")
            if element.value_data_type is not None:
                result["valueDataType"] = element.value_data_type
            result["value"] = [
                self._expanded_element(child, path + ".value") for child in element.value
            ]
        elif isinstance(element, MultiLanguageDataElement):
            if not element.value:
                raise DppJsonException(f"{path}.value must contain at least one item")
            result["value"] = [self._lang_value(item) for item in element.value]
        elif isinstance(element, RelatedResource):
            for field, value in (("contentType", element.content_type), ("url", element.url)):
                if value is None:
                    raise DppJsonException(f"{path}.{field} is required")
                result[field] = value
            if element.language is not None:
                result["language"] = element.language
            if element.resource_title is not None:
                result["resourceTitle"] = element.resource_title
        else:
            raise DppJsonException(f"{path} has an unsupported DataElement subtype")
        return result

    @staticmethod
    def _lang_value(value: MultiLanguageValue) -> dict[str, Any]:
        if value.value is None or value.language is None:
            raise DppJsonException("multilingual value and language are required")
        return {"value": value.value, "language": value.language}

    def _compressed_value(self, element: DataElement, path: str) -> Any:
        if isinstance(element, SingleValuedDataElement):
            value = _ordered_json(element.value)
            if isinstance(value, float) and not math.isfinite(value):
                raise DppJsonException(f"{path} number must be finite")
            return value
        if isinstance(element, DataElementCollection):
            if not element.elements:
                raise DppJsonException(f"{path} must contain at least one item")
            result: dict[str, Any] = {}
            for child in element.elements:
                child_id = self._required_id(child, path)
                if child_id in result:
                    raise DppJsonException(f"{path}.{child_id} duplicate compressed element key")
                result[child_id] = self._compressed_value(child, path + "." + child_id)
            return result
        if isinstance(element, MultiValuedDataElement):
            if not element.value:
                raise DppJsonException(f"{path} must contain at least one item")
            values = [
                self._compressed_value(child, f"{path}[{i}]")
                for i, child in enumerate(element.value)
            ]
            if any(_json_kind(value) != _json_kind(values[0]) for value in values):
                raise DppJsonException(
                    f"{path} MultiValuedDataElement items must have the same JSON datatype"
                )
            return values
        if isinstance(element, MultiLanguageDataElement):
            if not element.value:
                raise DppJsonException(f"{path} must contain at least one item")
            return [self._lang_value(item) for item in element.value]
        if isinstance(element, RelatedResource):
            if element.content_type is None or element.url is None:
                raise DppJsonException(f"{path} RelatedResource requires contentType and url")
            result = {"contentType": element.content_type, "url": element.url}
            if element.resource_title is not None:
                result = {"resourceTitle": element.resource_title, **result}
            if element.language is not None:
                result["language"] = element.language
            return result
        raise DppJsonException(f"{path} has an unsupported DataElement subtype")

    def _read_element(self, value: Any, path: str) -> _DataElementModel:
        if not isinstance(value, dict):
            raise DppJsonException(f"{path} must be an object")
        element_id = _required_text(value, "elementId", path)
        kind = _required_text(value, "objectType", path)
        dictionary = _optional_text(value, "dictionaryReference", path)
        common = {"elementId", "objectType", "dictionaryReference"}
        if kind == "DataElementCollection":
            self._known(value, common | {"elements"}, path)
            children = value.get("elements")
            if not isinstance(children, list) or not children:
                raise DppJsonException(f"{path}.elements must contain at least one item")
            return DataElementCollection(
                element_id=element_id,
                dictionary_reference=dictionary,
                elements=tuple(
                    self._read_element(item, f"{path}.elements[{i}]")
                    for i, item in enumerate(children)
                ),
            )
        if kind == "SingleValuedDataElement":
            self._known(value, common | {"valueDataType", "value"}, path)
            if "value" not in value:
                raise DppJsonException(f"{path}.value is required")
            return SingleValuedDataElement(
                element_id=element_id,
                dictionary_reference=dictionary,
                value_data_type=_optional_text(value, "valueDataType", path),
                value=value["value"],
            )
        if kind == "MultiValuedDataElement":
            self._known(value, common | {"valueDataType", "value", "elements"}, path)
            if ("value" in value) == ("elements" in value):
                raise DppJsonException(
                    f"{path} MultiValuedDataElement must contain exactly one of "
                    "'elements' or 'value'"
                )
            items = value.get("value", value.get("elements"))
            if not isinstance(items, list) or not items:
                raise DppJsonException(f"{path}.value must contain at least one item")
            return MultiValuedDataElement(
                element_id=element_id,
                dictionary_reference=dictionary,
                value_data_type=_optional_text(value, "valueDataType", path),
                value=tuple(
                    self._read_element(item, f"{path}.value[{i}]") for i, item in enumerate(items)
                ),
            )
        if kind == "MultiLanguageDataElement":
            self._known(value, common | {"value"}, path)
            items = value.get("value")
            if not isinstance(items, list) or not items:
                raise DppJsonException(f"{path}.value must contain at least one item")
            entries = []
            for i, item in enumerate(items):
                item_path = f"{path}.value[{i}]"
                if not isinstance(item, dict):
                    raise DppJsonException(f"{item_path} must be an object")
                self._known(item, {"value", "language"}, item_path)
                entries.append(
                    MultiLanguageValue(
                        value=_required_text(item, "value", item_path),
                        language=_required_text(item, "language", item_path),
                    )
                )
            return MultiLanguageDataElement(
                element_id=element_id, dictionary_reference=dictionary, value=tuple(entries)
            )
        if kind == "RelatedResource":
            self._known(value, common | _RESOURCE_FIELDS, path)
            return RelatedResource(
                element_id=element_id,
                dictionary_reference=dictionary,
                content_type=_required_text(value, "contentType", path),
                url=_required_text(value, "url", path),
                language=_optional_text(value, "language", path),
                resource_title=_optional_text(value, "resourceTitle", path),
            )
        raise DppJsonException(f"{path}.objectType unknown objectType '{kind}'")

    @staticmethod
    def _known(value: Mapping[str, Any], allowed: set[str], path: str) -> None:
        for field in value:
            if field not in allowed:
                raise DppJsonException(f"{path}.{field} unknown property")

    @staticmethod
    def _required_id(element: DataElement, path: str) -> str:
        if element.element_id is None:
            raise DppJsonException(f"{path} elementId is required")
        return element.element_id

    def _expand_element(
        self,
        element_id: str,
        value: Any,
        path: str,
        semantic_path: SemanticPath,
        content_specification_ids: Sequence[str],
        resolver: SemanticResolver | None,
        previous: DataElement | None,
        issues: list[ExpansionIssue],
    ) -> _DataElementModel:
        if not element_id.strip():
            raise DppJsonException(f"{path} elementId must not be blank")
        if value is None:
            raise DppJsonException(f"{path} null cannot form a required DataElement value")
        definition = (
            resolver.resolve(content_specification_ids, semantic_path) if resolver else None
        )
        if definition is not None:
            self._check_definition(element_id, definition, previous, path)
        kind = definition.kind if definition else None
        if kind is not None:
            assert definition is not None
        retained_single_value = False
        value_type_missing = False
        if (
            kind is None
            and isinstance(previous, SingleValuedDataElement)
            and isinstance(value, (dict, list))
        ):
            expanded: _DataElementModel = previous.with_updates(value=value)
            retained_single_value = True
            issues.append(
                ExpansionIssue(
                    path,
                    "object or array subtype was retained from the stored single-valued element",
                )
            )
        elif kind is DataElementKind.SINGLE:
            assert definition is not None
            value_type_missing = True
            expanded = SingleValuedDataElement(
                element_id=definition.element_id or element_id,
                dictionary_reference=definition.dictionary_reference,
                value_data_type=definition.value_data_type,
                value=value,
            )
        elif kind is DataElementKind.COLLECTION or (
            kind is None
            and isinstance(value, dict)
            and value
            and (not self._looks_resource(value) or isinstance(previous, DataElementCollection))
        ):
            if not isinstance(value, dict) or not value:
                raise DppJsonException(
                    f"{path} semantic definition expects a non-empty DataElementCollection object"
                )
            if kind is None:
                issues.append(
                    ExpansionIssue(
                        path,
                        "DataElementCollection was inferred from an object; "
                        "an object-valued single element is also possible",
                    )
                )
            old_children = (
                {child.element_id: child for child in previous.elements}
                if isinstance(previous, DataElementCollection)
                else {}
            )
            children = tuple(
                self._expand_element(
                    key,
                    child_value,
                    path + ".'" + key + "'",
                    semantic_path.child(key),
                    content_specification_ids,
                    resolver,
                    old_children.get(key),
                    issues,
                )
                for key, child_value in value.items()
            )
            expanded = DataElementCollection(
                element_id=definition.element_id if definition else element_id,
                dictionary_reference=definition.dictionary_reference if definition else None,
                elements=children,
            )
        elif kind is DataElementKind.RELATED_RESOURCE or (
            kind is None
            and isinstance(value, dict)
            and self._looks_resource(value)
            and not isinstance(previous, DataElementCollection)
        ):
            if kind is not None and (
                not isinstance(value, dict) or "contentType" not in value or "url" not in value
            ):
                raise DppJsonException(
                    f"{path} semantic definition expects a RelatedResource object "
                    "with contentType and url"
                )
            if set(value) - _RESOURCE_FIELDS:
                if kind is not None:
                    raise DppJsonException(
                        f"{path} resolved RelatedResource contains an unsupported field"
                    )
                issues.append(
                    ExpansionIssue(
                        path,
                        "resource-like object has additional fields; "
                        "retained as a single JSON value",
                    )
                )
                expanded = SingleValuedDataElement(element_id=element_id, value=value)
            else:
                expanded = RelatedResource(
                    element_id=definition.element_id if definition else element_id,
                    dictionary_reference=definition.dictionary_reference if definition else None,
                    content_type=_required_text(value, "contentType", path),
                    url=_required_text(value, "url", path),
                    language=_optional_text(value, "language", path),
                    resource_title=_optional_text(value, "resourceTitle", path),
                )
                if kind is None:
                    issues.append(
                        ExpansionIssue(
                            path,
                            "RelatedResource was inferred from contentType/url; "
                            "an object-valued single element is also possible",
                        )
                    )
        elif kind is None and isinstance(value, dict) and not value:
            expanded = SingleValuedDataElement(element_id=element_id, value=value)
            issues.append(
                ExpansionIssue(
                    path,
                    "empty object inferred as a single value because a collection "
                    "requires an element",
                )
            )
        elif kind in (DataElementKind.MULTI_VALUED, DataElementKind.MULTI_LANGUAGE) or isinstance(
            value, list
        ):
            if not isinstance(value, list) or not value:
                if kind is not None:
                    raise DppJsonException(f"{path} expected a non-empty array")
                expanded = SingleValuedDataElement(element_id=element_id, value=value)
                if not value:
                    issues.append(
                        ExpansionIssue(
                            path,
                            "empty array inferred as a single value because a multi-valued "
                            "element requires an item",
                        )
                    )
            elif kind is DataElementKind.MULTI_LANGUAGE or (
                kind is None
                and not isinstance(previous, MultiValuedDataElement)
                and self._is_language_array(value)
            ):
                entries = tuple(
                    MultiLanguageValue(
                        value=_required_text(item, "value", f"{path}[{i}]"),
                        language=_required_text(item, "language", f"{path}[{i}]"),
                    )
                    for i, item in enumerate(value)
                    if isinstance(item, dict)
                )
                if len(entries) != len(value):
                    if kind is not None:
                        raise DppJsonException(
                            f"{path} semantic definition expects language/value array items"
                        )
                    expanded = SingleValuedDataElement(element_id=element_id, value=value)
                else:
                    expanded = MultiLanguageDataElement(
                        element_id=definition.element_id if definition else element_id,
                        dictionary_reference=definition.dictionary_reference
                        if definition
                        else None,
                        value=entries,
                    )
                    if kind is None:
                        issues.append(
                            ExpansionIssue(
                                path,
                                "MultiLanguageDataElement was inferred from language/value items; "
                                "an array-valued single element is also possible",
                            )
                        )
            else:
                mixed_types = any(_json_kind(item) != _json_kind(value[0]) for item in value)
                if mixed_types and kind is DataElementKind.MULTI_VALUED:
                    raise DppJsonException(
                        f"{path} resolved MultiValuedDataElement requires like-typed items"
                    )
                if kind is None and mixed_types:
                    expanded = SingleValuedDataElement(element_id=element_id, value=value)
                    issues.append(
                        ExpansionIssue(
                            path,
                            "mixed array items retained as a single JSON value because a "
                            "multi-valued element requires like-typed items",
                        )
                    )
                else:
                    value_type_missing = True
                    if kind is None:
                        issues.append(
                            ExpansionIssue(
                                path,
                                "MultiValuedDataElement was inferred from an array; "
                                "an array-valued single element is also possible",
                            )
                        )
                    old_values = (
                        previous.value if isinstance(previous, MultiValuedDataElement) else ()
                    )
                    children = tuple(
                        self._expand_element(
                            str(i),
                            item,
                            f"{path}[{i}]",
                            semantic_path.child(str(i)),
                            content_specification_ids,
                            resolver,
                            old_values[i] if i < len(old_values) else None,
                            issues,
                        )
                        for i, item in enumerate(value)
                    )
                    if kind is None:
                        issues.append(
                            ExpansionIssue(
                                path,
                                "original array-item elementIds are absent; "
                                "positional identifiers were used",
                            )
                        )
                    expanded = MultiValuedDataElement(
                        element_id=definition.element_id if definition else element_id,
                        dictionary_reference=definition.dictionary_reference
                        if definition
                        else None,
                        value_data_type=definition.value_data_type if definition else None,
                        value=children,
                    )
        else:
            value_type_missing = True
            expanded = SingleValuedDataElement(element_id=element_id, value=value)

        if not retained_single_value:
            if definition is None or not definition.dictionary_reference_resolved:
                issues.append(
                    ExpansionIssue(path, "dictionaryReference is absent from operational JSON")
                )
            if value_type_missing and (
                definition is None or not definition.value_data_type_resolved
            ):
                issues.append(ExpansionIssue(path, "valueDataType is absent from operational JSON"))

        if definition is not None:
            expanded = self._apply_definition(expanded, definition, previous)
        elif previous is not None:
            expanded = self._restore_metadata(expanded, previous)
        return expanded

    @staticmethod
    def _looks_resource(value: Mapping[str, Any]) -> bool:
        return "contentType" in value and "url" in value

    @staticmethod
    def _is_language_array(value: list[Any]) -> bool:
        return bool(value) and all(
            isinstance(item, dict) and {"value", "language"} == set(item) for item in value
        )

    @staticmethod
    def _restore_metadata(fresh: DataElement, old: DataElement) -> _DataElementModel:
        if type(fresh) is not type(old):
            if isinstance(old, SingleValuedDataElement):
                raise DppJsonException(
                    "stored single-valued element was not retained during expansion"
                )
            raise DppJsonException("compressed value cannot change the stored DataElement subtype")
        values: dict[str, Any] = {
            "element_id": old.element_id,
            "dictionary_reference": old.dictionary_reference,
        }
        if isinstance(fresh, SingleValuedDataElement) and isinstance(old, SingleValuedDataElement):
            values["value_data_type"] = old.value_data_type
        if isinstance(fresh, MultiValuedDataElement) and isinstance(old, MultiValuedDataElement):
            values["value_data_type"] = old.value_data_type
            values["value"] = tuple(
                DppJsonCodec._restore_metadata(child, old.value[i]) if i < len(old.value) else child
                for i, child in enumerate(fresh.value)
            )
        if isinstance(fresh, DataElementCollection) and isinstance(old, DataElementCollection):
            old_by_id = {item.element_id: item for item in old.elements}
            values["elements"] = tuple(
                DppJsonCodec._restore_metadata(child, old_by_id[child.element_id])
                if child.element_id in old_by_id
                else child
                for child in fresh.elements
            )
        return cast(_DataElementModel, fresh.with_updates(**values))

    @staticmethod
    def _check_definition(
        element_id: str, definition: SemanticDefinition, previous: DataElement | None, path: str
    ) -> None:
        positional_id = element_id.isascii() and element_id.isdigit()
        if definition.element_id and element_id != definition.element_id and not positional_id:
            raise DppJsonException(
                f"{path} semantic definition elementId conflicts with compressed elementId"
            )
        if previous is not None:
            if definition.kind and _kind_of(previous) is not definition.kind:
                raise DppJsonException(
                    f"{path} semantic definition conflicts with stored DataElement kind"
                )
            if definition.element_id and previous.element_id != definition.element_id:
                raise DppJsonException(
                    f"{path} semantic definition conflicts with stored elementId"
                )
            if (
                definition.dictionary_reference_resolved
                and previous.dictionary_reference != definition.dictionary_reference
            ):
                raise DppJsonException(
                    f"{path} semantic definition conflicts with stored dictionaryReference"
                )
            previous_type = (
                previous.value_data_type
                if isinstance(previous, (SingleValuedDataElement, MultiValuedDataElement))
                else None
            )
            if definition.value_data_type_resolved and previous_type != definition.value_data_type:
                raise DppJsonException(
                    f"{path} semantic definition conflicts with stored valueDataType"
                )

    @staticmethod
    def _apply_definition(
        element: DataElement,
        definition: SemanticDefinition,
        previous: DataElement | None,
    ) -> _DataElementModel:
        changes: dict[str, Any] = {
            "element_id": definition.element_id
            or (previous.element_id if previous else element.element_id),
            "dictionary_reference": (
                definition.dictionary_reference
                if definition.dictionary_reference_resolved
                else previous.dictionary_reference
                if previous
                else element.dictionary_reference
            ),
        }
        previous_type = (
            previous.value_data_type
            if isinstance(previous, (SingleValuedDataElement, MultiValuedDataElement))
            else None
        )
        if isinstance(element, (SingleValuedDataElement, MultiValuedDataElement)):
            changes["value_data_type"] = (
                definition.value_data_type
                if definition.value_data_type_resolved
                else previous_type
                if previous_type is not None
                else element.value_data_type
            )
        if definition.value_data_type is not None and not isinstance(
            element, (SingleValuedDataElement, MultiValuedDataElement)
        ):
            raise DppJsonException("valueDataType is not valid for the resolved DataElement kind")
        return (
            cast(_DataElementModel, element.with_updates(**changes))
            if changes
            else cast(_DataElementModel, element)
        )


def _kind_of(element: DataElement) -> DataElementKind:
    if isinstance(element, DataElementCollection):
        return DataElementKind.COLLECTION
    if isinstance(element, SingleValuedDataElement):
        return DataElementKind.SINGLE
    if isinstance(element, MultiValuedDataElement):
        return DataElementKind.MULTI_VALUED
    if isinstance(element, MultiLanguageDataElement):
        return DataElementKind.MULTI_LANGUAGE
    return DataElementKind.RELATED_RESOURCE


def _json_kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float, Decimal)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__
