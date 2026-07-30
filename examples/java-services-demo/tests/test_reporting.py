from __future__ import annotations

import json
from uuid import UUID

from dpp_java_services_demo.reporting import (
    DemoReport,
    LegacyCompatibilityStatus,
    ScenarioResult,
    ScenarioStatus,
    has_required_failure,
    render_json,
    render_text,
)


def _report(status: ScenarioStatus = ScenarioStatus.PASSED) -> DemoReport:
    return DemoReport(
        mode="sdk",
        run_id=UUID("12345678-1234-5678-9234-567812345678"),
        results=(
            ScenarioResult(
                scenario_id="SDK-01",
                name="Complete construction",
                category="SDK_LOCAL",
                status=status,
                duration_seconds=0.125,
                summary="Complete fixture passed",
                details="typed tuple collections",
            ),
        ),
        summary="SDK capability demonstration completed",
        partial=False,
        sdk_version="0.2.1",
        sdk_location="/installed/site-packages/dpp_sdk/__init__.py",
        repo_image="repo@example",
        registry_image="registry@example",
    )


def test_text_report_contains_required_scenario_fields_and_policy_status() -> None:
    rendered = render_text(_report())

    assert "SDK-01" in rendered
    assert "Complete construction" in rendered
    assert "SDK_LOCAL" in rendered
    assert "PASSED" in rendered
    assert "0.125" in rendered
    assert "Complete fixture passed" in rendered
    assert "typed tuple collections" in rendered
    assert "LEGACY_COMPATIBILITY_NOT_RUN" in rendered


def test_json_report_is_machine_readable_and_complete() -> None:
    payload = json.loads(render_json(_report()))
    result = payload["results"][0]

    assert payload["mode"] == "sdk"
    assert payload["run_id"] == "12345678-1234-5678-9234-567812345678"
    assert payload["legacy_status"] == "LEGACY_COMPATIBILITY_NOT_RUN"
    assert payload["sdk_version"] == "0.2.1"
    assert result == {
        "scenario_id": "SDK-01",
        "name": "Complete construction",
        "category": "SDK_LOCAL",
        "status": "PASSED",
        "duration_seconds": 0.125,
        "summary": "Complete fixture passed",
        "details": "typed tuple collections",
    }


def test_required_failures_include_failed_and_not_implemented() -> None:
    assert has_required_failure(_report(ScenarioStatus.FAILED))
    assert has_required_failure(_report(ScenarioStatus.NOT_IMPLEMENTED))
    assert not has_required_failure(_report(ScenarioStatus.PASSED))
    assert _report().legacy_status is LegacyCompatibilityStatus.LEGACY_COMPATIBILITY_NOT_RUN
