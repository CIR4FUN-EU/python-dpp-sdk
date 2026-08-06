"""Command-line entry point for the isolated Java-services consumer demo."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, distribution
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
    capture_runtime_image_identities,
)
from .integration_scenarios import (
    integration_payload,
    render_integration_text,
    run_integration_scenarios,
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
_SDK_DEMONSTRATION_RUN_ID = UUID("12345678-1234-5678-9234-567812345678")


@dataclass(frozen=True)
class ModeResolution:
    """Canonical execution identity plus a transparent compatibility request."""

    requested: str
    canonical: str
    profile: str
    compatibility_alias: str = ""


def resolve_mode(requested: str) -> ModeResolution:
    """Resolve canonical modes without silently changing a legacy evidence set."""

    canonical, profile = {
        "integration": ("demo", "integration"),
        "services": ("full", "full"),
        "all": ("full", "all"),
    }.get(requested, (requested, requested))
    return ModeResolution(
        requested=requested,
        canonical=canonical,
        profile=profile,
        compatibility_alias=requested if requested in {"integration", "services", "all"} else "",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dpp_java_services_demo",
        description="Exercise the public Python SDK against disposable Java service images.",
    )
    parser.add_argument(
        "mode",
        choices=("sdk", "demo", "full", "verify", "integration", "services", "all"),
        help=(
            "sdk=local education; demo=curated live education; full=broad live health check; "
            "verify=strict evidence. integration, services, and all are compatibility aliases."
        ),
    )
    parser.add_argument("--env-file", type=Path, help="Compose/demo environment profile")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Explicitly allow the optional, non-blocking 0.4.0 profile",
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    output.add_argument(
        "--summary",
        action="store_true",
        help="Emit the compact SDK scenario summary instead of the detailed walkthrough",
    )
    output.add_argument(
        "--detailed",
        action="store_true",
        help="Emit detailed teaching output where the selected mode supports it",
    )
    parser.add_argument("--report-file", type=Path, help="Write retained JSON evidence atomically")
    parser.add_argument(
        "--compose-project",
        help="Compose project whose serving containers must be bound to image evidence",
    )
    parser.add_argument(
        "--sdk-wheel",
        type=Path,
        help="Exact dpp-sdk wheel whose installed archive hash must match",
    )
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


def _installed_sdk_result(config: DemoConfig, sdk_wheel: Path | None) -> ScenarioResult:
    sdk_file = Path(dpp_sdk.__file__ or "").resolve()
    git_root = _find_git_root(config.env_file)
    source_package = git_root / "src" / "dpp_sdk" if git_root is not None else None
    details = str(sdk_file)
    installed = False
    if sdk_wheel is not None:
        wheel = sdk_wheel.resolve()
        try:
            wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
            installed_distribution = distribution("dpp-sdk")
            distribution_root = Path(installed_distribution.locate_file("")).resolve()
            prefix = Path(sys.prefix).resolve()
            direct_url_raw = installed_distribution.read_text("direct_url.json")
            if direct_url_raw is None:
                raise ValueError("installed distribution has no direct_url.json")
            direct_url = json.loads(direct_url_raw)
            installed_hash = direct_url.get("archive_info", {}).get("hashes", {}).get("sha256")
            editable = direct_url.get("dir_info", {}).get("editable", False)
            outside_source = source_package is None or not sdk_file.is_relative_to(
                source_package.resolve()
            )
            installed = (
                wheel.is_file()
                and sdk_file.is_relative_to(prefix)
                and distribution_root.is_relative_to(prefix)
                and outside_source
                and not editable
                and installed_hash == wheel_sha256
                and installed_distribution.version == dpp_sdk.__version__
            )
            details = (
                f"sdk={sdk_file}; wheel={wheel}; wheel_sha256={wheel_sha256}; "
                f"installed_archive_sha256={installed_hash}"
            )
        except (OSError, PackageNotFoundError, ValueError, json.JSONDecodeError) as exc:
            details = f"sdk={sdk_file}; provenance_error={type(exc).__name__}: {exc}"
    return ScenarioResult(
        scenario_id="PKG-01",
        name="Installed SDK import isolation",
        category="PACKAGING",
        status=ScenarioStatus.PASSED if installed else ScenarioStatus.FAILED,
        duration_seconds=0,
        summary=(
            "dpp_sdk is installed from the exact supplied wheel in the active environment"
            if installed
            else "dpp_sdk wheel provenance could not be proven"
        ),
        details=details,
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
            status=(
                ScenarioStatus.PASSED
                if identity.equivalence.value == "SAME_BUILD"
                else ScenarioStatus.FAILED
            ),
            duration_seconds=0,
            summary=(
                "Image comparison classified SAME_BUILD"
                if identity.equivalence.value == "SAME_BUILD"
                else "DIFFERENT_BUILD requires a separate full maintained 0.5.0 verification"
            ),
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
        "demo": "Curated live Java demonstration completed",
        "full": "Full Java repository and registry health check completed",
        "integration": "Live educational Java integration demonstration completed",
        "services": "Java repository and registry interoperability completed",
        "all": "SDK demonstration and Java service interoperability completed",
        "verify": "Full assertion-based SDK and Java service verification completed",
    }[mode]


def _load_service_config(args: argparse.Namespace) -> DemoConfig:
    """Load configuration only for a mode that contacts Java services."""

    try:
        return load_config(args.env_file, legacy=args.legacy)
    except ValueError as exc:
        raise ValueError(f"{args.mode} mode requires service configuration: {exc}") from exc


def _report(
    mode: str,
    load_service_config: Callable[[], DemoConfig] | None = None,
    *,
    execution_profile: str | None = None,
    requested_mode: str | None = None,
    compatibility_alias: str = "",
    compose_project: str | None = None,
    sdk_wheel: Path | None = None,
) -> DemoReport:
    requested_mode = requested_mode or mode
    execution_profile = execution_profile or mode
    started_at = _now()
    run_id = _SDK_DEMONSTRATION_RUN_ID if mode == "sdk" else uuid4()
    results: tuple[ScenarioResult, ...] = ()
    cleanup_warnings: tuple[str, ...] = ()
    image_identity: ImageIdentityReport | None = None
    image_error: ImageInspectionError | None = None
    config: DemoConfig | None = None

    if execution_profile in {"sdk", "all", "verify"}:
        results = run_sdk_scenarios(run_id)
    if execution_profile == "verify":
        results = (*results, *run_controlled_scenarios())
    if execution_profile in {"full", "services", "all", "verify"}:
        if load_service_config is None:
            raise ValueError(f"{mode} mode requires service configuration")
        config = load_service_config()
        live = _run_live(config, run_id)
        results = (*results, *live.results)
        cleanup_warnings = live.cleanup_warnings
    if execution_profile == "verify":
        assert config is not None
        results = (*results, _installed_sdk_result(config, sdk_wheel))
        try:
            image_identity = capture_image_identities(
                config,
                compose_project=compose_project or "",
            )
        except ImageInspectionError as exc:
            image_error = exc
        results = (*results, *_image_results(image_identity, image_error))

    failed = any(
        result.status
        in {ScenarioStatus.FAILED, ScenarioStatus.SKIPPED, ScenarioStatus.NOT_IMPLEMENTED}
        for result in results
    )
    legacy_status = LegacyCompatibilityStatus.LEGACY_COMPATIBILITY_NOT_RUN
    is_legacy = config is not None and config.legacy
    if is_legacy:
        legacy_status = (
            LegacyCompatibilityStatus.LEGACY_COMPATIBILITY_FAILED
            if failed
            else LegacyCompatibilityStatus.LEGACY_COMPATIBILITY_PASSED
        )
    if mode == "verify" and not is_legacy:
        verdict = (
            InteroperabilityVerdict.PYTHON_JAVA_SERVICES_INTEROPERABILITY_FAILED
            if failed
            else InteroperabilityVerdict.PYTHON_JAVA_SERVICES_INTEROPERABILITY_VERIFIED
        )
    else:
        verdict = InteroperabilityVerdict.PYTHON_JAVA_SERVICES_INTEROPERABILITY_INCOMPLETE

    sdk_file = dpp_sdk.__file__
    commit = _git_commit(config.env_file if config is not None else Path.cwd())
    return DemoReport(
        mode=requested_mode,
        run_id=run_id,
        results=results,
        summary=_summary(requested_mode),
        partial=execution_profile != "verify" or is_legacy,
        sdk_version=dpp_sdk.__version__,
        sdk_location=str(Path(sdk_file).resolve()) if sdk_file is not None else "<unknown>",
        sdk_wheel=str(sdk_wheel.resolve()) if sdk_wheel is not None else "",
        sdk_wheel_sha256=(
            hashlib.sha256(sdk_wheel.resolve().read_bytes()).hexdigest()
            if sdk_wheel is not None and sdk_wheel.resolve().is_file()
            else ""
        ),
        repo_image=config.repo_image if config is not None else "",
        registry_image=config.registry_image if config is not None else "",
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
        repo_container_id=(image_identity.repo_container_id if image_identity is not None else ""),
        registry_container_id=(
            image_identity.registry_container_id if image_identity is not None else ""
        ),
        repo_container_image_id=(
            image_identity.repo_container_image_id if image_identity is not None else ""
        ),
        registry_container_image_id=(
            image_identity.registry_container_image_id if image_identity is not None else ""
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
        excluded_scenarios=(
            "REG-09: no public registry read-back API",
            "REG-10: no public registry cleanup API",
        ),
        started_at=started_at,
        ended_at=_now(),
        verdict=verdict,
        mode_verdict=("SDK_DEMONSTRATION_FAILED" if failed else "SDK_DEMONSTRATION_PASSED")
        if mode == "sdk"
        else (
            "FULL_INTEGRATION_BLOCKED"
            if mode == "full"
            and any(
                result.scenario_id in {"REP-01", "REG-01"}
                and result.status is ScenarioStatus.FAILED
                for result in results
            )
            else "FULL_INTEGRATION_FAILED"
            if mode == "full" and failed
            else "FULL_INTEGRATION_PASSED"
            if mode == "full"
            else ""
        ),
        canonical_mode=mode,
        requested_mode=requested_mode,
        compatibility_alias=compatibility_alias,
    )


def _write_report(path: Path, report: DemoReport) -> None:
    _write_json_report(path, json.loads(render_json(report)))


def _write_json_report(path: Path, payload: dict[str, object]) -> None:
    """Write a JSON report through a same-directory temporary file."""

    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _annotate_live_payload(
    payload: dict[str, object], resolution: ModeResolution
) -> dict[str, object]:
    """Attach request identity without changing the evidence captured by the runner."""

    return {
        **payload,
        "canonical_mode": resolution.canonical,
        "requested_mode": resolution.requested,
        "compatibility_alias": resolution.compatibility_alias or None,
        "scenario_selection": "curated" if resolution.profile == "demo" else "legacy_connected",
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run a demo mode and return its process exit code."""

    parser = _parser()
    args = parser.parse_args(argv)
    resolution = resolve_mode(args.mode)
    try:
        if resolution.profile in {"demo", "integration"}:
            config = _load_service_config(args)
            runtime_identity = None
            identity_error = ""
            if args.compose_project:
                try:
                    runtime_identity = capture_runtime_image_identities(
                        config, compose_project=args.compose_project
                    )
                except ImageInspectionError as exc:
                    identity_error = f"{type(exc).__name__}: {exc}"
            report = run_integration_scenarios(
                DemoIdentity.from_run_id(uuid4()),
                config,
                profile=resolution.profile,
                image_identity=runtime_identity,
                image_identity_error=identity_error,
            )
            payload = _annotate_live_payload(integration_payload(report), resolution)
            if args.report_file is not None:
                _write_json_report(args.report_file, payload)
            print(
                json.dumps(payload, indent=2, sort_keys=True)
                if args.json
                else render_integration_text(report)
            )
            return 0 if payload["exit_outcome"] == "SUCCESS" else 1
        report = _report(
            resolution.canonical,
            (lambda: _load_service_config(args))
            if resolution.canonical in {"full", "all", "verify"}
            else None,
            execution_profile=resolution.profile,
            requested_mode=resolution.requested,
            compatibility_alias=resolution.compatibility_alias,
            compose_project=args.compose_project,
            sdk_wheel=args.sdk_wheel,
        )
    except ValueError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    if args.report_file is not None:
        _write_report(args.report_file, report)
    print(
        render_json(report)
        if args.json
        else render_text(report, summary=args.summary, detailed=args.detailed)
    )
    if resolution.canonical in {"full", "all", "verify"} and args.legacy:
        return 0
    return 1 if has_required_failure(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
