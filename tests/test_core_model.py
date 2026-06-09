"""Core model construction, immutability, structural rules, and JSON round-trip."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from pydantic import ValidationError

from dpp_sdk.core.model import (
    Address,
    DppCore,
    Nameplate,
    Organization,
    OrganizationRole,
    PassportMetadata,
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


def test_model_copy_for_edits(valid_core: DppCore) -> None:
    updated = valid_core.nameplate.model_copy(update={"batchNumber": "B-9"})
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
    assert meta.passportUpdateDates == [date(2999, 1, 1)]
