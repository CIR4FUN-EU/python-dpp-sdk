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
    PYTHON_MOCK_SERVICES_INTEROPERABILITY_VERIFIED = (
        "PYTHON_MOCK_SERVICES_INTEROPERABILITY_VERIFIED"
    )
    PYTHON_MOCK_SERVICES_INTEROPERABILITY_FAILED = "PYTHON_MOCK_SERVICES_INTEROPERABILITY_FAILED"
    PYTHON_MOCK_SERVICES_INTEROPERABILITY_INCOMPLETE = (
        "PYTHON_MOCK_SERVICES_INTEROPERABILITY_INCOMPLETE"
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
class FullOperationEvidence:
    """Bounded execution evidence for one full live health-check operation."""

    scenario_id: str
    group: str
    title: str
    status: str
    public_operation: str
    selected_input: dict[str, object]
    observed_result: dict[str, object]
    persistence_or_error_proof: dict[str, object]
    explanation: str
    duration_seconds: float


_FULL_PUBLIC_OPERATIONS = {
    "REP-01": "DppRepoClient.health_check()",
    "REP-02": "DppRepoClient.create_dpp(dpp)",
    "REP-03": "DppRepoClient.read_dpp_by_id(dpp_id)",
    "REP-04": "DppRepoClient.read_compressed_dpp_by_id(dpp_id)",
    "REP-05": "DppRepoClient.read_dpp_by_product_id(product_id)",
    "REP-06": "DppRepoClient.read_dpp_version_by_id_and_date(dpp_id, at)",
    "REP-07": "DppRepoClient.read_dpp_ids_by_product_ids(product_ids, limit, cursor)",
    "REP-08": "DppRepoClient.update_dpp_by_id(dpp_id, patch)",
    "REP-09": "DppRepoClient.read_data_element(dpp_id, selector)",
    "REP-10": "DppRepoClient.update_data_element(dpp_id, selector, value)",
    "REP-11": "DppRepoClient.delete_dpp_by_id(dpp_id)",
    "REP-12": "DppRepoClient.create_dpp(dpp)",
    "REP-13": "DppRepoClient.read_dpp_by_id/read_dpp_by_product_id",
    "REP-14": "DppRepoClient.update_dpp_by_id(dpp_id, patch)",
    "REP-15": "DppRepoClient.read_data_element/update_data_element",
    "REG-01": "DppRegistryClient.health_check()",
    "REG-02": "DppRegistryClient.post_new_dpp_to_registry(request)",
    "REG-03": "DppRegistryClient.post_new_dpp_to_registry(request)",
    "REG-04": "DppRegistryClient.post_new_dpp_to_registry(request)",
    "REG-05": "DppRegistryClient.post_new_dpp_to_registry(request)",
    "REG-06": "DppRegistryClient.post_new_dpp_to_registry(request)",
    "REG-07": "DppRegistryClient.post_new_dpp_to_registry(request)",
}


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
        InteroperabilityVerdict.PYTHON_MOCK_SERVICES_INTEROPERABILITY_INCOMPLETE
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
        "       controlled client ownership. No Docker, Mock service, network, or profile is used.",
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
            "scope: reusable Python SDK only; no Docker, Mock services, or profiles",
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
            f"scenario_totals: total={totals.total} passed={totals.passed} failed={totals.failed} "
            f"skipped={totals.skipped} not_implemented={totals.not_implemented}",
            "scenarios:",
        ]
        if report.repo_image:
            lines.append(f"repository_image: {report.repo_image}")
        if report.registry_image:
            lines.append(f"registry_image: {report.registry_image}")
        if report.canonical_mode == "verify":
            if report.sdk_wheel:
                lines.append(f"sdk_wheel: {report.sdk_wheel}")
            if report.sdk_wheel_sha256:
                lines.append(f"sdk_wheel_sha256: {report.sdk_wheel_sha256}")
            if report.repo_container_id:
                lines.append(
                    "repository_container: "
                    f"{report.repo_container_id} ({report.repo_container_image_id})"
                )
            if report.registry_container_id:
                lines.append(
                    "registry_container: "
                    f"{report.registry_container_id} ({report.registry_container_image_id})"
                )
            lines.extend(
                (
                    f"legacy_status: {report.legacy_status.value}",
                    f"verdict: {report.verdict.value}",
                    f"image_equivalence: {report.image_equivalence}",
                )
            )
    if report.canonical_mode == "full":
        previous_group = ""
        for operation in (_full_operation(result, report.run_id) for result in report.results):
            if operation.group != previous_group:
                lines.extend(("", operation.group.title(), "-" * len(operation.group)))
                previous_group = operation.group
            lines.extend(
                (
                    f"- {operation.scenario_id} | {operation.title} | {operation.status}",
                    f"  operation: {operation.public_operation}",
                    f"  result: {operation.observed_result['details']}",
                )
            )
            if detailed:
                lines.extend(
                    (
                        f"  input: {operation.selected_input}",
                        f"  proof: {operation.persistence_or_error_proof['result_details']}",
                        f"  explanation: {operation.explanation}",
                    )
                )
        lines.append("next_step: run verify for strict package and image evidence")
        return "\n".join(lines)
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

    payload = _report_payload(report)
    return json.dumps(payload, default=str, indent=2, sort_keys=True)


