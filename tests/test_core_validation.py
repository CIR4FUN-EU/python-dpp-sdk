"""Semantic validation of the core model (fail-fast, explicit)."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

import pytest

from dpp_sdk.core.errors import DppValidationError
from dpp_sdk.core.model import (
    Contact,
    Documentation,
    DppCore,
    Email,
    Nameplate,
    Organization,
    OrganizationRole,
    PassportMetadata,
)
from dpp_sdk.core.validation import (
    validate_contact,
    validate_documentation,
    validate_dpp_core,
    validate_email,
    validate_nameplate,
)


def test_valid_core_passes(valid_core: DppCore) -> None:
    validate_dpp_core(valid_core)  # no raise


def test_future_date_rejected(valid_core: DppCore) -> None:
    future = date.today() + timedelta(days=1)
    bad = valid_core.model_copy(
        update={
            "passportMetadata": valid_core.passportMetadata.model_copy(
                update={"passportUpdateDates": [future]}
            )
        }
    )
    with pytest.raises(DppValidationError, match="future"):
        validate_dpp_core(bad)


def test_nameplate_requires_manufacturer_or_supplier() -> None:
    with pytest.raises(DppValidationError, match="manufacturer or supplier"):
        validate_nameplate(Nameplate(gtinCode="G1"))


def test_manufacturer_role_must_match_slot() -> None:
    np = Nameplate(
        gtinCode="G1", manufacturer=Organization(name="ACME", role=OrganizationRole.SUPPLIER)
    )
    with pytest.raises(DppValidationError, match="MANUFACTURER"):
        validate_nameplate(np)


def test_manufacturer_role_missing_rejected() -> None:
    np = Nameplate(gtinCode="G1", manufacturer=Organization(name="ACME"))
    with pytest.raises(DppValidationError, match="role is null"):
        validate_nameplate(np)


def test_email_must_contain_at() -> None:
    with pytest.raises(DppValidationError, match="missing @"):
        validate_email(Email(emailAddress="not-an-email"))


def test_contact_requires_a_channel() -> None:
    with pytest.raises(DppValidationError, match="at least one contact channel"):
        validate_contact(Contact(organization="HQ"))


def test_documentation_downloadable_requires_link() -> None:
    with pytest.raises(DppValidationError, match="downloadable"):
        validate_documentation(Documentation(downloadable=True))


def test_documentation_available_years_requires_link() -> None:
    with pytest.raises(DppValidationError, match="availableForYears"):
        validate_documentation(Documentation(availableForYears=5))


def test_external_doc_link_present_is_fine_when_constructed() -> None:
    # Construction allows externalDocumentationLink; the cross-rule lives in dpp4fun.
    meta = PassportMetadata(
        uniqueProductIdentifier=UUID(int=1),
        passportUpdateDates=[date(2024, 1, 1)],
        externalDocumentationLink="https://x.example",
    )
    assert meta.externalDocumentationLink == "https://x.example"
