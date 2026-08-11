"""Semantic validators for the core DPP model (port of ``dppsdk.core.validation``).

Fail-fast: each validator raises :class:`~dpp_sdk.core.errors.DppValidationError`
on the FIRST rule violation, matching the Java ``Validator``/``ValidationService``
contract. These checks are applied explicitly (not on construction), so a model
may be constructed — e.g. via JSON deserialization — and only later rejected here.

Structural rules already enforced at construction (required/non-blank strings) are
re-checked defensively to mirror the Java validators one-to-one.
"""

from __future__ import annotations

from datetime import date

from ._text import is_blank
from .errors import DppValidationError
from .model import (
    Address,
    Contact,
    Documentation,
    DppCore,
    Email,
    Nameplate,
    Organization,
    OrganizationRole,
    PassportMetadata,
    Telephone,
)


def _has_text(value: str | None) -> bool:
    return value is not None and not is_blank(value)


def _require_not_blank(value: str | None, field_name: str) -> None:
    if is_blank(value):
        raise DppValidationError(f"{field_name} must not be blank")


def validate_address(address: Address | None) -> None:
    if address is None:
        return
    _require_not_blank(address.country, "Address.country")
    _require_not_blank(address.town, "Address.town")
    if address.zipCode is not None:
        _require_not_blank(address.zipCode, "Address.zipCode")
    if address.region is not None:
        _require_not_blank(address.region, "Address.region")
    if address.street is not None:
        _require_not_blank(address.street, "Address.street")


def validate_email(email: Email | None) -> None:
    if email is None:
        return
    _require_not_blank(email.emailAddress, "Email.emailAddress")
    if "@" not in email.emailAddress:
        raise DppValidationError(
            "Email.emailAddress does not appear to be a valid email (missing @)"
        )
    if email.typeOfEmail is not None:
        _require_not_blank(email.typeOfEmail, "Email.typeOfEmail")


def validate_telephone(telephone: Telephone | None) -> None:
    if telephone is None:
        return
    _require_not_blank(telephone.telephoneNumber, "Telephone.telephoneNumber")
    if telephone.typeOfTelephone is not None:
        _require_not_blank(telephone.typeOfTelephone, "Telephone.typeOfTelephone")


def validate_contact(contact: Contact | None) -> None:
    if contact is None:
        return
    _require_not_blank(contact.organization, "Contact.organization")
    if contact.address is None and contact.email is None and contact.telephone is None:
        raise DppValidationError(
            "Contact must provide at least one contact channel (address, email, or telephone)"
        )
    validate_address(contact.address)
    validate_email(contact.email)
    validate_telephone(contact.telephone)


def validate_organization(organization: Organization | None) -> None:
    if organization is None:
        raise DppValidationError("Organization is required")
    _require_not_blank(organization.name, "Organization.name")
    if organization.uri is not None:
        _require_not_blank(organization.uri, "Organization.uri")
    if organization.contact is not None:
        validate_contact(organization.contact)


def validate_nameplate(nameplate: Nameplate | None) -> None:
    if nameplate is None:
        raise DppValidationError("Nameplate is required")
    _require_not_blank(nameplate.gtinCode, "Nameplate.gtinCode")

    for value, name in (
        (nameplate.internalArticleNumber, "Nameplate.internalArticleNumber"),
        (nameplate.batchNumber, "Nameplate.batchNumber"),
        (nameplate.customsTariffNumber, "Nameplate.customsTariffNumber"),
        (nameplate.uriOfTheProduct, "Nameplate.uriOfTheProduct"),
    ):
        if value is not None:
            _require_not_blank(value, name)

    if nameplate.manufacturer is None and nameplate.supplier is None:
        raise DppValidationError("Nameplate must have at least a manufacturer or supplier")

    if nameplate.manufacturer is not None:
        validate_organization(nameplate.manufacturer)
        if nameplate.manufacturer.role is None:
            raise DppValidationError(
                "Nameplate.manufacturer must have role MANUFACTURER, but role is null"
            )
        if nameplate.manufacturer.role is not OrganizationRole.MANUFACTURER:
            raise DppValidationError(
                "Nameplate.manufacturer must have role MANUFACTURER, but got "
                + nameplate.manufacturer.role.value
            )

    if nameplate.supplier is not None:
        validate_organization(nameplate.supplier)
        if nameplate.supplier.role is None:
            raise DppValidationError("Nameplate.supplier must have role SUPPLIER, but role is null")
        if nameplate.supplier.role is not OrganizationRole.SUPPLIER:
            raise DppValidationError(
                "Nameplate.supplier must have role SUPPLIER, but got "
                + nameplate.supplier.role.value
            )


def validate_documentation(documentation: Documentation | None) -> None:
    if documentation is None:
        return

    digital_link = documentation.digitalInstructionsLink
    safety_link = documentation.safetyInstructionsLink

    if digital_link is not None:
        _require_not_blank(digital_link, "Documentation.digitalInstructionsLink")
    if safety_link is not None:
        _require_not_blank(safety_link, "Documentation.safetyInstructionsLink")

    has_any_link = _has_text(digital_link) or _has_text(safety_link)

    if documentation.downloadable and not has_any_link:
        raise DppValidationError(
            "Documentation is marked as downloadable but no documentation links are provided"
        )

    if documentation.availableForYears is not None:
        if documentation.availableForYears < 0:
            raise DppValidationError(
                "Documentation.availableForYears must be non-negative, but got "
                + str(documentation.availableForYears)
            )
        if not has_any_link:
            raise DppValidationError(
                "Documentation.availableForYears is set but no documentation links are provided"
            )


def validate_passport_metadata(metadata: PassportMetadata | None) -> None:
    if metadata is None:
        raise DppValidationError("PassportMetadata is required")
    if metadata.uniqueProductIdentifier is None:
        raise DppValidationError("PassportMetadata.uniqueProductIdentifier is required")
    if not metadata.passportUpdateDates:
        raise DppValidationError("PassportMetadata.passportUpdateDates must not be empty")

    today = date.today()
    for index, update_date in enumerate(metadata.passportUpdateDates):
        if update_date is None:
            raise DppValidationError(f"PassportMetadata.passportUpdateDates[{index}] is null")
        if update_date > today:
            raise DppValidationError(
                f"PassportMetadata.passportUpdateDates[{index}] is in the future: {update_date}"
            )

    if metadata.qrCodeOrDigitalTag is not None:
        _require_not_blank(metadata.qrCodeOrDigitalTag, "PassportMetadata.qrCodeOrDigitalTag")
    if metadata.externalDocumentationLink is not None:
        _require_not_blank(
            metadata.externalDocumentationLink, "PassportMetadata.externalDocumentationLink"
        )


def validate_dpp_core(core: DppCore | None) -> None:
    """Validate the reusable DPP core. Fail-fast; raises on first violation."""
    if core is None:
        raise DppValidationError("DppCore cannot be null")
    validate_passport_metadata(core.passportMetadata)
    validate_nameplate(core.nameplate)
    validate_documentation(core.documentation)