def _identity_payload(report: DemoReport) -> dict[str, object]:
    payload: dict[str, object] = {
        "mode": report.mode,
        "canonical_mode": report.canonical_mode or report.mode,
        "requested_mode": report.requested_mode or report.mode,
    }
    if report.compatibility_alias:
        payload["compatibility_alias"] = report.compatibility_alias
    return payload


def _common_payload(report: DemoReport) -> dict[str, object]:
    payload: dict[str, object] = {
        **_identity_payload(report),
        "run_id": str(report.run_id),
        "summary": report.summary,
        "results": [asdict(result) for result in report.results],
        "scenario_totals": asdict(scenario_totals(report.results)),
    }
    if report.mode_verdict:
        payload["mode_verdict"] = report.mode_verdict
    return payload


def _sdk_payload(report: DemoReport) -> dict[str, object]:
    return {
        **_common_payload(report),
        "schema_version": 2,
        "teaching_schema_version": 1,
        "sdk_version": report.sdk_version,
        "sdk_location": report.sdk_location,
        "exit_outcome": "SUCCESS" if not has_required_failure(report) else "FAILURE",
    }


def _full_payload(report: DemoReport) -> dict[str, object]:
    payload = {
        **_common_payload(report),
        "partial": report.partial,
        "sdk_version": report.sdk_version,
        "sdk_location": report.sdk_location,
        "cleanup_warnings": list(report.cleanup_warnings),
        "excluded_scenarios": list(report.excluded_scenarios),
    }
    payload.pop("results")
    payload["operations"] = [
        asdict(_full_operation(result, report.run_id)) for result in report.results
    ]
    return {key: value for key, value in payload.items() if value != ""}


def _full_operation(result: ScenarioResult, run_id: UUID) -> FullOperationEvidence:
    is_repository = result.scenario_id.startswith("REP-")
    group = "repository" if is_repository else "registry"
    client = "DppRepoClient" if is_repository else "DppRegistryClient"
    return FullOperationEvidence(
        scenario_id=result.scenario_id,
        group=group,
        title=result.name,
        status=result.status.value,
        public_operation=_FULL_PUBLIC_OPERATIONS.get(
            result.scenario_id, f"{client} public operation"
        ),
        selected_input={"run_id": str(run_id), "scenario": result.scenario_id},
        observed_result={"summary": result.summary, "details": result.details or "not captured"},
        persistence_or_error_proof={"result_details": result.details or "not captured"},
        explanation=(
            "The health check records the exact result captured by the existing live scenario."
            if result.scenario_id.endswith("-01")
            else "The health check preserves the existing scenario's observed live result."
        ),
        duration_seconds=result.duration_seconds,
    )


def _verify_payload(report: DemoReport) -> dict[str, object]:
    payload = {
        **_common_payload(report),
        "partial": report.partial,
        "sdk_version": report.sdk_version,
        "sdk_location": report.sdk_location,
        "sdk_wheel": report.sdk_wheel,
        "sdk_wheel_sha256": report.sdk_wheel_sha256,
        "repository_image": report.repo_image,
        "registry_image": report.registry_image,
        "legacy_status": report.legacy_status.value,
        "verdict": report.verdict.value,
        "image_equivalence": report.image_equivalence,
        "cleanup_warnings": list(report.cleanup_warnings),
        "excluded_scenarios": list(report.excluded_scenarios),
        "python_repo_commit": report.python_repo_commit,
        "demo_commit": report.demo_commit,
        "contract_baseline": report.contract_baseline,
        "started_at": report.started_at,
        "ended_at": report.ended_at,
        "repo_runtime_digest": report.repo_runtime_digest,
        "registry_runtime_digest": report.registry_runtime_digest,
        "repo_container_id": report.repo_container_id,
        "registry_container_id": report.registry_container_id,
        "repo_container_image_id": report.repo_container_image_id,
        "registry_container_image_id": report.registry_container_image_id,
        "maintained_repo_digest": report.maintained_repo_digest,
        "maintained_registry_digest": report.maintained_registry_digest,
    }
    return {key: value for key, value in payload.items() if value != ""}


def _report_payload(report: DemoReport) -> dict[str, object]:
    canonical_mode = report.canonical_mode or report.mode
    if canonical_mode == "sdk":
        return _sdk_payload(report)
    if canonical_mode == "verify":
        return _verify_payload(report)
    return _full_payload(report)
