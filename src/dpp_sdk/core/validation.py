"""Aggregating semantic validation for the canonical core DPP model."""

from __future__ import annotations

import base64
import ipaddress
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from urllib.parse import unquote_to_bytes, urlsplit

from .model import (
    DataElement,
    DataElementCollection,
    DigitalProductPassport,
    DppHeader,
    Granularity,
    MultiLanguageDataElement,
    MultiValuedDataElement,
    RelatedResource,
    SingleValuedDataElement,
)


class ValidationSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class ValidationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One validation finding at a deterministic model path."""

    Severity = ValidationSeverity

    path: str
    rule: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR

    def __post_init__(self) -> None:
        if self.path is None or self.rule is None or self.message is None or self.severity is None:
            raise ValueError("path, rule, message, and severity are required")
        object.__setattr__(self, "rule", _canonical_rule(self.rule))


@dataclass(frozen=True, slots=True, init=False)
class ValidationResult:
    """Immutable ordered result of a complete core validation pass."""

    Status = ValidationStatus
    _issues: tuple[ValidationIssue, ...]
    _status: ValidationStatus

    def __init__(self, issues: tuple[ValidationIssue, ...] | list[ValidationIssue]) -> None:
        immutable_issues = tuple(issues)
        errors = tuple(i for i in immutable_issues if i.severity is ValidationSeverity.ERROR)
        unsupported = {
            "IDENTIFIER_METHOD_UNSUPPORTED",
            "IDENTIFICATION_LINK_DI_UNSUPPORTED",
            "GS1_DIGITAL_LINK_KEY_UNSUPPORTED",
            "GS1_DIGITAL_LINK_QUERY_UNSUPPORTED",
        }
        status = (
            ValidationStatus.VALID
            if not errors
            else ValidationStatus.UNSUPPORTED
            if all(issue.rule in unsupported for issue in errors)
            else ValidationStatus.INVALID
        )
        object.__setattr__(self, "_issues", immutable_issues)
        object.__setattr__(self, "_status", status)

    @classmethod
    def of(cls, issues: list[ValidationIssue] | tuple[ValidationIssue, ...]) -> ValidationResult:
        return cls(issues)

    @property
    def issues(self) -> tuple[ValidationIssue, ...]:
        return self._issues

    @property
    def status(self) -> ValidationStatus:
        return self._status

    @property
    def is_valid(self) -> bool:
        return self.status is ValidationStatus.VALID


_RULE_ALIASES = {
    "ELEMENT_ID_REQUIRED": "EN18223_ELEMENT_ID_REQUIRED",
    "ELEMENT_ID_DUPLICATE_IN_SCOPE": "EN18223_ELEMENT_ID_UNIQUE_WITHIN_LOCATION",
    "COLLECTION_EMPTY": "EN18223_COLLECTION_NON_EMPTY",
    "SINGLE_VALUE_REQUIRED": "EN18223_SINGLE_VALUE_REQUIRED",
    "MULTI_VALUE_EMPTY": "EN18223_MULTI_NON_EMPTY",
    "MULTI_VALUE_MIXED_ELEMENT_TYPES": "EN18223_MULTI_HOMOGENEOUS_KIND",
    "MULTI_VALUE_JSON_TYPE_MISMATCH": "EN18223_JSON_NATIVE_TYPE_MATCHES_XSD",
    "MULTI_LANGUAGE_EMPTY": "EN18223_MULTILANGUAGE_NON_EMPTY",
    "MULTI_LANGUAGE_VALUE_REQUIRED": "EN18223_MULTILANGUAGE_VALUE_REQUIRED",
    "MULTI_LANGUAGE_LANGUAGE_REQUIRED": "EN18223_MULTILANGUAGE_LANGUAGE_REQUIRED",
    "RELATED_RESOURCE_CONTENT_TYPE_REQUIRED": "EN18223_RELATED_RESOURCE_CONTENT_TYPE_REQUIRED",
    "RELATED_RESOURCE_URL_REQUIRED": "EN18223_RELATED_RESOURCE_URL_REQUIRED",
    "RESOURCE_URL_INVALID": "EN18223_RELATED_RESOURCE_URL_RFC3986",
    "MEDIA_TYPE_INVALID": "EN18223_RELATED_RESOURCE_CONTENT_TYPE_SYNTAX",
    "LOCALIZED_LANGUAGE_FORMAT_INVALID": "EN18223_MULTILANGUAGE_LANGUAGE_TAG",
    "LANGUAGE_CODE_UNKNOWN": "EN18223_MULTILANGUAGE_LANGUAGE_TAG",
    "COUNTRY_CODE_UNKNOWN": "EN18223_MULTILANGUAGE_LANGUAGE_TAG",
    "VALUE_DATA_TYPE_PROHIBITED": "EN18223_VALUE_DATATYPE_SUPPORTED",
    "VALUE_DATA_TYPE_UNKNOWN": "EN18223_VALUE_DATATYPE_SUPPORTED",
    "VALUE_TYPE_INCOMPATIBLE": "EN18223_VALUE_MATCHES_DATATYPE",
    "VALUE_FORMAT_INVALID": "EN18223_VALUE_MATCHES_DATATYPE",
    "MULTI_VALUE_DATA_TYPE_CONFLICT": "EN18223_MULTI_HOMOGENEOUS_DATATYPE",
    "MULTI_VALUE_DATA_TYPE_MISMATCH": "EN18223_MULTI_HOMOGENEOUS_DATATYPE",
}


def _canonical_rule(rule: str) -> str:
    return _RULE_ALIASES.get(rule, rule)


class DppValidator:
    """Checks mandatory EN 18223 Clause 4 semantics without raising on findings."""

    def validate(self, passport: DigitalProductPassport | None) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if passport is None:
            return ValidationResult(
                [ValidationIssue("dpp", "DPP_REQUIRED", "DigitalProductPassport is required")]
            )
        header = passport.dpp_header
        for name, value, rule in (
            (
                "digitalProductPassportId",
                header.digital_product_passport_id,
                "EN18223_HEADER_DPP_ID_REQUIRED",
            ),
            (
                "uniqueProductIdentifier",
                header.unique_product_identifier,
                "EN18223_HEADER_PRODUCT_ID_REQUIRED",
            ),
            ("granularity", header.granularity, "EN18223_HEADER_GRANULARITY_REQUIRED"),
            (
                "dppSchemaVersion",
                header.dpp_schema_version,
                "EN18223_HEADER_SCHEMA_VERSION_REQUIRED",
            ),
            ("dppStatus", header.dpp_status, "EN18223_HEADER_STATUS_REQUIRED"),
            ("lastUpdated", header.last_updated, "EN18223_HEADER_LAST_UPDATED_REQUIRED"),
            (
                "economicOperatorId",
                header.economic_operator_id,
                "EN18223_HEADER_ECONOMIC_OPERATOR_ID_REQUIRED",
            ),
        ):
            if value is None:
                issues.append(ValidationIssue(f"header.{name}", rule, f"{name} is required"))
        dpp_id = header.digital_product_passport_id
        if dpp_id is not None and not _absolute_uri(dpp_id):
            issues.append(
                ValidationIssue(
                    "header.digitalProductPassportId",
                    "EN18223_HEADER_DPP_ID_URI_RECOMMENDED",
                    "digitalProductPassportId should be an absolute URI",
                    ValidationSeverity.WARNING,
                )
            )
        for value in header.content_specification_ids:
            if value is None or not value.strip():
                issues.append(
                    ValidationIssue(
                        "header.contentSpecificationIds",
                        "EN18223_HEADER_CONTENT_SPEC_ID_NONBLANK",
                        "contentSpecificationId must not be blank",
                    )
                )

        seen_paths: set[str] = set()
        _absolute_paths(passport.data_elements, "elements", "elements", seen_paths, issues)
        _validate_elements(passport.data_elements, "elements", issues)
        return ValidationResult(issues)


def _absolute_uri(value: str) -> bool:
    return _uri_valid(value)


def _children(element: DataElement) -> tuple[DataElement, ...]:
    if isinstance(element, DataElementCollection):
        return element.elements
    if isinstance(element, MultiValuedDataElement):
        return element.value
    return ()


def _absolute_paths(
    elements: tuple[DataElement, ...],
    semantic_parent: str,
    display_parent: str,
    seen: set[str],
    issues: list[ValidationIssue],
) -> None:
    for index, element in enumerate(elements):
        element_id = element.element_id
        if element_id is None or not element_id.strip():
            continue
        absolute = f"{semantic_parent}.{element_id}"
        if absolute in seen:
            issues.append(
                ValidationIssue(
                    f"{display_parent}[{index}].elementId",
                    "EN18223_ABSOLUTE_PATH_UNIQUE",
                    "absolute DataElement paths must be unique",
                )
            )
        seen.add(absolute)
        children = _children(element)
        if children:
            _absolute_paths(children, absolute, f"{display_parent}[{index}].elements", seen, issues)


def _json_type(element: DataElement) -> str | None:
    if isinstance(element, SingleValuedDataElement):
        value = element.value
        if value is None:
            return None
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float, Decimal)):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, dict):
            return "object"
        if isinstance(value, (list, tuple)):
            return "array"
    if isinstance(element, (DataElementCollection, RelatedResource)):
        return "object"
    if isinstance(element, (MultiValuedDataElement, MultiLanguageDataElement)):
        return "array"
    return None


def _validate_elements(
    elements: tuple[DataElement, ...], path: str, issues: list[ValidationIssue]
) -> None:
    ids: set[str] = set()
    for index, element in enumerate(elements):
        element_path = f"{path}[{index}]"
        element_id = element.element_id
        if element_id is None or not element_id.strip():
            issues.append(
                ValidationIssue(
                    f"{element_path}.elementId",
                    "EN18223_ELEMENT_ID_REQUIRED",
                    "elementId is required",
                )
            )
        elif element_id in ids:
            issues.append(
                ValidationIssue(
                    f"{element_path}.elementId",
                    "EN18223_ELEMENT_ID_UNIQUE_WITHIN_LOCATION",
                    "elementId must be unique among elements in the same location",
                )
            )
        else:
            ids.add(element_id)

        if isinstance(element, DataElementCollection):
            child_path = f"{element_path}.elements"
            if not element.elements:
                issues.append(
                    ValidationIssue(
                        child_path,
                        "EN18223_COLLECTION_NON_EMPTY",
                        "DataElementCollection must contain at least one DataElement",
                    )
                )
            else:
                _validate_elements(element.elements, child_path, issues)
        elif isinstance(element, SingleValuedDataElement):
            if element.value is None:
                issues.append(
                    ValidationIssue(
                        f"{element_path}.value",
                        "EN18223_SINGLE_VALUE_REQUIRED",
                        "SingleValuedDataElement value is required",
                    )
                )
        elif isinstance(element, MultiValuedDataElement):
            child_path = f"{element_path}.elements"
            if not element.value:
                issues.append(
                    ValidationIssue(
                        child_path,
                        "EN18223_MULTI_NON_EMPTY",
                        "MultiValuedDataElement must contain at least one DataElement",
                    )
                )
            else:
                expected_class = type(element.value[0])
                mixed = False
                for child_index, child in enumerate(element.value[1:], 1):
                    if type(child) is not expected_class:
                        mixed = True
                        issues.append(
                            ValidationIssue(
                                f"{child_path}[{child_index}]",
                                "EN18223_MULTI_HOMOGENEOUS_KIND",
                                "All DataElements in a MultiValuedDataElement must have "
                                "the same concrete type",
                            )
                        )
                if not mixed:
                    expected_json_type: str | None = None
                    for child_index, child in enumerate(element.value):
                        current_type = _json_type(child)
                        if current_type is None:
                            continue
                        if expected_json_type is None:
                            expected_json_type = current_type
                        elif current_type != expected_json_type:
                            issues.append(
                                ValidationIssue(
                                    f"{child_path}[{child_index}]",
                                    "MULTI_VALUE_JSON_TYPE_MISMATCH",
                                    "All values in a MultiValuedDataElement must serialize "
                                    "to the same JSON type",
                                )
                            )
                _validate_elements(element.value, child_path, issues)
        elif isinstance(element, RelatedResource):
            if element.content_type is None:
                issues.append(
                    ValidationIssue(
                        f"{element_path}.contentType",
                        "RELATED_RESOURCE_CONTENT_TYPE_REQUIRED",
                        "contentType is required",
                    )
                )
            if element.url is None:
                issues.append(
                    ValidationIssue(
                        f"{element_path}.url", "RELATED_RESOURCE_URL_REQUIRED", "url is required"
                    )
                )
        elif isinstance(element, MultiLanguageDataElement):
            values_path = f"{element_path}.values"
            if not element.value:
                issues.append(
                    ValidationIssue(
                        values_path,
                        "MULTI_LANGUAGE_EMPTY",
                        "MultiLanguageDataElement must contain at least one MultiLanguageValue",
                    )
                )
            for value_index, value in enumerate(element.value):
                value_path = f"{values_path}[{value_index}]"
                if value.value is None:
                    issues.append(
                        ValidationIssue(
                            f"{value_path}.value",
                            "MULTI_LANGUAGE_VALUE_REQUIRED",
                            "value is required",
                        )
                    )
                if value.language is None:
                    issues.append(
                        ValidationIssue(
                            f"{value_path}.language",
                            "MULTI_LANGUAGE_LANGUAGE_REQUIRED",
                            "language is required",
                        )
                    )
        else:
            issues.append(
                ValidationIssue(
                    element_path,
                    "EN18223_OBJECT_TYPE_MATCHES_RUNTIME_KIND",
                    f"Unsupported DataElement implementation: {type(element).__name__}",
                )
            )


_XSD_ALLOWED = frozenset(  # noqa: SIM905 - compact source-backed type table
    """
