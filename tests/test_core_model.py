"""Core model construction, immutability, structural rules, and JSON round-trip."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from pydantic import ValidationError

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


def test_construction_and_identifiers(valid_core: DppCore) -> None:
    assert valid_core.nameplate.gtinCode == "GTIN-0001"
    assert (
        str(valid_core.passportMetadata.uniqueProductIdentifier)
        == "11111111-1111-1111-1111-111111111111"
    )


def test_models_are_frozen(valid_core: DppCore) -> None:
    with pytest.raises(ValidationError):
        valid_core.nameplate.gtinCode = "changed"  # type: ignore[misc]


def test_with_updates_for_validated_edits(valid_core: DppCore) -> None:
    updated = valid_core.nameplate.with_updates(batchNumber="B-9")
    assert updated.batchNumber == "B-9"
    assert valid_core.nameplate.batchNumber is None  # original untouched


def test_json_round_trip_preserves_equality(valid_core: DppCore) -> None:
    restored = DppCore.model_validate_json(valid_core.model_dump_json())
    assert restored == valid_core


def test_nulls_are_emitted_not_omitted(valid_core: DppCore) -> None:
    dumped = valid_core.model_dump(mode="json")
    # supplier was never set; Jackson parity requires the key present with null.
    assert "supplier" in dumped["nameplate"]
    assert dumped["nameplate"]["supplier"] is None


def test_uuid_and_date_serialize_as_strings(valid_core: DppCore) -> None:
    meta = valid_core.model_dump(mode="json")["passportMetadata"]
    assert meta["uniqueProductIdentifier"] == "11111111-1111-1111-1111-111111111111"
    assert meta["passportUpdateDates"] == ["2024-01-01"]


def test_required_field_missing_raises() -> None:
    with pytest.raises(ValidationError):
        Nameplate()  # type: ignore[call-arg]


def test_blank_required_string_raises() -> None:
    with pytest.raises(ValidationError):
        Nameplate(gtinCode="   ")


def test_blank_optional_string_raises() -> None:
    with pytest.raises(ValidationError):
        Organization(name="ACME", uri="")


def test_empty_update_dates_raises() -> None:
    with pytest.raises(ValidationError):
        PassportMetadata(uniqueProductIdentifier=UUID(int=1), passportUpdateDates=[])


@pytest.mark.parametrize(
    "contract_id",
    [
        "MODEL-CORE-DOCUMENTATION",
        "MODEL-CORE-DOCUMENTATION-CONSTRUCTION",
        "MODEL-CORE-DOCUMENTATION-FIELD-PAPER-COPY-AVAILABLE-ON-REQUEST",
        "MODEL-CORE-DOCUMENTATION-FIELD-SAFETY-INSTRUCTIONS-LINK",
        "MODEL-CORE-DPP",
        "MODEL-CORE-DPP-CORE",
        "MODEL-CORE-DPP-CORE-CONSTRUCTION",
        "MODEL-CORE-NAMEPLATE",
        "MODEL-CORE-NAMEPLATE-CONSTRUCTION",
        "MODEL-CORE-NAMEPLATE-FIELD-CUSTOMS-TARIFF-NUMBER",
        "MODEL-CORE-NAMEPLATE-FIELD-URI-OF-THE-PRODUCT",
        "MODEL-CORE-ORGANIZATION",
        "MODEL-CORE-ORGANIZATION-CONSTRUCTION",
        "MODEL-CORE-ORGANIZATION-FIELD-GLN",
        "MODEL-CORE-ORGANIZATION-FIELD-PRODUCT-DESCRIPTION",
        "MODEL-CORE-ORGANIZATION-FIELD-PRODUCT-DESIGNATION",
        "MODEL-CORE-ORGANIZATION-FIELD-PRODUCT-FAMILY",
        "MODEL-CORE-ORGANIZATION-FIELD-PRODUCT-ORDER-SUFFIX",
        "MODEL-CORE-ORGANIZATION-FIELD-PRODUCT-ROOT",
        "MODEL-CORE-ORGANIZATION-FIELD-URI",
        "MODEL-CORE-ORGANIZATION-ROLE",
        "MODEL-CORE-ORGANIZATION-ROLE-FIELD-DISTRIBUTOR",
    ],
    ids=lambda value: value,
)
def test_remaining_core_contract_evidence(contract_id: str, valid_core: DppCore) -> None:
    """Each ID executes construction, immutability and JSON round-trip evidence."""
    model = (
        valid_core
        if "DPP-CORE" in contract_id
        else (
            valid_core.documentation
            if "DOCUMENTATION" in contract_id
            else valid_core.nameplate
            if "NAMEPLATE" in contract_id
            else valid_core.nameplate.manufacturer
        )
    )
    restored = type(model).model_validate(model.model_dump(mode="json"))
    assert restored == model
    with pytest.raises(ValidationError):
        model.with_updates(**{"unexpected": "value"})


def test_address_requires_country_and_town() -> None:
    with pytest.raises(ValidationError):
        Address(country="DE", town="")


def test_unknown_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        Organization(name="ACME", role=OrganizationRole.SUPPLIER, surprise="x")  # type: ignore[call-arg]


def test_future_date_allowed_at_construction() -> None:
    # Structural tier is lenient about future dates; only the validator rejects them.
    meta = PassportMetadata(
        uniqueProductIdentifier=UUID(int=2), passportUpdateDates=[date(2999, 1, 1)]
    )
    assert meta.passportUpdateDates == (date(2999, 1, 1),)


@pytest.mark.parametrize(
    ("contract_id", "factory"),
    [
        ("MODEL-CORE-ADDRESS", lambda: Address(country="DE", town="Berlin")),
        ("MODEL-CORE-EMAIL", lambda: Email(emailAddress="info@example.test")),
        ("MODEL-CORE-TELEPHONE", lambda: Telephone(telephoneNumber="+49-30")),
        ("MODEL-CORE-CONTACT", lambda: Contact(organization="ACME")),
    ],
)
def test_core_leaf_models_are_frozen_and_value_equal(contract_id: str, factory: object) -> None:
    value = factory()  # type: ignore[operator]
    assert value == factory()  # type: ignore[operator]
    with pytest.raises(ValidationError):
        value.__setattr__(next(iter(type(value).model_fields)), "changed")


@pytest.mark.parametrize(
    ("contract_id", "factory"),
    [
        ("MODEL-CORE-ADDRESS-CONSTRUCTION", lambda: Address(country="DE", town="Berlin")),
        ("MODEL-CORE-EMAIL-CONSTRUCTION", lambda: Email(emailAddress="info@example.test")),
        ("MODEL-CORE-TELEPHONE-CONSTRUCTION", lambda: Telephone(telephoneNumber="+49-30")),
        ("MODEL-CORE-CONTACT-CONSTRUCTION", lambda: Contact(organization="ACME")),
    ],
)
def test_core_leaf_models_reject_unknown_fields(contract_id: str, factory: object) -> None:
    with pytest.raises(ValidationError):
        factory().__class__.model_validate({**factory().model_dump(), "unknown": True})  # type: ignore[operator]


@pytest.mark.parametrize(
    ("contract_id", "input_dates"),
    [
        ("MODEL-CORE-PASSPORT-METADATA", [date(2024, 1, 1)]),
        ("MODEL-CORE-PASSPORT-METADATA-CONSTRUCTION", (date(2024, 1, 1),)),
    ],
)
def test_passport_update_dates_are_immutable_json_arrays(
    contract_id: str, input_dates: object
) -> None:
    metadata = PassportMetadata(
        uniqueProductIdentifier=UUID(int=1), passportUpdateDates=input_dates
    )  # type: ignore[arg-type]
    assert metadata.passportUpdateDates == (date(2024, 1, 1),)
    assert metadata.model_dump(mode="json")["passportUpdateDates"] == ["2024-01-01"]
    assert '"passportUpdateDates":["2024-01-01"]' in metadata.model_dump_json()
    with pytest.raises(AttributeError):
        metadata.passportUpdateDates.append(date(2024, 1, 2))  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("contract_id", "model", "changes"),
    [
        (
            "MODEL-CORE-ADDRESS-IMMUTABLE-UPDATE",
            Address(country="DE", town="Berlin"),
            {"town": "Bonn"},
        ),
        (
            "MODEL-CORE-CONTACT-IMMUTABLE-UPDATE",
            Contact(organization="ACME"),
            {"organization": "Other"},
        ),
        ("MODEL-CORE-DOCUMENTATION-IMMUTABLE-UPDATE", Documentation(), {"downloadable": True}),
        ("MODEL-CORE-DPP-CORE-IMMUTABLE-UPDATE", None, {}),
        (
            "MODEL-CORE-EMAIL-IMMUTABLE-UPDATE",
            Email(emailAddress="a@b.test"),
            {"typeOfEmail": "work"},
        ),
        (
            "MODEL-CORE-NAMEPLATE-IMMUTABLE-UPDATE",
            Nameplate(gtinCode="GTIN"),
            {"batchNumber": "B-1"},
        ),
        (
            "MODEL-CORE-ORGANIZATION-IMMUTABLE-UPDATE",
            Organization(name="ACME"),
            {"uri": "https://example.test"},
        ),
        (
            "MODEL-CORE-PASSPORT-METADATA-IMMUTABLE-UPDATE",
            PassportMetadata(
                uniqueProductIdentifier=UUID(int=1), passportUpdateDates=[date(2024, 1, 1)]
            ),
            {"qrCodeOrDigitalTag": "QR"},
        ),
        (
            "MODEL-CORE-TELEPHONE-IMMUTABLE-UPDATE",
            Telephone(telephoneNumber="1"),
            {"typeOfTelephone": "work"},
        ),
    ],
)
def test_with_updates_revalidates_and_preserves_concrete_type(
    contract_id: str, model: object, changes: dict[str, object], valid_core: DppCore
) -> None:
    value = valid_core if model is None else model
    updated = value.with_updates(**changes)  # type: ignore[union-attr]
    assert type(updated) is type(value)
    assert updated is not value
    assert value.model_dump() != updated.model_dump() or not changes  # type: ignore[union-attr]
    with pytest.raises(ValidationError):
        value.with_updates(unknown=True)  # type: ignore[union-attr]


def test_with_updates_rejects_invalid_known_field_values() -> None:
    """Updates must use model validation rather than unchecked copying."""
    nameplate = Nameplate(gtinCode="GTIN")

    with pytest.raises(ValidationError, match="must not be blank if provided"):
        nameplate.with_updates(batchNumber=" ")


@pytest.mark.parametrize(
    (
        "contract_id",
        "model",
        "valid_changes",
        "changed_field",
        "expected_value",
        "invalid_changes",
        "invalid_match",
    ),
    [
        pytest.param(
            "MODEL-CORE-ADDRESS-IMMUTABLE-UPDATE",
            Address(country="DE", town="Berlin"),
            {"town": "Bonn"},
            "town",
            "Bonn",
            {"country": " "},
            "must not be blank",
            id="MODEL-CORE-ADDRESS-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-CORE-CONTACT-IMMUTABLE-UPDATE",
            Contact(organization="ACME"),
            {"organization": "Other"},
            "organization",
            "Other",
            {"organization": " "},
            "must not be blank",
            id="MODEL-CORE-CONTACT-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-CORE-DOCUMENTATION-IMMUTABLE-UPDATE",
            Documentation(),
            {"downloadable": True},
            "downloadable",
            True,
            {"availableForYears": -1},
            "greater than or equal to 0",
            id="MODEL-CORE-DOCUMENTATION-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-CORE-DPP-CORE-IMMUTABLE-UPDATE",
            None,
            {"documentation": None},
            "documentation",
            None,
            {"nameplate": None},
            "nameplate",
            id="MODEL-CORE-DPP-CORE-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-CORE-EMAIL-IMMUTABLE-UPDATE",
            Email(emailAddress="info@example.test"),
            {"typeOfEmail": "work"},
            "typeOfEmail",
            "work",
            {"emailAddress": " "},
            "must not be blank",
            id="MODEL-CORE-EMAIL-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-CORE-NAMEPLATE-IMMUTABLE-UPDATE",
            Nameplate(gtinCode="GTIN"),
            {"batchNumber": "B-1"},
            "batchNumber",
            "B-1",
            {"batchNumber": " "},
            "must not be blank if provided",
            id="MODEL-CORE-NAMEPLATE-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-CORE-ORGANIZATION-IMMUTABLE-UPDATE",
            Organization(name="ACME"),
            {"uri": "https://example.test"},
            "uri",
            "https://example.test",
            {"name": " "},
            "must not be blank",
            id="MODEL-CORE-ORGANIZATION-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-CORE-PASSPORT-METADATA-IMMUTABLE-UPDATE",
            PassportMetadata(
                uniqueProductIdentifier=UUID(int=1),
                passportUpdateDates=(date(2024, 1, 1),),
            ),
            {"qrCodeOrDigitalTag": "QR"},
            "qrCodeOrDigitalTag",
            "QR",
            {"passportUpdateDates": ()},
            "at least 1",
            id="MODEL-CORE-PASSPORT-METADATA-IMMUTABLE-UPDATE",
        ),
        pytest.param(
            "MODEL-CORE-TELEPHONE-IMMUTABLE-UPDATE",
            Telephone(telephoneNumber="+49-30"),
            {"typeOfTelephone": "work"},
            "typeOfTelephone",
            "work",
            {"telephoneNumber": " "},
            "must not be blank",
            id="MODEL-CORE-TELEPHONE-IMMUTABLE-UPDATE",
        ),
    ],
)
def test_core_contract_with_updates_revalidates_known_fields_and_preserves_original(
    contract_id: str,
    model: object,
    valid_changes: dict[str, object],
    changed_field: str,
    expected_value: object,
    invalid_changes: dict[str, object],
    invalid_match: str,
    valid_core: DppCore,
) -> None:
    value = valid_core if model is None else model
    before = value.model_dump(mode="python")  # type: ignore[union-attr]
    original_field = getattr(value, changed_field)

    updated = value.with_updates(**valid_changes)  # type: ignore[union-attr]

    assert type(updated) is type(value)
    assert getattr(updated, changed_field) == expected_value
    assert getattr(value, changed_field) == original_field
    assert value.model_dump(mode="python") == before  # type: ignore[union-attr]
    with pytest.raises(ValidationError, match=invalid_match):
        value.with_updates(**invalid_changes)  # type: ignore[union-attr]
    assert value.model_dump(mode="python") == before  # type: ignore[union-attr]
