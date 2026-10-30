"""Bounded HTTP readiness probes for already-running public services."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic, sleep

import httpx

from .reporting import ScenarioResult, ScenarioStatus


def wait_for_health(
    *,
    scenario_id: str,
    name: str,
    endpoint: str,
    timeout_seconds: float,
    client: httpx.Client | None = None,
    clock: Callable[[], float] = monotonic,
    pause: Callable[[float], object] = sleep,
    interval_seconds: float = 0.25,
) -> ScenarioResult:
    """Poll ``GET /health`` until HTTP succeeds or the configured deadline."""
    owned = client is None
    http = client or httpx.Client(timeout=2.0)
    started = clock()
    deadline = started + timeout_seconds
    attempts = 0
    last_error = ""
    url = endpoint.rstrip("/") + "/health"
    try:
        while True:
            attempts += 1
            try:
                response = http.get(url)
                if response.is_success:
                    return ScenarioResult(
                        scenario_id=scenario_id,
                        name=name,
                        category="LIVE_MOCK_IMAGE",
                        status=ScenarioStatus.PASSED,
                        duration_seconds=max(0.0, clock() - started),
                        summary=f"HTTP readiness succeeded after {attempts} attempt(s)",
                        details=f"GET {url} returned HTTP {response.status_code}",
                    )
                last_error = f"HTTP {response.status_code}"
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            now = clock()
            if now >= deadline:
                return ScenarioResult(
                    scenario_id=scenario_id,
                    name=name,
                    category="LIVE_MOCK_IMAGE",
                    status=ScenarioStatus.FAILED,
                    duration_seconds=max(0.0, now - started),
                    summary=f"HTTP readiness timed out after {attempts} attempt(s)",
                    details=f"{url}: {last_error}",
                )
            pause(min(interval_seconds, deadline - now))
    finally:
        if owned:
            http.close()
