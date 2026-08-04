"""Structured scenario results shared by SDK and future live-service runners."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from uuid import UUID


class ScenarioStatus(StrEnum):
    PASSED = "PASSED"
    EXPECTED_ERROR = "EXPECTED_ERROR"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class LegacyCompatibilityStatus(StrEnum):
    LEGACY_COMPATIBILITY_PASSED = "LEGACY_COMPATIBILITY_PASSED"
    LEGACY_COMPATIBILITY_FAILED = "LEGACY_COMPATIBILITY_FAILED"
    LEGACY_COMPATIBILITY_NOT_RUN = "LEGACY_COMPATIBILITY_NOT_RUN"


class InteroperabilityVerdict(StrEnum):
    PYTHON_JAVA_SERVICES_INTEROPERABILITY_VERIFIED = (
        "PYTHON_JAVA_SERVICES_INTEROPERABILITY_VERIFIED"
    )
    PYTHON_JAVA_SERVICES_INTEROPERABILITY_FAILED = "PYTHON_JAVA_SERVICES_INTEROPERABILITY_FAILED"
    PYTHON_JAVA_SERVICES_INTEROPERABILITY_INCOMPLETE = (
        "PYTHON_JAVA_SERVICES_INTEROPERABILITY_INCOMPLETE"
    )


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    name: str
    category: str
    status: ScenarioStatus
    duration_seconds: float
    summary: str
    details: str = ""


@dataclass(frozen=True)
class LiveRun:
    """Results from one stateful live flow plus non-fatal cleanup diagnostics."""

    results: tuple[ScenarioResult, ...]
    cleanup_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioTotals:
    total: int
    passed: int
    expected_error: int
    failed: int
    skipped: int
    not_implemented: int


@dataclass(frozen=True)
class DemoReport:
    """One machine- and human-readable demo execution report."""

    mode: str
    run_id: UUID
    results: tuple[ScenarioResult, ...]
    summary: str
    partial: bool
    sdk_version: str
    sdk_location: str
    repo_image: str
    registry_image: str
    sdk_wheel: str = ""
    sdk_wheel_sha256: str = ""
    legacy_status: LegacyCompatibilityStatus = (
        LegacyCompatibilityStatus.LEGACY_COMPATIBILITY_NOT_RUN
    )
    python_repo_commit: str = ""
    demo_commit: str = ""
    contract_baseline: str = ""
    repo_runtime_digest: str = ""
    registry_runtime_digest: str = ""
    repo_container_id: str = ""
    registry_container_id: str = ""
    repo_container_image_id: str = ""
    registry_container_image_id: str = ""
    maintained_repo_digest: str = ""
    maintained_registry_digest: str = ""
    image_equivalence: str = "NOT_CHECKED"
    cleanup_warnings: tuple[str, ...] = ()
    excluded_scenarios: tuple[str, ...] = ()
    started_at: str = ""
    ended_at: str = ""
    verdict: InteroperabilityVerdict = (
        InteroperabilityVerdict.PYTHON_JAVA_SERVICES_INTEROPERABILITY_INCOMPLETE
    )


def scenario_totals(results: tuple[ScenarioResult, ...]) -> ScenarioTotals:
    """Count each public scenario status without reclassifying it."""

    return ScenarioTotals(
        total=len(results),
        passed=sum(result.status is ScenarioStatus.PASSED for result in results),
        expected_error=sum(result.status is ScenarioStatus.EXPECTED_ERROR for result in results),
        failed=sum(result.status is ScenarioStatus.FAILED for result in results),
        skipped=sum(result.status is ScenarioStatus.SKIPPED for result in results),
        not_implemented=sum(result.status is ScenarioStatus.NOT_IMPLEMENTED for result in results),
    )


def has_required_failure(report: DemoReport) -> bool:
    """Return whether an executed required scenario prevents success."""

    blocking = {
        ScenarioStatus.FAILED,
        ScenarioStatus.SKIPPED,
        ScenarioStatus.NOT_IMPLEMENTED,
    }
    return any(result.status in blocking for result in report.results)


def render_text(report: DemoReport) -> str:
    """Render a compact, complete report for manual use."""

    totals = scenario_totals(report.results)
    if report.mode == "sdk":
        lines = [
            "DPP SDK offline demonstration",
            "scope: reusable Python SDK only; no Docker, Java services, or profiles",
            "schema_version: 2",
            f"mode: {report.mode}",
            f"summary: {report.summary}",
            "exit_outcome: SUCCESS"
            if not has_required_failure(report)
            else "exit_outcome: FAILURE",
            "scenarios:",
        ]
    else:
        lines = [
            f"mode: {report.mode}",
            f"run_id: {report.run_id}",
            f"summary: {report.summary}",
            f"partial: {str(report.partial).lower()}",
            f"sdk: {report.sdk_version} ({report.sdk_location})",
            f"sdk_wheel: {report.sdk_wheel}",
            f"sdk_wheel_sha256: {report.sdk_wheel_sha256}",
            f"repository_image: {report.repo_image}",
            f"registry_image: {report.registry_image}",
            f"repository_container: {report.repo_container_id} ({report.repo_container_image_id})",
            (
                f"registry_container: {report.registry_container_id} "
                f"({report.registry_container_image_id})"
            ),
            f"legacy_status: {report.legacy_status.value}",
            f"verdict: {report.verdict.value}",
            f"image_equivalence: {report.image_equivalence}",
            f"scenario_totals: total={totals.total} passed={totals.passed} failed={totals.failed} "
            f"skipped={totals.skipped} not_implemented={totals.not_implemented}",
            "scenarios:",
        ]
    for result in report.results:
        lines.append(
            f"- {result.scenario_id} | {result.name} | {result.category} | "
            f"{result.status.value} | {result.duration_seconds:.3f}s | {result.summary}"
        )
        if result.details:
            lines.append(f"  details: {result.details}")
    for warning in report.cleanup_warnings:
        lines.append(f"cleanup_warning: {warning}")
    for exclusion in report.excluded_scenarios:
        lines.append(f"excluded_scenario: {exclusion}")
    if report.mode == "sdk":
        lines.append(
            f"summary_totals: total={totals.total} pass={totals.passed} "
            f"expected_error={totals.expected_error} fail={totals.failed}"
        )
        lines.append("next_step: run with --json for machine-readable output")
    return "\n".join(lines)


def render_json(report: DemoReport) -> str:
    """Render a stable JSON report for later CI and release integration."""

    payload = asdict(report)
    if report.mode == "sdk":
        payload["schema_version"] = 2
        payload["exit_outcome"] = "SUCCESS" if not has_required_failure(report) else "FAILURE"
    payload["scenario_totals"] = asdict(scenario_totals(report.results))
    return json.dumps(payload, default=str, indent=2, sort_keys=True)
