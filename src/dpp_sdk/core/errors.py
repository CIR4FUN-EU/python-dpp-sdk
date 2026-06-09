"""Exception hierarchy for the DPP datamodel.

Mirrors the Java SDK's split between mapping/transport failures and semantic
validation failures. Construction-time (structural) failures surface as
``pydantic.ValidationError``; the semantic validators in
:mod:`dpp_sdk.core.validation` raise :class:`DppValidationError`.
"""

from __future__ import annotations


class DppError(Exception):
    """Base class for all datamodel errors raised by the SDK."""


class DppValidationError(DppError):
    """Raised when a DPP fails a semantic validation rule (fail-fast)."""


class DppMappingError(DppError):
    """Raised when a DPP cannot be serialized to or parsed from JSON."""
