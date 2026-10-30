"""Ordered source-backed DPP4Fun validation composition."""

from __future__ import annotations

from dpp_sdk.core import DigitalProductPassport, DppHeader, Granularity, ValidationSeverity
from dpp_sdk.dpp4fun import Dpp4Fun, Dpp4FunValidationService, Dpp4FunValidator


def test_validation_service_reports_core_then_profile_findings() -> None:
    passport = Dpp4Fun.from_passport(
        DigitalProductPassport(dpp_header=DppHeader(content_specification_ids=("unknown-profile",)))
    )
    result = Dpp4FunValidationService().validate(passport)
    assert not result.is_valid
    assert result.issues[0].path == "header.digitalProductPassportId"
    assert result.issues[-1].rule == "DPP4FUN_CONTENT_SPEC_SUPPORTED"
    assert all(issue.severity is ValidationSeverity.ERROR for issue in result.issues)


def test_profile_validator_reports_null_as_ordered_semantic_result() -> None:
    result = Dpp4FunValidator().validate(None)
    assert not result.is_valid
    assert [(item.rule, item.path, item.severity.value) for item in result.issues] == [
        ("DPP4FUN_REQUIRED", "", "ERROR")
    ]


def test_optional_characteristics_scalars_are_not_required() -> None:
    value = Dpp4Fun.create(
        DppHeader(
            digital_product_passport_id="urn:example:dpp:1",
            unique_product_identifier="urn:example:product:1",
            granularity=Granularity.MODEL,
            dpp_schema_version="1.0",
            dpp_status="active",
            economic_operator_id="urn:example:operator:1",
        )
    )
    assert Dpp4FunValidator().validate(value).is_valid
