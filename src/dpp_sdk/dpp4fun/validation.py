"""Core plus source-backed D4.1 validation for typed DPP4Fun passports."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from urllib.parse import urlsplit

from ..core.model import (
    DataElement,
    DataElementCollection,
    MultiLanguageDataElement,
    MultiValuedDataElement,
    RelatedResource,
    SingleValuedDataElement,
)
from ..core.semantic import DataElementKind, SemanticPath
from ..core.validation import (
    DataFormatValidator,
    DppValidator,
    IdentifierValidationContext,
    IdentifierValidator,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from .profile import DPP4FUN_PROFILE, Dpp4FunElementDefinition, Dpp4FunSemanticResolver
from .typed_model import Dpp4Fun
from .units import UnitDimension, _known_unit

_KINDS = {
    "DataElementCollection": DataElementKind.COLLECTION,
    "SingleValuedDataElement": DataElementKind.SINGLE,
    "MultiValuedDataElement": DataElementKind.MULTI_VALUED,
    "MultiLanguageDataElement": DataElementKind.MULTI_LANGUAGE,
    "RelatedResource": DataElementKind.RELATED_RESOURCE,
}


def _issue(
    path: str, rule: str, message: str, severity: ValidationSeverity = ValidationSeverity.ERROR
) -> ValidationIssue:
    return ValidationIssue(path, rule, message, severity)


def _matches(pattern: str, path: str) -> bool:
    expected, actual = pattern.split("."), path.split(".")
    expected_index = actual_index = 0
    while expected_index < len(expected) and actual_index < len(actual):
        segment = expected[expected_index]
        if segment.endswith("[*]"):
            if (
                segment[:-3] != actual[actual_index]
                or actual_index + 1 >= len(actual)
                or not actual[actual_index + 1].isdecimal()
            ):
                return False
            actual_index += 2
        elif segment != actual[actual_index]:
            return False
        else:
            actual_index += 1
        expected_index += 1
    return expected_index == len(expected) and actual_index == len(actual)


def _rule_path_matches(pattern: str, path: str) -> bool:
    expression = re.escape(pattern).replace(r"\[\*\]", r"\[\d+\]")
    return re.fullmatch(expression, path) is not None


def _definition(path: str, content_ids: Sequence[str]) -> Dpp4FunElementDefinition | None:
    ids = set(content_ids)
    applicable = {"general"} if DPP4FUN_PROFILE.metadata["contentSpecificationId"] in ids else set()
    applicable.update(
        f"characteristics-{variant}"
        for variant, identifier in DPP4FUN_PROFILE.variants.items()
        if identifier in ids
    )
    return next(
        (
            item
            for item in DPP4FUN_PROFILE.definitions
            if applicable.intersection(item.applies_to) and _matches(item.path, path)
        ),
        None,
    )


def _defined_for_any_variant(path: str) -> bool:
    return any(
        any(f"characteristics-{variant}" in item.applies_to for variant in DPP4FUN_PROFILE.variants)
        and _matches(item.path, path)
        for item in DPP4FUN_PROFILE.definitions
    )


def _value_matches(datatype: str | None, value: object) -> bool:
    if datatype in {"xsd:string", "xsd:anyURI", "xsd:dateTime"}:
        return isinstance(value, str)
    if datatype == "xsd:boolean":
        return isinstance(value, bool)
    if datatype == "xsd:integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if datatype in {"xsd:double", "xsd:decimal"}:
        return (
            isinstance(value, (int, float, Decimal))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    return False


def _uri_syntax_valid(value: str) -> bool:
    if not value or any(ord(char) <= 0x20 or ord(char) >= 0x7F for char in value):
        return False
    if re.search(r"%(?![0-9A-Fa-f]{2})", value):
        return False
    try:
        parsed = urlsplit(value)
        _ = parsed.port
        return True
    except ValueError:
        return False


def _wrong_unit_dimension(value: object, dimension: str) -> bool:
    if not isinstance(value, str):
        return False
    expected = dimension.removesuffix("-unit").upper()
    return any(
        name != expected and _known_unit(value, UnitDimension(name)) is not None
        for name in ("LENGTH", "MASS", "AREA", "VOLUME")
        if name in UnitDimension.__members__
    )


def _minimum_issues(elements: Sequence[DataElement], prefix: str = "") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    rules = DPP4FUN_PROFILE.metadata.get("semanticRules", ())
    for element in elements:
        element_id = element.element_id or ""
        path = f"{prefix}.{element_id}" if prefix else element_id
        if isinstance(element, (DataElementCollection, MultiValuedDataElement)):
            children = (
                element.elements if isinstance(element, DataElementCollection) else element.value
            )
            if isinstance(element, MultiValuedDataElement):
                parent_rules = [
                    rule
                    for rule in rules
                    if path.lower().endswith(str(rule["pathSuffix"]).replace("[*]", "").lower())
                ]
                for index, item in enumerate(children):
                    item_path = f"{path}[{index}]"
                    if isinstance(item, DataElementCollection):
                        for rule in parent_rules:
                            if any(
                                _rule_path_matches(str(excluded), item_path)
                                for excluded in rule["excludedPaths"]
                            ):
                                continue
                            required = rule["requiredField"]
                            child_ids = {child.element_id for child in item.elements}
                            if required and required not in child_ids:
                                issues.append(
                                    _issue(
                                        f"{item_path}.{required}",
                                        str(rule["id"]),
                                        f"field {required} is required by D4.1",
                                    )
                                )
                            elif (
                                not required
                                and rule["requiredAnyFields"]
                                and not child_ids.intersection(rule["requiredAnyFields"])
                            ):
                                field = str(rule["requiredAnyFields"][0])
                                issues.append(
                                    _issue(
                                        f"{item_path}.{field}",
                                        str(rule["id"]),
                                        "a source-backed time field is required by D4.1",
                                    )
                                )
                    if isinstance(item, DataElementCollection):
                        issues.extend(_minimum_issues(item.elements, item_path))
            else:
                issues.extend(_minimum_issues(children, path))
    return issues


class Dpp4FunValidator:
    """Validates D4.1 profile bindings without repeating generic core rules."""

    def __init__(self) -> None:
        self._resolver = Dpp4FunSemanticResolver()

    def validate(self, value: Dpp4Fun | None) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if value is None:
            return ValidationResult.of([_issue("", "DPP4FUN_REQUIRED", "Dpp4Fun is required")])
        passport = value.passport
        content_ids = passport.dpp_header.content_specification_ids
        known_content_ids = {
            DPP4FUN_PROFILE.metadata["contentSpecificationId"],
            *DPP4FUN_PROFILE.variants.values(),
        }
        for content_id in content_ids:
            if content_id not in known_content_ids:
                issues.append(
                    _issue(
                        "contentSpecificationIds",
                        "DPP4FUN_CONTENT_SPEC_SUPPORTED",
                        f"unsupported content specification: {content_id}",
                    )
                )
        selected = [
            identifier
            for identifier in DPP4FUN_PROFILE.variants.values()
            if identifier in content_ids
        ]
        if len(selected) > 1:
            issues.append(
                _issue(
                    "contentSpecificationIds",
                    "DPP4FUN_CHARACTERISTICS_VARIANT_SINGLE",
                    "at most one Characteristics variant may be selected",
                )
            )
        root_counts = Counter(element.element_id for element in passport.data_elements)
        for element in passport.data_elements:
            element_id = element.element_id or ""
            path = SemanticPath.of(element_id)
            if _definition(element_id, content_ids) is not None:
                self._element(element, path, content_ids, f"elements.{element_id}", issues)
            elif _defined_for_any_variant(element_id):
                issues.append(
                    _issue(
                        f"elements.{element_id}",
                        "DPP4FUN_CHARACTERISTICS_VARIANT_MATCHES_CONTENT_SPEC",
                        "element is defined for a different Characteristics variant",
                    )
                )
        for root_id, count in root_counts.items():
            definition = _definition(root_id or "", content_ids)
            if count > 1 and definition is not None:
                issues.append(
                    _issue(
                        f"elements.{root_id}",
                        "DPP4FUN_EXPLICIT_CARDINALITY",
                        "catalog binding permits at most one root occurrence",
                    )
                )
        if "general" not in self._applicability(content_ids) and any(
            _definition(
                element.element_id or "", (DPP4FUN_PROFILE.metadata["contentSpecificationId"],)
            )
            for element in passport.data_elements
        ):
            issues.append(
                _issue(
                    "contentSpecificationIds",
                    "DPP4FUN_CONTENT_SPEC_SUPPORTED",
                    "general aspects require the DPP4Fun common content specification",
                )
            )
        issues.extend(_minimum_issues(passport.data_elements))
        return ValidationResult.of(issues)

    @staticmethod
    def _applicability(content_ids: Sequence[str]) -> set[str]:
        result = (
            {"general"}
            if DPP4FUN_PROFILE.metadata["contentSpecificationId"] in content_ids
            else set()
        )
        result.update(
            f"characteristics-{variant}"
            for variant, identifier in DPP4FUN_PROFILE.variants.items()
            if identifier in content_ids
        )
        return result

    def _element(
        self,
        element: DataElement,
        path: SemanticPath,
        content_ids: Sequence[str],
        issue_path: str,
        issues: list[ValidationIssue],
    ) -> None:
        path_text = ".".join(path.segments)
        binding = _definition(path_text, content_ids)
        if binding is None:
            if _defined_for_any_variant(path_text):
                issues.append(
                    _issue(
                        issue_path,
                        "DPP4FUN_CHARACTERISTICS_VARIANT_MATCHES_CONTENT_SPEC",
                        "element is defined for a different Characteristics variant",
                    )
                )
            return
        actual_kind = _KINDS[type(element).__name__]
        expected_kind = _KINDS[binding.object_type]
        if actual_kind != expected_kind:
            issues.append(
                _issue(
                    issue_path,
                    "DPP4FUN_RESERVED_PATH_KIND",
                    f"catalog expects {expected_kind} but found {actual_kind}",
                )
            )
            return
        definition = self._resolver.resolve(content_ids, path)
        if (
            definition is not None
            and definition.element_id is not None
            and element.element_id != definition.element_id
        ):
            issues.append(
                _issue(
                    issue_path,
                    "DPP4FUN_RESERVED_PATH_ELEMENT_ID",
                    "elementId does not match the catalog binding",
                )
            )
        if (
            definition is not None
            and definition.dictionary_reference_resolved
            and element.dictionary_reference != definition.dictionary_reference
        ):
            issues.append(
                _issue(
                    issue_path,
                    "DPP4FUN_RESERVED_PATH_DICTIONARY_REFERENCE",
                    "dictionaryReference does not match the catalog binding",
                )
            )
        if isinstance(element, SingleValuedDataElement):
            if (
                binding.unit_dimension
                and binding.unit_dimension.endswith("-unit")
                and _wrong_unit_dimension(element.value, binding.unit_dimension)
            ):
                issues.append(
                    _issue(
                        issue_path,
                        "DPP4FUN_UNIT_DIMENSION_MISMATCH",
                        "known unit symbol does not match the catalogued physical dimension",
                    )
                )
            if (
                definition is not None
                and definition.value_data_type_resolved
                and element.value_data_type != definition.value_data_type
            ):
                issues.append(
                    _issue(
                        issue_path,
                        "DPP4FUN_RESERVED_PATH_VALUE_DATATYPE",
                        "valueDataType does not match the catalog binding",
                    )
                )
            if not _value_matches(binding.value_data_type, element.value):
                issues.append(
                    _issue(
                        issue_path,
                        "DPP4FUN_BINDING_DATATYPE_MISMATCH",
                        "value does not match the catalog datatype",
                    )
                )
            if (
                binding.value_data_type == "xsd:anyURI"
                and isinstance(element.value, str)
                and not _uri_syntax_valid(element.value)
            ):
                issues.append(
                    _issue(
                        f"{issue_path}.value",
                        "DPP4FUN_URI_FIELD_RFC3986",
                        "URI-valued D4.1 field must use RFC 3986 syntax",
                    )
                )
        elif isinstance(element, MultiValuedDataElement):
            if (
                definition is not None
                and definition.value_data_type_resolved
                and element.value_data_type != definition.value_data_type
            ):
                issues.append(
                    _issue(
                        issue_path,
                        "DPP4FUN_RESERVED_PATH_VALUE_DATATYPE",
                        "valueDataType does not match the catalog binding",
                    )
                )
            if not element.value:
                issues.append(
                    _issue(
                        issue_path,
                        "DPP4FUN_EXPLICIT_CARDINALITY",
                        "empty D4.1 lists must be omitted",
                    )
                )
            item_binding = _definition(f"{path_text}.0", content_ids)
            source_count = (
                item_binding.source_cardinality if item_binding else binding.source_cardinality
            )
            _check_count(source_count, len(element.value), issue_path, issues)
            for index, child in enumerate(element.value):
                item_path = path.child(str(index))
                item_path_text = ".".join(item_path.segments)
                child_binding = _definition(item_path_text, content_ids)
                if child_binding and child.object_type != child_binding.object_type:
                    issues.append(
                        _issue(
                            f"{issue_path}[{index}]",
                            "DPP4FUN_LIST_ITEM_KIND",
                            "repeated item must use the catalogued homogeneous child kind",
                        )
                    )
                    continue
                if child_binding and child_binding.repeated_item_policy:
                    pattern = child_binding.repeated_item_policy.get("elementIdPattern")
                    if pattern and child.element_id != pattern % index:
                        issues.append(
                            _issue(
                                f"{issue_path}[{index}].elementId",
                                "DPP4FUN_LIST_ITEM_ID_CANONICAL",
                                "repeated item id does not match its canonical position",
                            )
                        )
                self._element(child, item_path, content_ids, f"{issue_path}[{index}]", issues)
        elif isinstance(element, DataElementCollection):
            if not element.elements:
                issues.append(
                    _issue(
                        issue_path,
                        "DPP4FUN_EXPLICIT_CARDINALITY",
                        "empty D4.1 collections must be omitted",
                    )
                )
            counts = Counter(child.element_id for child in element.elements)
            for child in element.elements:
                child_path = path.child(child.element_id or "")
                child_binding = _definition(".".join(child_path.segments), content_ids)
                maximum = child_binding.binding_occurrence.get("max") if child_binding else None
                child_count = counts[child.element_id]
                if maximum is not None and child_count > maximum:
                    issues.append(
                        _issue(
                            f"{issue_path}.{child.element_id}",
                            "DPP4FUN_EXPLICIT_CARDINALITY",
                            "catalog binding occurrence is exceeded",
                        )
                    )
                self._element(
                    child, child_path, content_ids, f"{issue_path}.{child.element_id}", issues
                )
        elif isinstance(element, (MultiLanguageDataElement, RelatedResource)):
            return


def _check_count(
    occurrence: Mapping[str, int | None] | None,
    count: int,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    if occurrence is None:
        return
    minimum = occurrence.get("min") or 0
    maximum = occurrence.get("max")
    if count < minimum or maximum is not None and count > maximum:
        issues.append(
            _issue(
                path,
                "DPP4FUN_EXPLICIT_CARDINALITY",
                "item count conflicts with frozen source cardinality",
            )
        )


class Dpp4FunValidationService:
    """Java-equivalent ordered validation composition."""

    def __init__(self) -> None:
        self._core = DppValidator()
        self._format = DataFormatValidator()
        self._identifier = IdentifierValidator()
        self._profile = Dpp4FunValidator()

    def validate(
        self, value: Dpp4Fun | None, context: IdentifierValidationContext | None = None
    ) -> ValidationResult:
        if value is None:
            return self._profile.validate(None)
        passport = value.passport
        issues = list(self._core.validate(passport).issues)
        issues.extend(self._format.validate(passport).issues)
        if context is not None:
            issues.extend(self._identifier.validate(passport.dpp_header, context).issues)
        issues.extend(self._profile.validate(value).issues)
        return ValidationResult.of(issues)

    def validate_profile(self, value: Dpp4Fun | None) -> ValidationResult:
        return self._profile.validate(value)


def validate_dpp4fun(
    value: Dpp4Fun | None, context: IdentifierValidationContext | None = None
) -> ValidationResult:
    """Return ordered core, format, optional identifier, and D4.1 findings."""
    return Dpp4FunValidationService().validate(value, context)
