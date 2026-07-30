"""Command-line entry point for the isolated Java-services consumer demo."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import dpp_sdk

from .config import DemoConfig, load_config
from .controlled_scenarios import run_controlled_scenarios
from .fixtures import DemoIdentity
from .image_identity import (
    ImageIdentityReport,
    ImageInspectionError,
    capture_image_identities,
)
from .registry_scenarios import run_registry_scenarios
from .reporting import (
    DemoReport,
    InteroperabilityVerdict,
    LegacyCompatibilityStatus,
    LiveRun,
    ScenarioResult,
    ScenarioStatus,
    has_required_failure,
    render_json,
    render_text,
)
from .repository_scenarios import run_repository_scenarios
from .sdk_scenarios import run_sdk_scenarios

_CONTRACT_BASELINE = "62fe00932e184744ca3de15c47491326881e4c7a"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dpp_java_services_demo",
        description="Exercise the public Python SDK against disposable Java service images.",
    )
    parser.add_argument("mode", choices=("sdk", "services", "all", "verify"))
    parser.add_argument("--env-file", type=Path, help="Compose/demo environment profile")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Explicitly allow the optional, non-blocking 0.4.0 profile",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument("--report-file", type=Path, help="Write retained JSON evidence atomically")
    return parser


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _find_git_root(start: Path) -> Path | None:
    for candidate in (start.resolve(), *start.resolve().parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _git_commit(start: Path) -> str:
    root = _find_git_root(start)
    if root is None:
        return "UNKNOWN"
    try:
        completed = subprocess.run(
            ("git", "-C", str(root), "rev-parse", "HEAD"),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"
    return completed.stdout.strip() or "UNKNOWN"


def _installed_sdk_result(config: DemoConfig) -> ScenarioResult:
    sdk_file = Path(dpp_sdk.__file__ or "").resolve()
    git_root = _find_git_root(config.env_file)
    source_package = git_root / "src" / "dpp_sdk" if git_root is not None else None
    installed = source_package is None or not sdk_file.is_relative_to(source_package.resolve())
    return ScenarioResult(
        scenario_id="PKG-01",
        name="Installed SDK import isolation",
        category="PACKAGING",
        status=ScenarioStatus.PASSED if installed else ScenarioStatus.FAILED,
        duration_seconds=0,
        summary=(
            "dpp_sdk resolves outside the source checkout"
            if installed
            else "dpp_sdk resolves from the source checkout"
        ),
        details=str(sdk_file),
    )


def _image_results(
    identity: ImageIdentityReport | None,
    error: ImageInspectionError | None,
) -> tuple[ScenarioResult, ...]:
    if identity is None:
        return (
            ScenarioResult(
                scenario_id="IMG-01",
                name="Runtime and maintained image identity capture",
                category="IMAGE_IDENTITY",
                status=ScenarioStatus.FAILED,
                duration_seconds=0,
                summary="Image identity capture failed",
                details=str(error),
            ),
        )
    return (
        ScenarioResult(
            scenario_id="IMG-01",
            name="Runtime image digest capture",
            category="IMAGE_IDENTITY",
            status=ScenarioStatus.PASSED,
            duration_seconds=0,
            summary="Repository and registry runtime digests recorded",
            details=(
                f"repository={identity.repo_runtime_digest}; "
                f"registry={identity.registry_runtime_digest}"
            ),
        ),
        ScenarioResult(
            scenario_id="IMG-02",
            name="Maintained 0.5.0 identity comparison",
            category="IMAGE_IDENTITY",
            status=ScenarioStatus.PASSED,
            duration_seconds=0,
            summary=f"Image comparison classified {identity.equivalence.value}",
            details=(
                f"repository={identity.maintained_repo_digest}; "
                f"registry={identity.maintained_registry_digest}"
            ),
        ),
    )


def _run_live(config: DemoConfig, run_id: UUID) -> LiveRun:
    repository = run_repository_scenarios(config, DemoIdentity.from_run_id(run_id))
    registry = run_registry_scenarios(config, DemoIdentity.from_run_id(uuid4()))
    results = (*repository.results, *registry.results)
    if config.legacy:
        results = tuple(replace(result, category="LEGACY_040") for result in results)
    return LiveRun(
        results,
        (*repository.cleanup_warnings, *registry.cleanup_warnings),
    )


def _summary(mode: str) -> str:
    return {
        "sdk": "SDK capability demonstration completed",
        "services": "Java repository and registry interoperability completed",
        "all": "SDK demonstration and Java service interoperability completed",
        "verify": "Full assertion-based SDK and Java service verification completed",
    }[mode]


def _report(mode: str, config: DemoConfig) -> DemoReport:
    started_at = _now()
    run_id = uuid4()
    results: tuple[ScenarioResult, ...] = ()
    cleanup_warnings: tuple[str, ...] = ()
    image_identity: ImageIdentityReport | None = None
    image_error: ImageInspectionError | None = None

    if mode in {"sdk", "all", "verify"}:
        results = run_sdk_scenarios(run_id)
    if mode == "verify":
        results = (*results, *run_controlled_scenarios())
    if mode in {"services", "all", "verify"}:
        live = _run_live(config, run_id)
        results = (*results, *live.results)
        cleanup_warnings = live.cleanup_warnings
    if mode == "verify":
        results = (*results, _installed_sdk_result(config))
        try:
            image_identity = capture_image_identities(config)
        except ImageInspectionError as exc:
            image_error = exc
        results = (*results, *_image_results(image_identity, image_error))

    failed = any(
        result.status
        in {ScenarioStatus.FAILED, ScenarioStatus.SKIPPED, ScenarioStatus.NOT_IMPLEMENTED}
        for result in results
    )
    legacy_status = LegacyCompatibilityStatus.LEGACY_COMPATIBILITY_NOT_RUN
    if config.legacy:
        legacy_status = (
            LegacyCompatibilityStatus.LEGACY_COMPATIBILITY_FAILED
            if failed
            else LegacyCompatibilityStatus.LEGACY_COMPATIBILITY_PASSED
        )
    if mode == "verify" and not config.legacy:
        verdict = (
            InteroperabilityVerdict.PYTHON_JAVA_SERVICES_INTEROPERABILITY_FAILED
            if failed
            else InteroperabilityVerdict.PYTHON_JAVA_SERVICES_INTEROPERABILITY_VERIFIED
        )
    else:
        verdict = InteroperabilityVerdict.PYTHON_JAVA_SERVICES_INTEROPERABILITY_INCOMPLETE

    sdk_file = dpp_sdk.__file__
    commit = _git_commit(config.env_file)
    return DemoReport(
        mode=mode,
        run_id=run_id,
        results=results,
        summary=_summary(mode),
        partial=mode != "verify" or config.legacy,
        sdk_version=dpp_sdk.__version__,
        sdk_location=str(Path(sdk_file).resolve()) if sdk_file is not None else "<unknown>",
        repo_image=config.repo_image,
        registry_image=config.registry_image,
        legacy_status=legacy_status,
        python_repo_commit=commit,
        demo_commit=commit,
        contract_baseline=_CONTRACT_BASELINE,
        repo_runtime_digest=(
            image_identity.repo_runtime_digest if image_identity is not None else ""
        ),
        registry_runtime_digest=(
            image_identity.registry_runtime_digest if image_identity is not None else ""
        ),
        maintained_repo_digest=(
            image_identity.maintained_repo_digest if image_identity is not None else ""
        ),
        maintained_registry_digest=(
            image_identity.maintained_registry_digest if image_identity is not None else ""
        ),
        image_equivalence=(
            image_identity.equivalence.value if image_identity is not None else "NOT_CHECKED"
        ),
        cleanup_warnings=cleanup_warnings,
        started_at=started_at,
        ended_at=_now(),
        verdict=verdict,
    )


def _write_report(path: Path, report: DemoReport) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(f"{render_json(report)}\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


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
    if args.report_file is not None:
        _write_report(args.report_file, report)
    print(render_json(report) if args.json else render_text(report))
    if config.legacy:
        return 0
    return 1 if has_required_failure(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
