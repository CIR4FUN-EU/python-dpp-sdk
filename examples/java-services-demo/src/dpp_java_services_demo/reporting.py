"""Structured scenario results shared by SDK and future live-service runners."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from uuid import UUID


class ScenarioStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class LegacyCompatibilityStatus(StrEnum):
    LEGACY_COMPATIBILITY_PASSED = "LEGACY_COMPATIBILITY_PASSED"
    LEGACY_COMPATIBILITY_FAILED = "LEGACY_COMPATIBILITY_FAILED"
    LEGACY_COMPATIBILITY_NOT_RUN = "LEGACY_COMPATIBILITY_NOT_RUN"


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
    legacy_status: LegacyCompatibilityStatus = (
        LegacyCompatibilityStatus.LEGACY_COMPATIBILITY_NOT_RUN
    )


def has_required_failure(report: DemoReport) -> bool:
    """Return whether an executed required scenario prevents success."""

    blocking = {ScenarioStatus.FAILED, ScenarioStatus.NOT_IMPLEMENTED}
    return any(result.status in blocking for result in report.results)


def render_text(report: DemoReport) -> str:
    """Render a compact, complete report for manual use."""

    lines = [
        f"mode: {report.mode}",
        f"run_id: {report.run_id}",
        f"summary: {report.summary}",
        f"partial: {str(report.partial).lower()}",
        f"sdk: {report.sdk_version} ({report.sdk_location})",
        f"repository_image: {report.repo_image}",
        f"registry_image: {report.registry_image}",
        f"legacy_status: {report.legacy_status.value}",
        "scenarios:",
    ]
    for result in report.results:
        lines.append(
            f"- {result.scenario_id} | {result.name} | {result.category} | "
            f"{result.status.value} | {result.duration_seconds:.3f}s | {result.summary}"
        )
        if result.details:
            lines.append(f"  details: {result.details}")
    return "\n".join(lines)


def render_json(report: DemoReport) -> str:
    """Render a stable JSON report for later CI and release integration."""

    return json.dumps(asdict(report), default=str, indent=2, sort_keys=True)
