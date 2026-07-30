"""Core DPP domain models (port of ``dppsdk.core.model``).

Each class is a frozen Pydantic v2 model that doubles as the JSON transport
payload: ``UUID`` serializes to its canonical string and ``date`` to ISO
``yyyy-MM-dd``, matching the Java ``*Payload`` POJOs exactly. Field names are the
verbatim camelCase JSON keys used by the Java SDK (Jackson applied no renaming).

Only *structural* rules (the checks performed by the Java ``Builder.build()``
methods) are enforced here on construction. *Semantic* rules (e.g. "no future
dates", cross-object consistency) live in :mod:`dpp_sdk.core.validation` and are
applied explicitly, preserving the Java behavior where ``fromJson`` is lenient.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from ._text import is_blank


def _require_non_blank(value: str) -> str:
    if is_blank(value):
        raise ValueError("must not be blank")
    return value


def _reject_blank_if_present(value: str | None) -> str | None:
    if value is not None and is_blank(value):
        raise ValueError("must not be blank if provided")
    return value


# A required, non-blank string (Java: `x == null || x.isBlank()` guard).
NonBlankStr = Annotated[str, AfterValidator(_require_non_blank)]
# An optional string that must not be blank when present.
OptionalStr = Annotated[str | None, AfterValidator(_reject_blank_if_present)]
# A non-negative integer used for optional count fields.
NonNegativeInt = Annotated[int, Field(ge=0)]


class _Base(BaseModel):
    """Shared config: immutable, name-or-alias population, reject unknown keys.

    ``extra='forbid'`` mirrors Jackson's default of failing on unknown
    properties in ``Dpp4FunJsonCodec``.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")

    def with_updates(self, **changes: object) -> Self:
        """Return a structurally revalidated immutable copy with ``changes``."""
        return type(self).model_validate({**self.model_dump(mode="python"), **changes})


class OrganizationRole(StrEnum):
    """Structural role an organization can play (port of ``OrganizationRole``)."""

    MANUFACTURER = "MANUFACTURER"
    SUPPLIER = "SUPPLIER"
    DISTRIBUTOR = "DISTRIBUTOR"


class Address(_Base):
    country: NonBlankStr
    zipCode: OptionalStr = None
    region: OptionalStr = None
    town: NonBlankStr
    street: OptionalStr = None


class Email(_Base):
    emailAddress: NonBlankStr
    typeOfEmail: OptionalStr = None


class Telephone(_Base):
    telephoneNumber: NonBlankStr
    typeOfTelephone: OptionalStr = None


class Contact(_Base):
    organization: NonBlankStr
    address: Address | None = None
    email: Email | None = None
    telephone: Telephone | None = None


class Organization(_Base):
    name: NonBlankStr
    gln: OptionalStr = None
    productDescription: OptionalStr = None
    productDesignation: OptionalStr = None
    productFamily: OptionalStr = None
    productRoot: OptionalStr = None
    productOrderSuffix: OptionalStr = None
    uri: OptionalStr = None
    contact: Contact | None = None
    role: OrganizationRole | None = None


class Nameplate(_Base):
    gtinCode: NonBlankStr
    internalArticleNumber: OptionalStr = None
    batchNumber: OptionalStr = None
    customsTariffNumber: OptionalStr = None
    uriOfTheProduct: OptionalStr = None
    manufacturer: Organization | None = None
    supplier: Organization | None = None


class Documentation(_Base):
    digitalInstructionsLink: OptionalStr = None
    safetyInstructionsLink: OptionalStr = None
    downloadable: bool = False
    availableForYears: NonNegativeInt | None = None
    paperCopyAvailableOnRequest: bool = False


class PassportMetadata(_Base):
    uniqueProductIdentifier: UUID
    passportUpdateDates: tuple[date, ...] = Field(min_length=1)
    qrCodeOrDigitalTag: OptionalStr = None
    externalDocumentationLink: OptionalStr = None


class DppCore(_Base):
    passportMetadata: PassportMetadata
    nameplate: Nameplate
    documentation: Documentation | None = None


class Dpp(_Base):
    """Abstract base for DPP aggregates (port of ``Dpp``).

    Holds the reusable ``coreDpp`` and exposes read-through accessors plus the
    standard ``dpp_id`` / ``product_id`` identifiers. Concrete aggregates (e.g.
    :class:`dpp_sdk.dpp4fun.model.Dpp4Fun`) extend this with domain submodels.
    """

    coreDpp: DppCore

    @property
    def passport_type(self) -> str:  # pragma: no cover - overridden by subclasses
        raise NotImplementedError

    # --- read-through accessors -------------------------------------------------
    @property
    def passportMetadata(self) -> PassportMetadata:
        return self.coreDpp.passportMetadata

    @property
    def nameplate(self) -> Nameplate:
        return self.coreDpp.nameplate

    @property
    def documentation(self) -> Documentation | None:
        return self.coreDpp.documentation

    @property
    def uniqueProductIdentifier(self) -> UUID:
        return self.coreDpp.passportMetadata.uniqueProductIdentifier

    @property
    def passportUpdateDates(self) -> tuple[date, ...]:
        return self.coreDpp.passportMetadata.passportUpdateDates

    @property
    def qrCodeOrDigitalTag(self) -> str | None:
        return self.coreDpp.passportMetadata.qrCodeOrDigitalTag

    @property
    def externalDocumentationLink(self) -> str | None:
        return self.coreDpp.passportMetadata.externalDocumentationLink

    @property
    def gtinCode(self) -> str:
        return self.coreDpp.nameplate.gtinCode

    @property
    def manufacturer(self) -> Organization | None:
        return self.coreDpp.nameplate.manufacturer

    @property
    def supplier(self) -> Organization | None:
        return self.coreDpp.nameplate.supplier

    @property
    def digitalInstructionsLink(self) -> str | None:
        doc = self.coreDpp.documentation
        return None if doc is None else doc.digitalInstructionsLink

    @property
    def safetyInstructionsLink(self) -> str | None:
        doc = self.coreDpp.documentation
        return None if doc is None else doc.safetyInstructionsLink

    # --- standard identifiers ---------------------------------------------------
    @property
    def dpp_id(self) -> str:
        """Stable DPP identifier: the unique product identifier as a string."""
        return str(self.coreDpp.passportMetadata.uniqueProductIdentifier)

    @property
    def product_id(self) -> str:
        """Stable product identifier: the GTIN code."""
        return self.coreDpp.nameplate.gtinCode
