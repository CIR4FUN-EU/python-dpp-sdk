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
class ScenarioTeaching:
    """Structured, bounded evidence used by both SDK-only renderers."""

    group: str
    evidence_class: str
    purpose: str
    input: dict[str, object]
    operation: dict[str, str]
    expected_behavior: str
    observed_result: dict[str, object]
    explanation: str
    why_it_matters: str


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    name: str
    category: str
    status: ScenarioStatus
    duration_seconds: float
    summary: str
    details: str = ""
    teaching: ScenarioTeaching | None = None


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
    mode_verdict: str = ""
    canonical_mode: str = ""
    requested_mode: str = ""
    compatibility_alias: str = ""


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


def _append_evidence(lines: list[str], value: object, *, indent: int) -> None:
    """Render bounded JSON-native evidence without Python reprs."""

    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            lines.append(f"{prefix}{{}}")
            return
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                _append_evidence(lines, item, indent=indent + 2)
            else:
                lines.append(f"{prefix}{key}: {item}")
        return
    if isinstance(value, list):
        if not value:
            lines.append(f"{prefix}[]")
            return
        for item in value:
            if isinstance(item, dict):
                first, *rest = item.items()
                if first:
                    key, scalar = first
                    lines.append(f"{prefix}- {key}: {scalar}")
                    _append_evidence(lines, dict(rest), indent=indent + 2)
                else:
                    lines.append(f"{prefix}- {{}}")
            else:
                rendered = '""' if item == "" else str(item)
                lines.append(f"{prefix}- {rendered}")
        return
    lines.append(f"{prefix}{value!s}")


def _render_sdk_detailed(report: DemoReport) -> str:
    totals = scenario_totals(report.results)
    lines = [
        "DPP Python SDK demonstration",
        "============================",
        "",
        f"SDK version: {report.sdk_version}",
        "Mode: SDK-only",
        "Scope: typed models, validation, codecs, immutable updates, public errors, and",
        "       controlled client ownership. No Docker, Java service, network, or profile is used.",
        f"Verdict: {report.mode_verdict}",
    ]
    previous_group = ""
    for result in report.results:
        teaching = result.teaching
        if teaching is None:
            lines.extend(
                (
                    "",
                    f"[{result.scenario_id}] {result.name}",
                    "Status: FAILED",
                    f"Evidence: {result.category}",
                    "Observed result",
                    f"  {result.summary}",
                    f"  {result.details or 'No additional diagnostic was captured.'}",
                    "Explanation",
                    "  The scenario failed before it could capture its normal teaching evidence.",
                    "Why this matters",
                    "  The demonstration keeps unexpected failures visible so they can be "
                    "investigated.",
                )
            )
            continue
        if teaching.group != previous_group:
            group_title = teaching.group.replace("_", " ").title()
            lines.extend(("", group_title, "-" * len(group_title)))
            previous_group = teaching.group
        lines.extend(
            (
                "",
                f"[{result.scenario_id}] {result.name}",
                "Status: "
                f"{'PASS' if result.status is ScenarioStatus.PASSED else result.status.value}",
                f"Evidence: {teaching.evidence_class}",
                "",
                "Purpose",
                f"  {teaching.purpose}",
                "Input",
            )
        )
        _append_evidence(lines, teaching.input, indent=2)
        lines.extend(
            (
                "SDK operation",
                f"  {teaching.operation['display']}",
                "Expected behavior",
                f"  {teaching.expected_behavior}",
                "Observed result",
            )
        )
        _append_evidence(lines, teaching.observed_result, indent=2)
        lines.extend(
            (
                "Explanation",
                f"  {teaching.explanation}",
                "Why this matters",
                f"  {teaching.why_it_matters}",
            )
        )
    lines.extend(
        (
            "",
            f"Summary: total={totals.total} pass={totals.passed} "
            f"expected_error={totals.expected_error} fail={totals.failed}",
            "Next step: run with --summary for compact verification or --json for "
            "machine-readable evidence.",
        )
    )
    return "\n".join(lines)


def render_text(report: DemoReport, *, summary: bool = False, detailed: bool = False) -> str:
    """Render a compact, complete report for manual use."""

    totals = scenario_totals(report.results)
    if report.mode == "sdk" and not summary:
        return _render_sdk_detailed(report)
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
        if result.details and (detailed or report.canonical_mode != "full"):
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
        payload["teaching_schema_version"] = 1
        payload["exit_outcome"] = "SUCCESS" if not has_required_failure(report) else "FAILURE"
    payload["scenario_totals"] = asdict(scenario_totals(report.results))
    return json.dumps(payload, default=str, indent=2, sort_keys=True)
