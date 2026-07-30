"""Bounded functional readiness probes for already-running public services."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic, sleep
from typing import Protocol

from .reporting import ScenarioResult, ScenarioStatus


class HealthClient(Protocol):
    def health_check(self) -> bool: ...


def wait_for_health(
    *,
    scenario_id: str,
    name: str,
    client: HealthClient,
    timeout_seconds: float,
    endpoint: str,
    clock: Callable[[], float] = monotonic,
    pause: Callable[[float], object] = sleep,
    interval_seconds: float = 0.25,
) -> ScenarioResult:
    """Poll public health behavior until success or the configured deadline."""

    started = clock()
    deadline = started + timeout_seconds
    attempts = 0
    last_error = ""
    while True:
        attempts += 1
        try:
            if client.health_check():
                return ScenarioResult(
                    scenario_id=scenario_id,
                    name=name,
                    category="LIVE_050",
                    status=ScenarioStatus.PASSED,
                    duration_seconds=max(0.0, clock() - started),
                    summary=f"Functional readiness succeeded after {attempts} attempt(s)",
                    details=f"GET {endpoint.rstrip('/')}/health",
                )
            last_error = "health endpoint returned a non-success response"
        except Exception as exc:  # noqa: BLE001 - retained as readiness failure context
            last_error = f"{type(exc).__name__}: {exc}"
        now = clock()
        if now >= deadline:
            return ScenarioResult(
                scenario_id=scenario_id,
                name=name,
                category="LIVE_050",
                status=ScenarioStatus.FAILED,
                duration_seconds=max(0.0, now - started),
                summary=f"Functional readiness timed out after {attempts} attempt(s)",
                details=f"{endpoint.rstrip('/')}/health: {last_error}",
            )
        pause(min(interval_seconds, deadline - now))
