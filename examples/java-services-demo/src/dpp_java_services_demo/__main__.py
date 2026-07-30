"""Command-line entry point for the isolated Java-services consumer demo."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

import dpp_sdk

from .config import DemoConfig, load_config
from .reporting import (
    DemoReport,
    ScenarioResult,
    ScenarioStatus,
    has_required_failure,
    render_json,
    render_text,
)
from .sdk_scenarios import run_sdk_scenarios

_LIVE_SCENARIO_ID = "LIVE-PHASE-2"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dpp_java_services_demo",
        description="Demonstrate the public Python SDK and, in phase 2, the Java service images.",
    )
    parser.add_argument("mode", choices=("sdk", "services", "all", "verify"))
    parser.add_argument("--env-file", type=Path, help="Compose/demo environment profile")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Explicitly allow the optional, non-blocking 0.4.0 profile",
    )
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable JSON report")
    return parser


def _live_placeholder() -> ScenarioResult:
    return ScenarioResult(
        scenario_id=_LIVE_SCENARIO_ID,
        name="Java repository and registry interoperability",
        category="LIVE_050",
        status=ScenarioStatus.NOT_IMPLEMENTED,
        duration_seconds=0.0,
        summary="Live interoperability belongs to the next implementation phase",
        details="No repository or registry operation was executed by this foundation",
    )


def _summary(mode: str) -> str:
    if mode == "sdk":
        return "SDK capability demonstration completed"
    if mode == "services":
        return "Live service interoperability belongs to the next implementation phase"
    if mode == "all":
        return (
            "SDK demonstration completed; live service interoperability belongs to the "
            "next implementation phase"
        )
    return (
        "SDK-only partial verification; live interoperability belongs to the "
        "next implementation phase"
    )


def _report(mode: str, config: DemoConfig) -> DemoReport:
    run_id = uuid4()
    results: tuple[ScenarioResult, ...] = ()
    if mode in {"sdk", "all", "verify"}:
        results = run_sdk_scenarios(run_id)
    if mode in {"services", "all", "verify"}:
        results = (*results, _live_placeholder())
    sdk_file = dpp_sdk.__file__
    return DemoReport(
        mode=mode,
        run_id=run_id,
        results=results,
        summary=_summary(mode),
        partial=mode != "sdk",
        sdk_version=dpp_sdk.__version__,
        sdk_location=str(Path(sdk_file).resolve()) if sdk_file is not None else "<unknown>",
        repo_image=config.repo_image,
        registry_image=config.registry_image,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run a demo mode and return its process exit code."""

    parser = _parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.env_file, legacy=args.legacy)
    except ValueError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    report = _report(args.mode, config)
    print(render_json(report) if args.json else render_text(report))
    return 1 if has_required_failure(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