anySimpleType string boolean decimal float double duration dateTime time date gYearMonth gYear
gMonthDay gDay gMonth hexBinary base64Binary anyURI integer nonPositiveInteger negativeInteger
long int short byte nonNegativeInteger unsignedLong unsignedInt unsignedShort unsignedByte
positiveInteger
""".split()  # noqa: SIM905
)
_XSD_PROHIBITED = frozenset(  # noqa: SIM905 - compact source-backed type table
    """
ENTITIES IDREFS NMTOKENS normalizedString token language NMTOKEN Name NCName ID IDREF ENTITY
NOTATION QName
""".split()  # noqa: SIM905
)
_LANGUAGE_CODES = frozenset(  # noqa: SIM905 - compact pinned ISO code table
    """
aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr cs cu cv cy
da de dv dz ee el en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha he hi ho hr ht hu hy
hz ia id ie ig ii ik io is it iu ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb lg li ln
lo lt lu lv mg mh mi mk ml mn mr ms mt my na nb nd ne ng nl nn no nr nv ny oc oj om or os pa pi
pl ps pt qu rm rn ro ru rw sa sc sd se sg si sk sl sm sn so sq sr ss st su sv sw ta te tg th ti tk
tl tn to tr ts tt tw ty ug uk ur uz ve vi vo wa wo xh yi yo za zh zu
""".split()  # noqa: SIM905
)
_COUNTRY_CODES = frozenset(  # noqa: SIM905 - compact pinned ISO code table
    """
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS
BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE
EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM
HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC
LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA
NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW
SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO
TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
""".split()  # noqa: SIM905
)


def _datatype(value: str) -> str:
    if not value.startswith("xsd:") or len(value) == 4:
        return "unknown"
    name = value[4:]
    if name in _XSD_PROHIBITED:
        return "prohibited"
    return "allowed" if name in _XSD_ALLOWED else "unknown"


def _media_type_valid(value: str) -> bool:
    token = r"[A-Za-z0-9!#$%&'*+.^_`|~-]+"
    match = re.fullmatch(rf"({token})/({token})(.*)", value)
    if match is None or len(match[1]) > 127 or len(match[2]) > 127:
        return False
    suffix = match[3]
    names: set[str] = set()
    while suffix:
        parameter = re.match(
            rf";[ \t]*({token})=({token}|\"(?:[^\"\\\r\n]|\\[^\r\n])*\")[ \t]*", suffix
        )
        if parameter is None:
            return False
        name = parameter[1].lower()
        if name in names:
            return False
        names.add(name)
        suffix = suffix[parameter.end() :]
    return True


def _uri_valid(value: str) -> bool:
    if not value or any(ord(char) < 0x21 or ord(char) > 0x7E for char in value):
        return False
    scheme = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*):", value)
    if scheme is None:
        return False
    remainder = value[scheme.end() :]
    if remainder.count("#") > 1:
        return False
    hierarchy, hash_mark, fragment = remainder.partition("#")
    before_query, query_mark, query = hierarchy.partition("?")
    if hash_mark and not _uri_chars_valid(fragment, "/?", allow_colon=True):
        return False
    if query_mark and not _uri_chars_valid(query, "/?", allow_colon=True):
        return False
    if before_query.startswith("//"):
        authority_path = before_query[2:]
        authority, slash, path = authority_path.partition("/")
        if not _authority_valid(authority):
            return False
        return not slash or _uri_chars_valid(path, "/", allow_colon=True)
    return _uri_chars_valid(before_query, "/", allow_colon=True)


def _uri_chars_valid(value: str, extra: str, *, allow_colon: bool) -> bool:
    allowed = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~!$&'()*+,;=" + extra
    )
    if "/" in extra:
        allowed += "@"
    if allow_colon:
        allowed += ":"
    index = 0
    while index < len(value):
        char = value[index]
        if char == "%":
            if re.fullmatch(r"[0-9A-Fa-f]{2}", value[index + 1 : index + 3]) is None:
                return False
            index += 3
        elif char in allowed:
            index += 1
        else:
            return False
    return True


def _authority_valid(authority: str) -> bool:
    if authority.count("@") > 1:
        return False
    userinfo, at, server = authority.rpartition("@")
    if at and not _uri_chars_valid(userinfo, ":", allow_colon=True):
        return False
    if server.startswith("["):
        end = server.find("]")
        if end < 0:
            return False
        literal = server[1:end]
        if literal.lower().startswith("v"):
            if re.fullmatch(r"[vV][0-9A-Fa-f]+\.[A-Za-z0-9._~!$&'()*+,;=:-]+", literal) is None:
                return False
        else:
            try:
                ipaddress.IPv6Address(literal)
            except ipaddress.AddressValueError:
                return False
        suffix = server[end + 1 :]
        return not (suffix and (not suffix.startswith(":") or not suffix[1:].isdigit()))
    if server.count(":") > 1:
        return False
    host, colon, port = server.partition(":")
    if colon and not all(char.isascii() and char.isdigit() for char in port):
        return False
    return _uri_chars_valid(host, ".", allow_colon=False)


def _language_valid(value: str) -> bool:
    if re.fullmatch(r"[A-Za-z]{2}-[A-Za-z]{2}", value) is None:
        return False
    return value[:2].lower() in _LANGUAGE_CODES and value[3:].upper() in _COUNTRY_CODES


def _value_failure(datatype: str, value: Any) -> tuple[str, str] | None:
    name = datatype[4:]
    if name in ("string", "anySimpleType"):
        if name == "anySimpleType":
            return None
        good = isinstance(value, str)
    elif name == "boolean":
        good = isinstance(value, bool)
    elif name in ("float", "double"):
        good = isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
    elif name == "decimal":
        good = isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
        if isinstance(value, str):
            normalized = re.sub(r"[ \t\r\n]+", " ", value).strip()
            if re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", normalized) is None:
                return "VALUE_FORMAT_INVALID", "value is not in the required decimal string format"
            try:
                Decimal(normalized)
                good = True
            except InvalidOperation:
                return "VALUE_FORMAT_INVALID", "value is not in the required decimal string format"
        if not good:
            return "VALUE_TYPE_INCOMPATIBLE", "value must be a JSON number or decimal string"
    elif name in (
        "integer",
        "long",
        "int",
        "short",
        "byte",
        "positiveInteger",
        "nonNegativeInteger",
        "negativeInteger",
        "nonPositiveInteger",
        "unsignedLong",
        "unsignedInt",
        "unsignedShort",
        "unsignedByte",
    ):
        if (
            not isinstance(value, (int, float, Decimal))
            or isinstance(value, bool)
            or int(value) != value
        ):
            return "VALUE_TYPE_INCOMPATIBLE", "value must be a JSON integral number"
        number = int(value)
        bounds = {
            "positiveInteger": (1, None),
            "nonNegativeInteger": (0, None),
            "negativeInteger": (None, -1),
            "nonPositiveInteger": (None, 0),
            "long": (-(2**63), 2**63 - 1),
            "int": (-(2**31), 2**31 - 1),
            "short": (-(2**15), 2**15 - 1),
            "byte": (-(2**7), 2**7 - 1),
            "unsignedLong": (0, 2**64 - 1),
            "unsignedInt": (0, 2**32 - 1),
            "unsignedShort": (0, 65535),
            "unsignedByte": (0, 255),
        }
        lower, upper = bounds.get(name, (None, None))
        if lower is not None and number < lower or upper is not None and number > upper:
            return "VALUE_FORMAT_INVALID", f"value is outside the {name} integer range"
        return None
    elif name == "date":
        good = isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None
        if good:
            try:
                date.fromisoformat(value)
            except ValueError:
                return (
                    "VALUE_FORMAT_INVALID",
                    "value is not in the required real calendar date format",
                )
        elif isinstance(value, str):
            return "VALUE_FORMAT_INVALID", "value is not in the required YYYY-MM-DD date format"
        else:
            return "VALUE_TYPE_INCOMPATIBLE", "value must be a JSON date string"
    elif name == "dateTime":
        good = (
            isinstance(value, str)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is not None
        )
        if good:
            try:
                date.fromisoformat(value[:10])
                hour, minute, second = (
                    int(value[start:end]) for start, end in ((11, 13), (14, 16), (17, 19))
                )
                if hour == 24 and minute == 0 and second == 0:
                    return None
                if hour > 23 or minute > 59:
                    raise ValueError
                if second <= 59:
                    return None
                leap_second_dates = {
                    "1972-06-30",
                    "1972-12-31",
                    "1973-12-31",
                    "1974-12-31",
                    "1975-12-31",
                    "1976-12-31",
                    "1977-12-31",
                    "1978-12-31",
                    "1979-12-31",
                    "1981-06-30",
                    "1982-06-30",
                    "1983-06-30",
                    "1985-06-30",
                    "1987-12-31",
                    "1989-12-31",
                    "1990-12-31",
                    "1992-06-30",
                    "1993-06-30",
                    "1994-06-30",
                    "1995-12-31",
                    "1997-06-30",
                    "1998-12-31",
                    "2005-12-31",
                    "2008-12-31",
                    "2012-06-30",
                    "2015-06-30",
                    "2016-12-31",
                }
                if second == 60 and hour == 23 and minute == 59 and value[:10] in leap_second_dates:
                    return None
                raise ValueError
            except ValueError:
                return (
                    "VALUE_FORMAT_INVALID",
                    "value is not in the required real UTC dateTime format",
                )
        elif isinstance(value, str):
            return (
                "VALUE_FORMAT_INVALID",
                "value is not in the required YYYY-MM-DDThh:mm:ssZ dateTime format",
            )
        else:
            return "VALUE_TYPE_INCOMPATIBLE", "value must be a UTC dateTime string"
    elif name == "anyURI":
        if not isinstance(value, str):
            return "VALUE_TYPE_INCOMPATIBLE", "value must be a URI string"
        if not _uri_valid(value):
            return "VALUE_FORMAT_INVALID", "value is not in the required RFC 3986 URI format"
        return None
    elif name == "base64Binary":
        if not isinstance(value, str):
            return "VALUE_TYPE_INCOMPATIBLE", "value must be a base64 string"
        collapsed = re.sub(r"[ \t\r\n]+", " ", value).strip().replace(" ", "")
        try:
            if (
                len(collapsed) % 4
                or base64.b64encode(base64.b64decode(collapsed, validate=True)).decode()
                != collapsed
            ):
                raise ValueError
        except ValueError:
            return "VALUE_FORMAT_INVALID", "value is not in the required base64 encoding format"
        return None
    else:
        return None
    return (
        None
        if good
        else ("VALUE_TYPE_INCOMPATIBLE", "value has a JSON type incompatible with its datatype")
    )


class DataFormatValidator:
    """Checks locally verifiable JSON, datatype, URI, media, and language formats."""

    def validate(self, passport: DigitalProductPassport | None) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if passport is not None:
            self._elements(passport.data_elements, "elements", issues)
        return ValidationResult(issues)

    def _elements(
        self, elements: tuple[DataElement, ...], path: str, issues: list[ValidationIssue]
    ) -> None:
        for index, element in enumerate(elements):
            self._element(element, f"{path}[{index}]", issues)

    def _element(self, element: DataElement, path: str, issues: list[ValidationIssue]) -> None:
        if isinstance(element, RelatedResource):
            if element.url is not None and not _uri_valid(element.url):
                issues.append(
                    ValidationIssue(
                        f"{path}.url",
                        "RESOURCE_URL_INVALID",
                        "url must be an absolute RFC 3986 URI",
                    )
                )
            if element.content_type is not None and not _media_type_valid(element.content_type):
                issues.append(
                    ValidationIssue(
                        f"{path}.contentType",
                        "MEDIA_TYPE_INVALID",
                        "contentType must be a syntactically valid media type",
                    )
                )
            if element.language is not None and not _language_valid(element.language):
                issues.append(
                    ValidationIssue(
                        f"{path}.language",
                        "EN18223_RELATED_RESOURCE_LANGUAGE_TAG",
                        "language must be a recognized two-letter language and country tag",
                    )
                )
        elif isinstance(element, SingleValuedDataElement):
            self._single(element, path, element.value_data_type, False, issues)
        elif isinstance(element, DataElementCollection):
            self._elements(element.elements, f"{path}.elements", issues)
        elif isinstance(element, MultiValuedDataElement):
            self._multi(element, path, issues)
        elif isinstance(element, MultiLanguageDataElement):
            for index, item in enumerate(element.value):
                if item.language is not None and not _language_valid(item.language):
                    issues.append(
                        ValidationIssue(
                            f"{path}.values[{index}].language",
                            "EN18223_MULTILANGUAGE_LANGUAGE_TAG",
                            "language must be a recognized two-letter language and country tag",
                        )
                    )

    def _multi(
        self, multi: MultiValuedDataElement, path: str, issues: list[ValidationIssue]
    ) -> None:
        container_type = multi.value_data_type
        if container_type is not None:
            self._check_datatype(container_type, f"{path}.valueDataType", issues)
        inferred: str | None = None
        for index, child in enumerate(multi.value):
            child_path = f"{path}.elements[{index}]"
            if isinstance(child, SingleValuedDataElement):
                child_type = child.value_data_type
                if (
                    container_type is not None
                    and child_type is not None
                    and container_type != child_type
                ):
                    issues.append(
                        ValidationIssue(
                            f"{child_path}.valueDataType",
                            "MULTI_VALUE_DATA_TYPE_CONFLICT",
                            "child valueDataType conflicts with its MultiValuedDataElement "
                            "declaration",
                        )
                    )
                if container_type is None and child_type is not None:
                    if inferred is None:
                        inferred = child_type
                    elif inferred != child_type:
                        issues.append(
                            ValidationIssue(
                                f"{child_path}.valueDataType",
                                "MULTI_VALUE_DATA_TYPE_MISMATCH",
                                "all declared child valueDataType values in a "
                                "MultiValuedDataElement must match",
                            )
                        )
                if child_type is not None:
                    self._single(child, child_path, child_type, False, issues)
                elif container_type is not None:
                    self._single(child, child_path, container_type, True, issues)
            else:
                self._element(child, child_path, issues)

    def _check_datatype(self, datatype: str, path: str, issues: list[ValidationIssue]) -> str:
        classification = _datatype(datatype)
        if classification == "prohibited":
            issues.append(
                ValidationIssue(
                    path,
                    "VALUE_DATA_TYPE_PROHIBITED",
                    "valueDataType uses an XSD built-in prohibited by EN 18223",
                )
            )
        elif classification == "unknown":
            issues.append(
                ValidationIssue(
                    path,
                    "VALUE_DATA_TYPE_UNKNOWN",
                    "valueDataType must use a supported xsd:<built-in> spelling",
                )
            )
        return classification

    def _single(
        self,
        single: SingleValuedDataElement,
        path: str,
        datatype: str | None,
        inherited: bool,
        issues: list[ValidationIssue],
    ) -> None:
        if datatype is None:
            return
        classification = _datatype(datatype)
        if not inherited:
            classification = self._check_datatype(datatype, f"{path}.valueDataType", issues)
        if classification != "allowed" or single.value is None:
            return
        failure = _value_failure(datatype, single.value)
        if failure:
            rule, message = failure
            issues.append(ValidationIssue(f"{path}.value", rule, message))


class ProductIdentifierMethod(StrEnum):
    GS1_DIGITAL_LINK = "GS1_DIGITAL_LINK"
    IDENTIFICATION_LINK = "IDENTIFICATION_LINK"
    UNSUPPORTED = "UNSUPPORTED"


class EconomicOperatorIdentifierMethod(StrEnum):
    GS1_GLN = "GS1_GLN"
    UNSUPPORTED = "UNSUPPORTED"


class FacilityIdentifierMethod(StrEnum):
    GS1_GLN = "GS1_GLN"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class IdentifierValidationContext:
    """Caller-selected local identifier profiles; methods are never inferred."""

    product_identifier_method: ProductIdentifierMethod
    economic_operator_identifier_method: EconomicOperatorIdentifierMethod
    facility_identifier_method: FacilityIdentifierMethod | None = None

    def __post_init__(self) -> None:
        if (
            self.product_identifier_method is None
            or self.economic_operator_identifier_method is None
        ):
            raise ValueError("product and economic-operator identifier methods are required")


def _gs1_check_digit(value: str, length: int) -> bool:
    if len(value) != length or not value.isascii() or not value.isdigit():
        return False
    total = sum(
        int(char) * (3 if (length - 2 - index) % 2 == 0 else 1)
        for index, char in enumerate(value[:-1])
    )
    return (10 - total % 10) % 10 == int(value[-1])


def _identifier_url(value: str, schemes: tuple[str, ...]) -> tuple[str, str, str | None] | None:
    if any(ord(char) < 0x21 or ord(char) > 0x7E for char in value) or re.search(
        r"%(?![0-9A-Fa-f]{2})", value
    ):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme.lower() not in schemes
            or not parsed.hostname
            or not parsed.path
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            return None
        _ = parsed.port
        query = parsed.query if "?" in value.split("#", 1)[0] else None
        return parsed.scheme, parsed.path, query
    except ValueError:
        return None


def _valid_gs1_query(query: str) -> bool:
    for parameter in query.split("&"):
        if "=" not in parameter:
            return False
        raw_key, raw_value = parameter.split("=", 1)
        try:
            key = unquote_to_bytes(raw_key).decode("utf-8", errors="strict")
            value = unquote_to_bytes(raw_value).decode("utf-8", errors="strict")
        except UnicodeError:
            return False
        if not key:
            return False
        if "=" in key:
            return False
        if key.isascii() and key.isdigit() and (not 2 <= len(key) <= 4 or not value):
            return False
    return True


def _xchar_value(raw: str, maximum: int) -> bool:
    unreserved = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._"
    symbols = "!\"%&'()*+,-./:;<=>?ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz0123456789"
    index = 0
    while index < len(raw):
        char = raw[index]
        if char == "%":
            if (
                index + 2 >= len(raw)
                or re.fullmatch(r"[0-9A-Fa-f]{2}", raw[index + 1 : index + 3]) is None
            ):
                return False
            decoded = chr(int(raw[index + 1 : index + 3], 16))
            if decoded in unreserved or decoded not in symbols:
                return False
            index += 3
        elif char in unreserved:
            index += 1
        else:
            return False
    try:
        decoded_value = unquote_to_bytes(raw).decode("utf-8", errors="strict")
    except UnicodeError:
        return False
    return (
        bool(decoded_value)
        and len(decoded_value) <= maximum
        and all(char in symbols for char in decoded_value)
    )


def _granularity_issue(
    represented: Granularity, actual: Granularity | None
) -> ValidationIssue | None:
    if actual is None:
        return ValidationIssue(
            "header.granularity",
            "IDENTIFIER_GRANULARITY_REQUIRED",
            "Granularity is required to compare with the selected identifier",
        )
    if represented is not actual:
        return ValidationIssue(
            "header.granularity",
            "IDENTIFIER_GRANULARITY_MISMATCH",
            "Granularity does not match the product level represented by the selected identifier",
        )
    return None


def _gs1_product(identifier: str | None, granularity: Granularity | None) -> list[ValidationIssue]:
    path = "header.uniqueProductIdentifier"
    parsed = None if identifier is None else _identifier_url(identifier, ("https",))
    if parsed is None or parsed[2] is not None and not _valid_gs1_query(parsed[2]):
        return [
            ValidationIssue(
                path,
                "GS1_DIGITAL_LINK_URL_INVALID",
                "GS1 Digital Link must be an absolute HTTPS URI with valid RFC 3986 encoding",
            )
        ]
    _, raw_path, query = parsed
    segments = raw_path.split("/")
    key_index = next(
        (
            i
            for i in range(len(segments) - 2, 0, -1)
            if segments[i] == "01" and _gs1_check_digit(segments[i + 1], 14)
        ),
        -1,
    )
    if key_index < 0:
        if any(
            segments[i] in {"8006", "8010", "8013"} and segments[i + 1]
            for i in range(1, len(segments) - 1)
        ):
            return [
                ValidationIssue(
                    path,
                    "GS1_DIGITAL_LINK_KEY_UNSUPPORTED",
                    "This GS1 Digital Link product key is not locally validated",
                )
            ]
        return [
            ValidationIssue(
                path, "GS1_DIGITAL_LINK_KEY_INVALID", "A GTIN primary key using AI 01 is required"
            )
        ]
    seen: set[str] = set()
    ranks = {"22": 0, "10": 1, "21": 2, "235": 3}
    qualifiers: list[str] = []
    previous = -1
    for i in range(key_index + 2, len(segments), 2):
        if i + 1 >= len(segments) or not segments[i] or not segments[i + 1]:
            return [
                ValidationIssue(
                    path,
                    "GS1_DIGITAL_LINK_QUALIFIER_INVALID",
                    "GS1 Digital Link qualifiers must be complete AI/value pairs",
                )
            ]
        ai, raw = segments[i], segments[i + 1]
        rank = ranks.get(ai, -1)
        if (
            rank < 0
            or rank <= previous
            or ai in seen
            or ai == "235"
            and qualifiers
            or not _xchar_value(raw, 28 if ai == "235" else 20)
        ):
            return [
                ValidationIssue(
                    path,
                    "GS1_DIGITAL_LINK_QUALIFIER_INVALID",
                    "The GTIN key qualifiers must use supported GS1 syntax and order",
                )
            ]
        previous = rank
        seen.add(ai)
        qualifiers.append(ai)
    represented = (
        Granularity.ITEM
        if "21" in qualifiers or "235" in qualifiers
        else Granularity.BATCH
        if "10" in qualifiers
        else Granularity.MODEL
    )
    issue = _granularity_issue(represented, granularity)
    issues = [issue] if issue else []
    if query is not None and any(
        key.isdigit() for key in (piece.split("=", 1)[0] for piece in query.split("&"))
    ):
        issues.append(
            ValidationIssue(
                path,
                "GS1_DIGITAL_LINK_QUERY_UNSUPPORTED",
                "GS1 numeric query attributes require AI/value validation not implemented by "
                "this local profile",
            )
        )
    return issues


def _gln(identifier: str | None, path: str, role: str) -> list[ValidationIssue]:
    if not identifier:
        return [ValidationIssue(path, "GS1_GLN_INVALID", "A GS1 GLN is required")]
    ai: str | None = None
    query_issue: ValidationIssue | None = None
    key = identifier
    if identifier.lower().startswith(("https://", "http://")):
        parsed = _identifier_url(identifier, ("http", "https"))
        if parsed is None:
            return [
                ValidationIssue(
                    path,
                    "GS1_GLN_INVALID",
                    "A GS1 GLN Digital Link must be a valid HTTP or HTTPS URI",
                )
            ]
        _, raw_path, query = parsed
        if query is not None and not _valid_gs1_query(query):
            return [
                ValidationIssue(
                    path, "GS1_GLN_INVALID", "A GS1 GLN Digital Link must use valid query syntax"
                )
            ]
        if query is not None and any(
            piece.split("=", 1)[0].isdigit() for piece in query.split("&")
        ):
            query_issue = ValidationIssue(
                path,
                "GS1_DIGITAL_LINK_QUERY_UNSUPPORTED",
                "GS1 numeric query attributes require AI/value validation not implemented by "
                "this local profile",
            )
        segments = raw_path.split("/")
        ix = next(
            (
                i
                for i in range(len(segments) - 2, 0, -1)
                if segments[i] in {"414", "417"} and len(segments) - i in {2, 4}
            ),
            -1,
        )
        if ix < 0:
            return [
                issue
                for issue in (
                    query_issue,
                    ValidationIssue(
                        path, "GS1_GLN_INVALID", "A GS1 GLN Digital Link must use AI 414 or AI 417"
                    ),
                )
                if issue is not None
            ]
        ai, key = segments[ix], segments[ix + 1]
        if len(segments) - ix == 4 and (
            ai != "414" or segments[ix + 2] != "254" or not _xchar_value(segments[ix + 3], 20)
        ):
            return [
                issue
                for issue in (
                    query_issue,
                    ValidationIssue(
                        path,
                        "GS1_GLN_INVALID",
                        "Only physical-location GLN can carry a GS1 GLN extension",
                    ),
                )
                if issue is not None
            ]
    elif len(identifier) == 16 and identifier[:3] in {"414", "417"}:
        ai, key = identifier[:3], identifier[3:]
    else:
        return [ValidationIssue(path, "GS1_GLN_INVALID", "A GS1 GLN must include AI 414 or AI 417")]
    if not _gs1_check_digit(key, 13):
        return [
            issue
            for issue in (
                query_issue,
                ValidationIssue(
                    path,
                    "GS1_GLN_INVALID",
                    "A GLN must be 13 digits and have a valid GS1 check digit",
                ),
            )
            if issue is not None
        ]
    expected = "417" if role == "party" else "414"
    if ai is not None and ai != expected:
        role_label = "party (AI 417)" if role == "party" else "physical location (AI 414)"
        role_issue = ValidationIssue(
            path, "GS1_GLN_ROLE_MISMATCH", f"Identifier must identify a {role_label}"
        )
    else:
        role_issue = None
    return [issue for issue in (query_issue, role_issue) if issue is not None]


class IdentifierValidator:
    """Validates explicitly selected EN 18219 local identifier profiles."""

    def validate(
        self, header: DppHeader | None, context: IdentifierValidationContext | None
    ) -> ValidationResult:
        if header is None:
            return ValidationResult(
                [ValidationIssue("header", "IDENTIFIER_HEADER_REQUIRED", "DppHeader is required")]
            )
        if context is None:
            return ValidationResult(
                [
                    ValidationIssue(
                        "context",
                        "IDENTIFIER_VALIDATION_CONTEXT_REQUIRED",
                        "IdentifierValidationContext is required",
                    )
                ]
            )
        issues: list[ValidationIssue] = []
        if context.product_identifier_method is ProductIdentifierMethod.GS1_DIGITAL_LINK:
            issues.extend(_gs1_product(header.unique_product_identifier, header.granularity))
        elif context.product_identifier_method is ProductIdentifierMethod.IDENTIFICATION_LINK:
            identifier = header.unique_product_identifier or ""
            permitted = (
                re.fullmatch(r"[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=-]+", identifier) is not None
            )
            if not identifier or len(identifier) > 255 or not permitted:
                issues.append(
                    ValidationIssue(
                        "header.uniqueProductIdentifier",
                        "IDENTIFICATION_LINK_URL_INVALID",
                        "Identification Link must use valid IEC 61406-1 URL syntax and "
                        "permitted characters",
                    )
                )
            else:
                scheme = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", identifier)
                explicit_authority = (
                    re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", identifier) is not None
                )
                authority_end = min(
                    (identifier.find(char) for char in "/?#" if identifier.find(char) >= 0),
                    default=len(identifier),
                )
                authority = identifier[:authority_end]
                port = re.search(r":([0-9]+)$", authority)
                if not explicit_authority and port is not None or scheme is None:
                    normalized = "https://" + identifier
                else:
                    normalized = identifier
                try:
                    parsed = urlsplit(normalized)
                    if (
                        parsed.scheme.lower() != "https"
                        or not parsed.hostname
                        or parsed.fragment
                        or any(
                            label.lower().startswith("xn--") for label in parsed.hostname.split(".")
                        )
                    ):
                        raise ValueError
                    _ = parsed.port
                except ValueError:
                    issues.append(
                        ValidationIssue(
                            "header.uniqueProductIdentifier",
                            "IDENTIFICATION_LINK_URL_INVALID",
                            "Identification Link must use valid IEC 61406-1 URL syntax and "
                            "permitted characters",
                        )
                    )
                else:
                    parameters = parsed.query.split("&") if parsed.query else []
                    sidi = [p for p in parameters if p.split("=", 1)[0].startswith(".")]
                    if not sidi:
                        issue = _granularity_issue(Granularity.ITEM, header.granularity)
                        if issue:
                            issues.append(issue)
                    else:
                        malformed_parameter = any(
                            ("=" not in parameter or not parameter.split("=", 1)[0])
                            for parameter in parameters
                            if not parameter.split("=", 1)[0].startswith(".")
                        )
                        if malformed_parameter:
                            issues.append(
                                ValidationIssue(
                                    "header.uniqueProductIdentifier",
                                    "IDENTIFICATION_LINK_STRUCTURED_SYNTAX_INVALID",
                                    "Structured query parameters must be name/value pairs",
                                )
                            )
                        else:
                            product = batch = item = False
                            for parameter in sidi:
                                name, sep, value = parameter.partition("=")
                                if not sep or re.fullmatch(r"\.[0-9]{0,3}[A-Z]", name) is None:
                                    issues.append(
                                        ValidationIssue(
                                            "header.uniqueProductIdentifier",
                                            "IDENTIFICATION_LINK_STRUCTURED_SYNTAX_INVALID",
                                            "SIDI parameters require a dot-prefixed "
                                            "Data Identifier and a name/value pair",
                                        )
                                    )
                                    break
                                if not value:
                                    issues.append(
                                        ValidationIssue(
                                            "header.uniqueProductIdentifier",
                                            "IDENTIFICATION_LINK_REQUIRED_IDENTIFIER_MISSING",
                                            "A structured Data Identifier requires a "
                                            "non-empty value",
                                        )
                                    )
                                    break
                                if name in {".P", ".1P"}:
                                    product = True
                                elif name in {".T", ".1T"}:
                                    batch = True
                                elif name == ".S":
                                    item = True
                                else:
                                    issues.append(
                                        ValidationIssue(
                                            "header.uniqueProductIdentifier",
                                            "IDENTIFICATION_LINK_DI_UNSUPPORTED",
                                            "This locally validated structured subset recognizes "
                                            "product categories .P/.1P, batch categories .T/.1T, "
                                            "and serial category .S",
                                        )
                                    )
                                    break
                            else:
                                represented = (
                                    Granularity.ITEM
                                    if item
                                    else Granularity.BATCH
                                    if batch and product
                                    else Granularity.MODEL
                                    if product
                                    else None
                                )
                                if represented is None:
                                    issues.append(
                                        ValidationIssue(
                                            "header.uniqueProductIdentifier",
                                            "IDENTIFICATION_LINK_REQUIRED_IDENTIFIER_MISSING",
                                            "A structured product link requires product-code, "
                                            "batch, or item identification",
                                        )
                                    )
                                else:
                                    issue = _granularity_issue(represented, header.granularity)
                                    if issue:
                                        issues.append(issue)
        else:
            issues.append(
                ValidationIssue(
                    "header.uniqueProductIdentifier",
                    "IDENTIFIER_METHOD_UNSUPPORTED",
                    "The selected product identifier method is outside this SDK milestone",
                )
            )

        if (
            context.economic_operator_identifier_method
            is EconomicOperatorIdentifierMethod.UNSUPPORTED
        ):
            issues.append(
                ValidationIssue(
                    "header.economicOperatorId",
                    "IDENTIFIER_METHOD_UNSUPPORTED",
                    "The selected economic-operator identifier method is outside this SDK "
                    "milestone",
                )
            )
        else:
            issues.extend(_gln(header.economic_operator_id, "header.economicOperatorId", "party"))
        if header.facility_id is not None:
            if context.facility_identifier_method is not FacilityIdentifierMethod.GS1_GLN:
                issues.append(
                    ValidationIssue(
                        "header.facilityId",
                        "IDENTIFIER_METHOD_UNSUPPORTED",
                        "The selected facility identifier method is outside this SDK milestone",
                    )
                )
            else:
                issues.extend(_gln(header.facility_id, "header.facilityId", "location"))
        return ValidationResult(issues)
