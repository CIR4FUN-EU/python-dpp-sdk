"""DPP4Fun facade over canonical core JSON transport."""

from __future__ import annotations

from ..core.errors import DppValidationError
from ..core.json_codec import CompressedExpansionResult, DppJsonCodec
from ..core.model import DigitalProductPassport
from ..core.validation import IdentifierValidationContext
from .profile import Dpp4FunSemanticResolver
from .typed_model import Dpp4Fun


class Dpp4FunJsonCodec:
    """Typed DPP4Fun convenience operations backed by the core codec."""

    def __init__(self) -> None:
        self._codec = DppJsonCodec()
        self._resolver = Dpp4FunSemanticResolver()

    def to_json(self, value: Dpp4Fun | None) -> str:
        return self.to_expanded_json(value)

    def to_expanded_json(self, value: Dpp4Fun | None) -> str:
        return self._codec.to_expanded_json(None if value is None else value.passport)  # type: ignore[arg-type]

    def to_compressed_json(self, value: Dpp4Fun | None) -> str:
        return self._codec.to_compressed_json(None if value is None else value.passport)  # type: ignore[arg-type]

    def from_json(self, json_text: str) -> Dpp4Fun:
        return self.from_expanded_json(json_text)

    def from_expanded_json(self, json_text: str) -> Dpp4Fun:
        return Dpp4Fun.from_passport(self._codec.from_expanded_json(json_text))

    def expand_compressed_json(
        self,
        json_text: str,
        previous: DigitalProductPassport | Dpp4Fun | None = None,
    ) -> CompressedExpansionResult:
        prior_passport = previous.passport if isinstance(previous, Dpp4Fun) else previous
        return self._codec.expand_compressed_json(json_text, prior_passport, self._resolver)

    def from_compressed_json(self, json_text: str) -> Dpp4Fun:
        return Dpp4Fun.from_passport(self.expand_compressed_json(json_text).passport)

    def from_json_and_validate(
        self, json_text: str, context: IdentifierValidationContext | None = None
    ) -> Dpp4Fun:
        value = self.from_expanded_json(json_text)
        self._require_valid(value, context)
        return value

    def from_compressed_json_and_validate(self, json_text: str) -> Dpp4Fun:
        value = self.from_compressed_json(json_text)
        self._require_valid(value)
        return value

    @staticmethod
    def _require_valid(value: Dpp4Fun, context: IdentifierValidationContext | None = None) -> None:
        from .validation import Dpp4FunValidationService

        result = Dpp4FunValidationService().validate(value, context)
        if not result.is_valid:
            raise DppValidationError(f"Dpp4Fun validation failed: {result.issues}")


def to_json(value: Dpp4Fun | None) -> str:
    return Dpp4FunJsonCodec().to_json(value)


def from_json(json_text: str) -> Dpp4Fun:
    return Dpp4FunJsonCodec().from_json(json_text)


def from_json_and_validate(
    json_text: str, context: IdentifierValidationContext | None = None
) -> Dpp4Fun:
    return Dpp4FunJsonCodec().from_json_and_validate(json_text, context)
