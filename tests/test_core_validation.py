"""Semantic validation of the core model (fail-fast, explicit)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from dpp_sdk.core.errors import DppError, DppValidationError
from dpp_sdk.core.model import (
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
from dpp_sdk.core.validation import (
    validate_address,
    validate_contact,
    validate_documentation,
    validate_dpp_core,
    validate_email,
    validate_nameplate,
    validate_organization,
    validate_passport_metadata,
    validate_telephone,
)


@pytest.mark.parametrize(
    "contract_id, factory",
    [
        (
            "VALIDATION-CORE-DOCUMENTATION-SAFETY-INSTRUCTIONS-LINK-MUST-NOT-BE-BLANK-IF-PROVIDED-F24E7A",
            lambda: Documentation(safetyInstructionsLink=" "),
        ),
        (
            "VALIDATION-CORE-NAMEPLATE-CUSTOMS-TARIFF-NUMBER-MUST-NOT-BE-BLANK-IF-PROVIDED-BC8DDB",
            lambda: Nameplate(gtinCode="G", customsTariffNumber=" "),
        ),
        (
            "VALIDATION-CORE-NAMEPLATE-URI-OF-THE-PRODUCT-MUST-NOT-BE-BLANK-IF-PROVIDED-BD396E",
            lambda: Nameplate(gtinCode="G", uriOfTheProduct=" "),
        ),
        (
            "VALIDATION-CORE-ORGANIZATION-PRODUCT-DESCRIPTION-MUST-NOT-BE-BLANK-IF-PROVIDED-72C9DA",
            lambda: Organization(name="A", productDescription=" "),
        ),
        (
            "VALIDATION-CORE-ORGANIZATION-PRODUCT-DESIGNATION-MUST-NOT-BE-BLANK-IF-PROVIDED-31B8FD",
            lambda: Organization(name="A", productDesignation=" "),
        ),
        (
            "VALIDATION-CORE-ORGANIZATION-PRODUCT-FAMILY-MUST-NOT-BE-BLANK-IF-PROVIDED-4F1CD8",
            lambda: Organization(name="A", productFamily=" "),
        ),
        (
            "VALIDATION-CORE-ORGANIZATION-PRODUCT-ORDER-SUFFIX-MUST-NOT-BE-BLANK-IF-PROVIDED-E0A619",
            lambda: Organization(name="A", productOrderSuffix=" "),
        ),
        (
            "VALIDATION-CORE-ORGANIZATION-PRODUCT-ROOT-MUST-NOT-BE-BLANK-IF-PROVIDED-B78AEF",
            lambda: Organization(name="A", productRoot=" "),
        ),
    ],
    ids=lambda row: row if isinstance(row, str) else None,
)
def test_optional_blank_contract_evidence(contract_id: str, factory: Callable[[], object]) -> None:
    with pytest.raises(ValidationError):
        factory()


def test_valid_core_passes(valid_core: DppCore) -> None:
    validate_dpp_core(valid_core)  # no raise


def test_future_date_rejected(valid_core: DppCore) -> None:
    future = date.today() + timedelta(days=1)
    bad = valid_core.model_copy(
        update={
            "passportMetadata": valid_core.passportMetadata.model_copy(
                update={"passportUpdateDates": (future,)}
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
        passportUpdateDates=(date(2024, 1, 1),),
        externalDocumentationLink="https://x.example",
    )
    assert meta.externalDocumentationLink == "https://x.example"


@pytest.mark.parametrize(
    ("contract_id", "validator", "value", "context"),
    [
        pytest.param(
            "VALIDATION-CORE-ADDRESS-ADDRESS-COUNTRY-9CDFA3",
            validate_address,
            Address.model_construct(country="", town="Berlin"),
            "Address.country",
            id="VALIDATION-CORE-ADDRESS-ADDRESS-COUNTRY-9CDFA3",
        ),
        pytest.param(
            "VALIDATION-CORE-ADDRESS-ADDRESS-TOWN-07F97D",
            validate_address,
            Address.model_construct(country="DE", town=""),
            "Address.town",
            id="VALIDATION-CORE-ADDRESS-ADDRESS-TOWN-07F97D",
        ),
        pytest.param(
            "VALIDATION-CORE-ADDRESS-ADDRESS-ZIP-CODE-58EF55",
            validate_address,
            Address.model_construct(country="DE", town="Berlin", zipCode=""),
            "Address.zipCode",
            id="VALIDATION-CORE-ADDRESS-ADDRESS-ZIP-CODE-58EF55",
        ),
        pytest.param(
            "VALIDATION-CORE-ADDRESS-ADDRESS-REGION-0D098C",
            validate_address,
            Address.model_construct(country="DE", town="Berlin", region=""),
            "Address.region",
            id="VALIDATION-CORE-ADDRESS-ADDRESS-REGION-0D098C",
        ),
        pytest.param(
            "VALIDATION-CORE-ADDRESS-ADDRESS-STREET-7432C5",
            validate_address,
            Address.model_construct(country="DE", town="Berlin", street=""),
            "Address.street",
            id="VALIDATION-CORE-ADDRESS-ADDRESS-STREET-7432C5",
        ),
        pytest.param(
            "VALIDATION-CORE-EMAIL-EMAIL-VALIDATOR-ACD929",
            validate_email,
            Email.model_construct(emailAddress="bad"),
            "missing @",
            id="VALIDATION-CORE-EMAIL-EMAIL-VALIDATOR-ACD929",
        ),
        pytest.param(
            "VALIDATION-CORE-TELEPHONE-TELEPHONE-TELEPHONE-NUMBER-62DD93",
            validate_telephone,
            Telephone.model_construct(telephoneNumber=""),
            "Telephone.telephoneNumber",
            id="VALIDATION-CORE-TELEPHONE-TELEPHONE-TELEPHONE-NUMBER-62DD93",
        ),
        pytest.param(
            "VALIDATION-CORE-ORGANIZATION-ORGANIZATION-NAME-6061B8",
            validate_organization,
            Organization.model_construct(name=""),
            "Organization.name",
            id="VALIDATION-CORE-ORGANIZATION-ORGANIZATION-NAME-6061B8",
        ),
        pytest.param(
            "VALIDATION-CORE-TELEPHONE-TELEPHONE-TYPE-OF-TELEPHONE-E23B71",
            validate_telephone,
            Telephone.model_construct(telephoneNumber="+49", typeOfTelephone=" "),
            "Telephone.typeOfTelephone",
            id="VALIDATION-CORE-TELEPHONE-TELEPHONE-TYPE-OF-TELEPHONE-E23B71",
        ),
        pytest.param(
            "VALIDATION-CORE-ORGANIZATION-ORGANIZATION-URI-024597",
            validate_organization,
            Organization.model_construct(name="ACME", uri=""),
            "Organization.uri",
            id="VALIDATION-CORE-ORGANIZATION-ORGANIZATION-URI-024597",
        ),
    ],
)
def test_core_leaf_validators_fail_fast_without_mutation(
    contract_id: str, validator: Callable[[Any], None], value: Any, context: str
) -> None:
    before = value.model_dump()
    with pytest.raises(DppValidationError, match=context):
        validator(value)
    assert value.model_dump() == before


@pytest.mark.parametrize(
    ("contract_id", "validator", "value"),
    [
        pytest.param(
            "VALIDATION-CORE-ADDRESS-ADDRESS-VALIDATOR-CCD6BD",
            validate_address,
            Address(country="DE", town="Berlin"),
            id="VALIDATION-CORE-ADDRESS-ADDRESS-VALIDATOR-CCD6BD",
        ),
        pytest.param(
            "VALIDATION-CORE-CONTACT-CONTACT-VALIDATOR-CD435C",
            validate_contact,
            Contact(organization="ACME", email=Email(emailAddress="info@example.test")),
            id="VALIDATION-CORE-CONTACT-CONTACT-VALIDATOR-CD435C",
        ),
        pytest.param(
            "VALIDATION-CORE-ORGANIZATION-ORGANIZATION-VALIDATOR-F89B91",
            validate_organization,
            Organization(name="ACME", uri="https://example.test"),
            id="VALIDATION-CORE-ORGANIZATION-ORGANIZATION-VALIDATOR-F89B91",
        ),
        pytest.param(
            "VALIDATION-CORE-TELEPHONE-TELEPHONE-VALIDATOR-2C430B",
            validate_telephone,
            Telephone(telephoneNumber="+49 30 123"),
            id="VALIDATION-CORE-TELEPHONE-TELEPHONE-VALIDATOR-2C430B",
        ),
    ],
)
def test_core_leaf_validators_accept_valid_values_repeatedly(
    contract_id: str, validator: Callable[[Any], None], value: Any
) -> None:
    before = value.model_dump()
    validator(value)
    validator(value)
    assert value.model_dump() == before


@pytest.mark.parametrize(
    "contract_id",
    [
        pytest.param(
            "VALIDATION-CORE-ORGANIZATION-ORGANIZATION-IS-REQUIRED-01893A",
            id="VALIDATION-CORE-ORGANIZATION-ORGANIZATION-IS-REQUIRED-01893A",
        )
    ],
)
def test_organization_is_required(contract_id: str) -> None:
    with pytest.raises(DppValidationError, match="Organization is required"):
        validate_organization(None)


def test_core_aggregate_order_metadata_then_nameplate_then_documentation(
    valid_core: DppCore,
) -> None:
    metadata = PassportMetadata.model_construct(
        uniqueProductIdentifier=None, passportUpdateDates=()
    )
    core = DppCore.model_construct(
        passportMetadata=metadata,
        nameplate=Nameplate.model_construct(gtinCode=""),
        documentation=Documentation(downloadable=True),
    )
    with pytest.raises(DppValidationError, match="PassportMetadata"):
        validate_dpp_core(core)
    core = DppCore.model_construct(
        passportMetadata=valid_core.passportMetadata,
        nameplate=Nameplate.model_construct(gtinCode=""),
        documentation=Documentation(downloadable=True),
    )
    with pytest.raises(DppValidationError, match="Nameplate.gtinCode"):
        validate_dpp_core(core)
    core = DppCore.model_construct(
        passportMetadata=valid_core.passportMetadata,
        nameplate=valid_core.nameplate,
        documentation=Documentation(downloadable=True),
    )
    with pytest.raises(DppValidationError, match="downloadable"):
        validate_dpp_core(core)


@pytest.mark.parametrize(
    ("contract_id", "validator", "value"),
    [
        pytest.param(
            "VALIDATION-CORE-DOCUMENTATION-DOCUMENTATION-VALIDATOR-025B6C",
            validate_documentation,
            Documentation(digitalInstructionsLink="https://example.test/manual"),
            id="VALIDATION-CORE-DOCUMENTATION-DOCUMENTATION-VALIDATOR-025B6C",
        ),
    ],
)
def test_core_aggregate_validators_accept_valid_values(
    contract_id: str, validator: Callable[[Any], None], value: Any
) -> None:
    before = value.model_dump()
    validator(value)
    validator(value)
    assert value.model_dump() == before


@pytest.mark.parametrize(
    "contract_id",
    [
        pytest.param(
            "VALIDATION-CORE-DPP-CORE-DPP-CORE-VALIDATOR-7DA7A0",
            id="VALIDATION-CORE-DPP-CORE-DPP-CORE-VALIDATOR-7DA7A0",
        ),
        pytest.param(
            "VALIDATION-CORE-GENERAL-VALIDATION-SERVICE-F1BAD8",
            id="VALIDATION-CORE-GENERAL-VALIDATION-SERVICE-F1BAD8",
        ),
        pytest.param(
            "VALIDATION-CORE-GENERAL-VALIDATOR-5967A0",
            id="VALIDATION-CORE-GENERAL-VALIDATOR-5967A0",
        ),
    ],
)
def test_dpp_core_validator_accepts_valid_value_repeatedly(
    contract_id: str, valid_core: DppCore
) -> None:
    before = valid_core.model_dump()
    validate_dpp_core(valid_core)
    validate_dpp_core(valid_core)
    assert valid_core.model_dump() == before


@pytest.mark.parametrize(
    ("contract_id", "value", "context"),
    [
        pytest.param(
            "VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-IS-REQUIRED-D184CB",
            None,
            "PassportMetadata is required",
            id="VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-IS-REQUIRED-D184CB",
        ),
        pytest.param(
            "VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-UNIQUE-PRODUCT-IDENTIFIER-FAF1E3",
            PassportMetadata.model_construct(uniqueProductIdentifier=None, passportUpdateDates=()),
            "uniqueProductIdentifier",
            id="VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-UNIQUE-PRODUCT-IDENTIFIER-FAF1E3",
        ),
        pytest.param(
            "VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-PASSPORT-UPDATE-DATES-MUST-NOT-BE-EMP-6E5F21",
            PassportMetadata.model_construct(
                uniqueProductIdentifier=UUID(int=1), passportUpdateDates=()
            ),
            "must not be empty",
            id="VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-PASSPORT-UPDATE-DATES-MUST-NOT-BE-EMP-6E5F21",
        ),
        pytest.param(
            "VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-PASSPORT-UPDATE-DATES-5A79C5",
            PassportMetadata.model_construct(
                uniqueProductIdentifier=UUID(int=1), passportUpdateDates=(None,)
            ),
            "passportUpdateDates\\[0\\] is null",
            id="VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-PASSPORT-UPDATE-DATES-5A79C5",
        ),
        pytest.param(
            "VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-PASSPORT-UPDATE-DATES-656933",
            PassportMetadata.model_construct(
                uniqueProductIdentifier=UUID(int=1),
                passportUpdateDates=(date.today() + timedelta(days=1),),
            ),
            "is in the future",
            id="VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-PASSPORT-UPDATE-DATES-656933",
        ),
        pytest.param(
            "VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-QR-CODE-OR-DIGITAL-TAG-B484DD",
            PassportMetadata.model_construct(
                uniqueProductIdentifier=UUID(int=1),
                passportUpdateDates=(date(2024, 1, 1),),
                qrCodeOrDigitalTag=" ",
            ),
            "qrCodeOrDigitalTag",
            id="VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-QR-CODE-OR-DIGITAL-TAG-B484DD",
        ),
        pytest.param(
            "VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-EXTERNAL-DOCUMENTATION-LINK-50F759",
            PassportMetadata.model_construct(
                uniqueProductIdentifier=UUID(int=1),
                passportUpdateDates=(date(2024, 1, 1),),
                externalDocumentationLink=" ",
            ),
            "externalDocumentationLink",
            id="VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-EXTERNAL-DOCUMENTATION-LINK-50F759",
        ),
    ],
)
def test_passport_metadata_public_validator_is_fail_fast_and_non_mutating(
    contract_id: str, value: PassportMetadata | None, context: str
) -> None:
    before = value.model_dump() if value is not None else None
    with pytest.raises(DppValidationError, match=context):
        validate_passport_metadata(value)
    if value is not None:
        assert value.model_dump() == before


def test_core_general_and_error_contracts(valid_core: DppCore) -> None:
    with pytest.raises(DppValidationError, match="cannot be null"):
        validate_dpp_core(None)
    assert issubclass(DppValidationError, DppError)
    validate_dpp_core(valid_core)


@pytest.mark.parametrize(
    ("contract_id", "validator", "value"),
    [
        pytest.param(
            "VALIDATION-CORE-NAMEPLATE-NAMEPLATE-VALIDATOR-1DA7B8",
            validate_nameplate,
            Nameplate(
                gtinCode="G1",
                manufacturer=Organization(name="ACME", role=OrganizationRole.MANUFACTURER),
            ),
            id="VALIDATION-CORE-NAMEPLATE-NAMEPLATE-VALIDATOR-1DA7B8",
        ),
        pytest.param(
            "VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-VALIDATOR-BF1A4A",
            validate_passport_metadata,
            PassportMetadata(
                uniqueProductIdentifier=UUID(int=1), passportUpdateDates=(date(2024, 1, 1),)
            ),
            id="VALIDATION-CORE-PASSPORT-METADATA-PASSPORT-METADATA-VALIDATOR-BF1A4A",
        ),
    ],
)
def test_core_aggregate_leaf_validators_accept_valid_values_repeatedly(
    contract_id: str, validator: Callable[[Any], None], value: Any
) -> None:
    before = value.model_dump()
    validator(value)
    validator(value)
    assert value.model_dump() == before


@pytest.mark.parametrize(
    "contract_id",
    [
        pytest.param(
            "VALIDATION-CORE-GENERAL-CANNOT-VALIDATE-NULL-380A2C",
            id="VALIDATION-CORE-GENERAL-CANNOT-VALIDATE-NULL-380A2C",
        ),
        pytest.param(
            "VALIDATION-CORE-VALIDATION-EXCEPTION-VALIDATION-EXCEPTION-9B74AF",
            id="VALIDATION-CORE-VALIDATION-EXCEPTION-VALIDATION-EXCEPTION-9B74AF",
        ),
    ],
)
def test_core_validation_null_and_error_category_contracts(contract_id: str) -> None:
    with pytest.raises(DppValidationError, match="cannot be null"):
        validate_dpp_core(None)
