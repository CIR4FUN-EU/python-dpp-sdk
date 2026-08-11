"""JSON transport for the furniture DPP (port of ``Dpp4FunJsonCodec``).

The canonical model nests the reusable fields under ``coreDpp``. For transport,
the outbound JSON is *flattened* — ``passportMetadata``, ``nameplate`` and
``documentation`` are lifted to the root — while the inbound parser accepts
*either* the flat or the nested shape and normalizes to nested before validation.

This module also serves as a ``DppCodec`` for :class:`Dpp4Fun` when used with the
repository client.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from ..core.errors import DppMappingError
from .model import Dpp4Fun
from .validation import validate_dpp4fun

_CORE_FIELDS = ("passportMetadata", "nameplate", "documentation")


def _reject_non_finite_constant(token: str) -> Any:
    raise ValueError(f"non-finite JSON number is not allowed: {token}")


def _move_if_present(source: dict[str, Any], target: dict[str, Any], field: str) -> None:
    """Move ``field`` from ``source`` to ``target`` if present (incl. a null value)."""
    if field in source:
        target[field] = source.pop(field)


def _flatten_core(root: dict[str, Any]) -> None:
    """Lift the core submodels out of ``coreDpp`` up to the root (outbound)."""
    core = root.pop("coreDpp", None)
    if not isinstance(core, dict):
        return
    for field in _CORE_FIELDS:
        _move_if_present(core, root, field)


def _normalize_transport(root: dict[str, Any]) -> None:
    """Normalize a flat-or-nested inbound shape to the canonical nested shape."""
    has_core = isinstance(root.get("coreDpp"), dict)

    if not has_core:
        created_core: dict[str, Any] = {}
        for field in _CORE_FIELDS:
            _move_if_present(root, created_core, field)
        if created_core:
            root["coreDpp"] = created_core
        return

    # coreDpp already present: drop any duplicate flat keys at the root.
    for field in _CORE_FIELDS:
        root.pop(field, None)
    if not root["coreDpp"]:
        del root["coreDpp"]


def to_json(dpp: Dpp4Fun) -> str:
    """Serialize a :class:`Dpp4Fun` to its flat transport JSON string."""
    try:
        data = dpp.model_dump(mode="json")
        _flatten_core(data)
        return json.dumps(data, allow_nan=False)
    except ValueError as exc:
        raise DppMappingError(f"Failed to serialize DPP to JSON: {exc}") from exc


def from_json(raw: str) -> Dpp4Fun:
    """Parse a :class:`Dpp4Fun` from JSON, accepting the flat or nested shape.

    Does not apply semantic validation (mirrors the lenient ``fromJson``).
    """
    try:
        tree = json.loads(raw, parse_constant=_reject_non_finite_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise DppMappingError(f"Failed to deserialize DPP JSON: {exc}") from exc
    if isinstance(tree, dict):
        _normalize_transport(tree)
    try:
        return Dpp4Fun.model_validate(tree)
    except ValidationError as exc:
        raise DppMappingError(f"Failed to map DPP JSON to Dpp4Fun: {exc}") from exc


def from_json_and_validate(raw: str) -> Dpp4Fun:
    """Parse and then fully validate a :class:`Dpp4Fun` (fail-fast)."""
    dpp = from_json(raw)
    validate_dpp4fun(dpp)
    return dpp


class Dpp4FunJsonCodec:
    """Object-oriented facade mirroring the Java ``Dpp4FunJsonCodec``.

    Also usable as a ``DppCodec[Dpp4Fun]`` with the repository client.
    """

    def to_json(self, dpp: Dpp4Fun) -> str:
        return to_json(dpp)

    def from_json(self, raw: str) -> Dpp4Fun:
        return from_json(raw)

    def from_json_and_validate(self, raw: str) -> Dpp4Fun:
        return from_json_and_validate(raw)
