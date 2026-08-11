from __future__ import annotations

import json
from uuid import UUID

from dpp_mock_services_demo.reporting import (
    DemoReport,
    InteroperabilityVerdict,
    LegacyCompatibilityStatus,
    ScenarioResult,
    ScenarioStatus,
    ScenarioTeaching,
    has_required_failure,
    render_json,
    render_text,
    scenario_totals,
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
                teaching=ScenarioTeaching(
                    group="MODELS_AND_IDENTIFIERS",
                    evidence_class="SDK_LOCAL",
                    purpose="Construct a typed DPP.",
                    input={"product_name": "Demo Chair"},
                    operation={"public_api": "Dpp4Fun", "display": "Dpp4Fun(...)"},
                    expected_behavior="The model is valid.",
                    observed_result={"model_type": "Dpp4Fun"},
                    explanation="The SDK creates a typed model.",
                    why_it_matters="Consumers avoid raw JSON.",
                ),
            ),
        ),
        summary="SDK capability demonstration completed",
        partial=False,
        sdk_version="0.4.0",
        sdk_location="/installed/site-packages/dpp_sdk/__init__.py",
        repo_image="repo@example",
        registry_image="registry@example",
    )


def test_text_report_contains_required_scenario_fields_and_policy_status() -> None:
    rendered = render_text(_report())

    assert "SDK-01" in rendered
    assert "Complete construction" in rendered
    assert "SDK_LOCAL" in rendered
    assert "Status: PASS" in rendered
    assert "Purpose" in rendered
    assert "Input" in rendered
    assert "SDK operation" in rendered
    assert "Observed result" in rendered
    assert "DPP Python SDK demonstration" in rendered
    assert "Next step:" in rendered


def test_json_report_is_machine_readable_and_complete() -> None:
    payload = json.loads(render_json(_report()))
    result = payload["results"][0]

    assert payload["mode"] == "sdk"
    assert payload["run_id"] == "12345678-1234-5678-9234-567812345678"
    assert payload["sdk_version"] == "0.4.0"
    assert result["scenario_id"] == "SDK-01"
    assert result["summary"] == "Complete fixture passed"
    assert result["teaching"]["operation"]["public_api"] == "Dpp4Fun"
    assert payload["teaching_schema_version"] == 1


def test_sdk_json_omits_service_only_and_alias_placeholders() -> None:
    payload = json.loads(render_json(_report()))

    assert "repo_image" not in payload
    assert "registry_image" not in payload
    assert "repo_runtime_digest" not in payload
    assert "sdk_wheel" not in payload
    assert "compatibility_alias" not in payload


def test_full_text_omits_inapplicable_empty_metadata_lines() -> None:
    report = DemoReport(
        **{
            **_report().__dict__,
            "mode": "full",
            "canonical_mode": "full",
            "requested_mode": "full",
            "mode_verdict": "FULL_INTEGRATION_PASSED",
            "results": (
                ScenarioResult(
                    scenario_id="REP-07",
                    name="Bulk product identifier lookup",
                    category="LIVE_050",
                    status=ScenarioStatus.PASSED,
                    duration_seconds=0.125,
                    summary="Bulk lookup returned one identifier",
                    details="bulk lookup returned 1 identifier",
                ),
            ),
        }
    )

    rendered = render_text(report)

    assert "sdk_wheel: " not in rendered
    assert "repository_container:  ()" not in rendered
    assert "registry_container:  ()" not in rendered


def test_full_json_projects_each_result_as_a_bounded_operation() -> None:
    report = DemoReport(
        **{
            **_report().__dict__,
            "mode": "full",
            "canonical_mode": "full",
            "requested_mode": "full",
            "mode_verdict": "FULL_INTEGRATION_PASSED",
        }
    )

    payload = json.loads(render_json(report))

    assert len(payload["operations"]) == 1
    operation = payload["operations"][0]
    assert operation["public_operation"]
    assert operation["selected_input"]
    assert operation["observed_result"]
    assert operation["persistence_or_error_proof"]


def test_full_text_renders_operation_evidence_and_detailed_explanation() -> None:
    report = DemoReport(
        **{
            **_report().__dict__,
            "mode": "full",
            "canonical_mode": "full",
            "requested_mode": "full",
            "mode_verdict": "FULL_INTEGRATION_PASSED",
            "results": (
                ScenarioResult(
                    scenario_id="REP-07",
                    name="Bulk product identifier lookup",
                    category="LIVE_050",
                    status=ScenarioStatus.PASSED,
                    duration_seconds=0.125,
                    summary="Bulk lookup returned one identifier",
                    details="bulk lookup returned 1 identifier",
                ),
            ),
        }
    )

    concise = render_text(report)
    detailed = render_text(report, detailed=True)

    assert "operation: DppRepoClient.read_dpp_ids_by_product_ids" in concise
    assert "result: bulk lookup returned 1 identifier" in concise
    assert "explanation:" not in concise
    assert "explanation:" in detailed


def test_required_failures_include_failed_and_not_implemented() -> None:
    assert has_required_failure(_report(ScenarioStatus.FAILED))
    assert has_required_failure(_report(ScenarioStatus.NOT_IMPLEMENTED))
    assert not has_required_failure(_report(ScenarioStatus.PASSED))
    assert _report().legacy_status is LegacyCompatibilityStatus.LEGACY_COMPATIBILITY_NOT_RUN


def test_release_report_totals_metadata_cleanup_and_verdict_are_serialized() -> None:
    report = DemoReport(
        **{
            **_report().__dict__,
            "python_repo_commit": "python-commit",
            "demo_commit": "demo-commit",
            "contract_baseline": "contract-baseline",
            "repo_runtime_digest": "sha256:repo",
            "registry_runtime_digest": "sha256:registry",
            "maintained_repo_digest": "sha256:repo",
            "maintained_registry_digest": "sha256:registry",
            "image_equivalence": "SAME_BUILD",
            "cleanup_warnings": ("cleanup warning",),
            "started_at": "2026-07-30T10:00:00Z",
            "ended_at": "2026-07-30T10:01:00Z",
            "verdict": InteroperabilityVerdict.PYTHON_MOCK_SERVICES_INTEROPERABILITY_VERIFIED,
            "mode": "verify",
            "canonical_mode": "verify",
            "requested_mode": "verify",
            "mode_verdict": "STRICT_VERIFICATION_PASSED",
        }
    )

    totals = scenario_totals(report.results)
    payload = json.loads(render_json(report))

    assert totals.total == 1
    assert totals.passed == 1
    assert payload["scenario_totals"]["passed"] == 1
    assert payload["cleanup_warnings"] == ["cleanup warning"]
    assert payload["image_equivalence"] == "SAME_BUILD"
    assert payload["verdict"] == "PYTHON_MOCK_SERVICES_INTEROPERABILITY_VERIFIED"
