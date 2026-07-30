"""Structured scenario results shared by SDK and future live-service runners."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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
