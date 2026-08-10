"""Maintainer entry points retain strict verification ownership."""

from dpp_java_services_demo.maintainer import _parser
from dpp_java_services_demo.verification.runner import run_maintainer_mode


def test_maintainer_exposes_explicit_verification_modes() -> None:
    assert _parser().parse_args(["sdk-contracts"]).mode == "sdk-contracts"
    assert _parser().parse_args(["live"]).mode == "live"
    assert _parser().parse_args(["verify"]).mode == "verify"
    assert _parser().parse_args(["verify", "--report-file", "report.json"]).report_file.name == (
        "report.json"
    )


def test_public_cli_help_keeps_legacy_modes_out_of_the_consumer_path() -> None:
    from dpp_java_services_demo.__main__ import _parser as public_parser

    help_text = public_parser().format_help()
    assert "sdk=representative offline SDK use" in help_text
    assert "full=broad live health check" not in help_text


def test_sdk_contract_mode_keeps_full_sdk_inventory() -> None:
    report = run_maintainer_mode("sdk-contracts")
    assert tuple(result.scenario_id for result in report.results) == tuple(
        f"SDK-{index:02d}" for index in range(1, 18)
    )
