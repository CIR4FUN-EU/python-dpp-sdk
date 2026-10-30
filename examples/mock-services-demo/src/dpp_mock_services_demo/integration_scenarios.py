"""Connected example using typed models at the edge and generic JSON clients."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from time import perf_counter
from typing import Any, Protocol

import dpp_sdk
from dpp_sdk import Dpp4FunJsonCodec, validate_dpp4fun
from dpp_sdk.clients import (
    DppApiClientError,
    DppApiResponse,
    DppRegistryClient,
    DppRepoClient,
    DppRepresentation,
    RegisterDppRequest,
)

from .config import DemoConfig
from .fixtures import DemoIdentity, build_complete_fixture
from .image_identity import RuntimeImageIdentity
from .readiness import wait_for_health


@dataclass(frozen=True)
class IntegrationStep:
    step_id: str
    stage: str
    title: str
    status: str
    evidence_class: str
    purpose: str
    input: dict[str, object]
    operation: dict[str, str]
    service: dict[str, str]
    response: dict[str, object]
    persistence_proof: dict[str, object]
    explanation: str
    why_it_matters: str
    cleanup_effect: str
    duration_seconds: float


@dataclass(frozen=True)
class IntegrationRunContext:
    run_id: object
    dpp_id: object
    product_id: str
    initial_dpp: object
    repository_created: bool = False
    repository_cleanup: str = "not_created"
    post_delete_result: str = "not_attempted"
    registration_id: str = ""


@dataclass(frozen=True)
class IntegrationReport:
    identity: DemoIdentity
    config: DemoConfig | None
    steps: tuple[IntegrationStep, ...]
    context: IntegrationRunContext
    image_identity: RuntimeImageIdentity | None = None
    image_identity_error: str = ""
    cleanup_warnings: tuple[str, ...] = ()
    profile: str = "integration"


class RepositoryClient(Protocol):
    def create_dpp(self, dpp: object, representation: DppRepresentation = ...) -> object: ...

    def read_dpp_by_id(
        self, dpp_id: str, representation: DppRepresentation = ...
    ) -> DppApiResponse: ...

    def delete_dpp_by_id(self, dpp_id: str) -> object: ...

    def close(self) -> None: ...


class RegistryClient(Protocol):
    def post_new_dpp_to_registry(self, request: RegisterDppRequest) -> object: ...

    def close(self) -> None: ...


def _step(
    index: int,
    stage: str,
    title: str,
    purpose: str,
    operation: str,
    service: dict[str, str],
    action: Any,
    *,
    input: dict[str, object],
    cleanup: str = "none",
) -> tuple[IntegrationStep, Any]:
    started = perf_counter()
    try:
        response, proof = action()
        status = "PASS"
    except Exception as exc:  # noqa: BLE001 - preserve each operation failure in report
        response = {"error": f"{type(exc).__name__}: {exc}"}
        proof = {"proof": "operation failed"}
        status = "FAIL"
    interaction = f"{service['http_method']} {service['route']}" if service else "No HTTP request"
    return (
        IntegrationStep(
            f"INT-{index:02d}",
            stage,
            title,
            status,
            "LIVE_MOCK_IMAGE" if service else "SDK_LOCAL",
            purpose,
            input,
            {"public_api": operation, "display": operation},
            {**service, "interaction": interaction},
            response if isinstance(response, dict) else {"result": response},
            proof if isinstance(proof, dict) else {"proof": proof},
            "The report records the JSON exchanged with the selected public endpoint.",
            "Applications can keep typed domain objects while clients remain JSON based.",
            cleanup,
            perf_counter() - started,
        ),
        response,
    )


def _blocked_steps() -> tuple[IntegrationStep, ...]:
    titles = (
        ("Repository readiness", "GET", "/health"),
        ("Registry readiness", "GET", "/health"),
        ("Validate typed DPP", "", ""),
        ("Create DPP", "POST", "/v1/dpps"),
        ("Read DPP JSON", "GET", "/v1/dpps/{digitalProductPassportId}"),
        ("Register DPP", "POST", "/v1/registerDPP"),
        ("Demonstrate not found mapping", "GET", "/v1/dpps/{unknownId}"),
        ("Delete created DPP", "DELETE", "/v1/dpps/{digitalProductPassportId}"),
    )
    return tuple(
        IntegrationStep(
            f"INT-{index:02d}",
            "blocked",
            title,
            "BLOCKED",
            "NOT_RUN",
            "Select a service profile before running the connected flow.",
            {"selected": "not available"},
            {"public_api": "not invoked", "display": "not invoked"},
            {"name": "not contacted", "interaction": "No service request was attempted."},
            {"result": "not attempted"},
            {"blocked_by": "missing service configuration"},
            "No live configuration was supplied.",
            "The demo does not guess service endpoints.",
            "not_created",
            0.0,
        )
        for index, (title, method, route) in enumerate(titles, 1)
    )


def run_integration_scenarios(
    identity: DemoIdentity,
    config: DemoConfig | None,
    repository: RepositoryClient | None = None,
    registry: RegistryClient | None = None,
    profile: str = "integration",
    image_identity: RuntimeImageIdentity | None = None,
    image_identity_error: str = "",
) -> IntegrationReport:
    """Run one disposable JSON API lifecycle and report cleanup explicitly."""
    if profile not in {"demo", "integration"}:
        raise ValueError(f"unsupported integration profile: {profile}")
    fixture = build_complete_fixture(identity)
    context = IntegrationRunContext(identity.run_id, identity.dpp_id, identity.product_id, fixture)
    if config is None:
        return IntegrationReport(
            identity,
            None,
            _blocked_steps(),
            context,
            image_identity,
            image_identity_error,
            profile=profile,
        )

    repo_owned, registry_owned = repository is None, registry is None
    repo = repository or DppRepoClient(config.repo_base_url)
    reg = registry or DppRegistryClient(config.registry_base_url)
    codec = Dpp4FunJsonCodec()
    wire = json.loads(codec.to_json(fixture))
    steps: list[IntegrationStep] = []
    warnings: list[str] = []
    active = False
    context = replace(context)

    try:
        probes = (
            ("repository", config.repo_base_url),
            ("registry", config.registry_base_url),
        )
        for index, (name, endpoint) in enumerate(probes, 1):
            readiness = wait_for_health(
                scenario_id=f"INT-{index:02d}",
                name=f"{name.title()} readiness",
                endpoint=endpoint,
                timeout_seconds=config.startup_timeout_seconds,
            )
            steps.append(
                IntegrationStep(
                    f"INT-{index:02d}",
                    "environment",
                    f"{name.title()} readiness",
                    "PASS" if readiness.status.value == "PASSED" else "FAIL",
                    "LIVE_MOCK_IMAGE",
                    f"Confirm {name} is reachable before making requests.",
                    {"endpoint": endpoint},
                    {"public_api": "GET /health", "display": "http.get('/health')"},
                    {
                        "name": name,
                        "http_method": "GET",
                        "route": "/health",
                        "interaction": f"GET {endpoint.rstrip('/')}/health",
                    },
                    {"details": readiness.details},
                    {"ready": readiness.status.value == "PASSED"},
                    "Readiness uses a direct HTTP health probe.",
                    "The clients expose API operations only.",
                    "none",
                    readiness.duration_seconds,
                )
            )
            if readiness.status.value != "PASSED":
                steps.extend(_blocked_steps()[index:7])
                break

        if len(steps) == 2:
            result = validate_dpp4fun(fixture)
            step, _ = _step(
                3,
                "local",
                "Validate typed DPP",
                "Check the profile at the application boundary.",
                "validate_dpp4fun(dpp)",
                {},
                lambda: (
                    (
                        {"valid": result.is_valid, "issues": len(result.issues)},
                        {"valid": result.is_valid},
                    )
                    if result.is_valid
                    else (_ for _ in ()).throw(
                        ValueError(f"DPP4Fun validation failed: {result.issues!r}")
                    )
                ),
                input={"digitalProductPassportId": str(identity.dpp_id)},
            )
            steps.append(step)

            def create() -> tuple[dict[str, object], dict[str, object]]:
                nonlocal active, context
                response = repo.create_dpp(wire, DppRepresentation.FULL)
                dpp_id = response.digital_product_passport_id
                if dpp_id != str(identity.dpp_id):
                    raise AssertionError(f"unexpected created DPP identifier {dpp_id!r}")
                active = True
                context = replace(context, repository_created=True)
                return {"digitalProductPassportId": dpp_id}, {"identifier_matches": True}

            step, _ = _step(
                4,
                "create",
                "Create DPP",
                "Send canonical DPP JSON to the repository.",
                "DppRepoClient.create_dpp(json_value, FULL)",
                {
                    "name": "repository",
                    "http_method": "POST",
                    "route": "/v1/dpps?representation=full",
                },
                create,
                input={"digitalProductPassportId": str(identity.dpp_id)},
                cleanup="deleted at end of run",
            )
            steps.append(step)

            def read() -> tuple[dict[str, object], dict[str, object]]:
                response = repo.read_dpp_by_id(str(identity.dpp_id), DppRepresentation.FULL)
                if response.payload != wire:
                    raise AssertionError("FULL JSON response differs from submitted document")
                return {
                    "digitalProductPassportId": response.payload.get("digitalProductPassportId")
                }, {"matches_submitted_json": True}

            step, _ = _step(
                5,
                "read",
                "Read DPP JSON",
                "Read the created DPP as canonical JSON.",
                "DppRepoClient.read_dpp_by_id(id, FULL)",
                {
                    "name": "repository",
                    "http_method": "GET",
                    "route": "/v1/dpps/{id}?representation=full",
                },
                read,
                input={"digitalProductPassportId": str(identity.dpp_id)},
                cleanup="deleted at end of run",
            )
            steps.append(step)

            request = RegisterDppRequest(
                unique_product_identifier=identity.product_id,
                digital_product_passport_id=str(identity.dpp_id),
                unique_economic_operator_identifier=identity.registry_sensitive_id,
                dpp_api_endpoint=f"{config.repo_base_url.rstrip('/')}/v1/dpps",
            )

            def register() -> tuple[dict[str, object], dict[str, object]]:
                nonlocal context
                response = reg.post_new_dpp_to_registry(request)
                registration_id = response.registration_id
                if not registration_id:
                    raise AssertionError("registrationId missing from response")
                context_update = replace(context, registration_id=registration_id)
                # Assigning the frozen context is local report state, not SDK state.
                context = context_update
                return {"registrationId": registration_id}, {
                    "request_fields": list(request.model_dump(by_alias=True))
                }

            step, _ = _step(
                6,
                "registry",
                "Register DPP",
                "Register endpoint metadata as JSON.",
                "DppRegistryClient.post_new_dpp_to_registry(request)",
                {"name": "registry", "http_method": "POST", "route": "/v1/registerDPP"},
                register,
                input={"digitalProductPassportId": str(identity.dpp_id)},
                cleanup="registry lifecycle is managed by its service",
            )
            steps.append(step)

            def not_found() -> tuple[dict[str, object], dict[str, object]]:
                try:
                    repo.read_dpp_by_id("missing-" + identity.run_id.hex)
                except DppApiClientError as exc:
                    return {"exception": type(exc).__name__, "http_status": exc.http_status}, {
                        "api_status": exc.status_code.value if exc.status_code else None
                    }
                raise AssertionError("unknown DPP did not produce API error")

            step, _ = _step(
                7,
                "error",
                "Demonstrate not-found mapping",
                "Show structured API error mapping.",
                "DppRepoClient.read_dpp_by_id(unknown_id)",
                {"name": "repository", "http_method": "GET", "route": "/v1/dpps/{unknownId}"},
                not_found,
                input={"digitalProductPassportId": "unknown"},
            )
            if step.status == "PASS":
                step = replace(step, status="EXPECTED_ERROR")
            steps.append(step)
    finally:
        if active:
            try:
                repo.delete_dpp_by_id(str(identity.dpp_id))
                context = replace(
                    context, repository_cleanup="deleted", post_delete_result="DELETE succeeded"
                )
            except Exception as exc:  # noqa: BLE001 - cleanup errors are report evidence
                context = replace(context, repository_cleanup="delete_failed")
                warnings.append(f"repository cleanup failed: {type(exc).__name__}: {exc}")
        if repo_owned:
            repo.close()
        if registry_owned:
            reg.close()

    steps.append(
        IntegrationStep(
            step_id="INT-08",
            stage="cleanup",
            title="Delete created DPP",
            status=(
                "PASS"
                if context.repository_cleanup == "deleted"
                else "FAIL"
                if context.repository_cleanup == "delete_failed"
                else "SKIP"
            ),
            evidence_class="LIVE_MOCK_IMAGE",
            purpose="Remove the disposable record created by this run.",
            input={"digitalProductPassportId": str(identity.dpp_id)},
            operation={
                "public_api": "DppRepoClient.delete_dpp_by_id(id)",
                "display": "repo.delete_dpp_by_id(id)",
            },
            service={
                "name": "repository",
                "http_method": "DELETE",
                "route": "/v1/dpps/{id}",
                "interaction": "DELETE /v1/dpps/{digitalProductPassportId}",
            },
            response={"repository": context.repository_cleanup},
            persistence_proof={"public_sdk_deleted": context.repository_cleanup == "deleted"},
            explanation="Cleanup runs for records created by this invocation.",
            why_it_matters="Disposable test records should not accumulate.",
            cleanup_effect=context.repository_cleanup,
            duration_seconds=0.0,
        )
    )
    return IntegrationReport(
        identity,
        config,
        tuple(steps),
        context,
        image_identity,
        image_identity_error,
        tuple(warnings),
        profile,
    )


def integration_payload(report: IntegrationReport) -> dict[str, object]:
    steps = [asdict(step) for step in report.steps]
    statuses = [step.status for step in report.steps]
    summary = {
        "total": len(statuses),
        "passed": statuses.count("PASS"),
        "expected_error": statuses.count("EXPECTED_ERROR"),
        "blocked": statuses.count("BLOCKED"),
        "skipped": statuses.count("SKIP"),
        "fail": statuses.count("FAIL"),
        "steps_completed": statuses.count("PASS"),
        "expected_errors_demonstrated": statuses.count("EXPECTED_ERROR"),
        "blocked_steps": statuses.count("BLOCKED"),
        "skipped_steps": statuses.count("SKIP"),
        "unexpected_failures": statuses.count("FAIL"),
    }
    config = report.config
    runtime = report.image_identity
    return {
        "profile": report.profile,
        "sdk": {"version": dpp_sdk.__version__},
        "services": {
            "repository": {
                "endpoint": config.repo_base_url if config else "",
                "configured_image": config.repo_image if config else "",
                "runtime_digest": runtime.repo_runtime_digest if runtime else "NOT_CAPTURED",
            },
            "registry": {
                "endpoint": config.registry_base_url if config else "",
                "configured_image": config.registry_image if config else "",
                "runtime_digest": runtime.registry_runtime_digest if runtime else "NOT_CAPTURED",
            },
        },
        "runtime_identity": {
            "status": "CAPTURED" if runtime else "NOT_CAPTURED",
            "reason": report.image_identity_error,
        },
        "steps": steps,
        "summary": summary,
        "cleanup": {
            "repository": report.context.repository_cleanup,
            "public_sdk_deleted": (
                [f"repository_dpp:{report.identity.dpp_id}"]
                if report.context.repository_cleanup == "deleted"
                else []
            ),
            "post_delete_result": report.context.post_delete_result,
            "registry": "public registration endpoint has no deregistration operation",
            "registration_id": report.context.registration_id,
            "warnings": list(report.cleanup_warnings),
        },
        "strict_verification": {"status": "NOT_RUN", "next_command": "verify"},
        "verdict": "LIVE_DEMONSTRATION_PASSED"
        if summary["fail"] == 0 and summary["blocked"] == 0
        else "LIVE_DEMONSTRATION_FAILED",
        "exit_outcome": "SUCCESS"
        if summary["fail"] == 0 and summary["blocked"] == 0
        else "FAILURE",
    }


def render_integration_text(report: IntegrationReport) -> str:
    payload = integration_payload(report)
    lines = [
        "DPP Python SDK - Live Mock-service Interoperability Example",
        f"Python SDK: {payload['sdk']['version']}",
        "Scope: typed DPP4Fun preparation and neutral JSON HTTP clients.",
        "Configured images:",
        "  repository: "
        f"{payload['services']['repository']['configured_image'] or 'not configured'}",
        f"  registry: {payload['services']['registry']['configured_image'] or 'not configured'}",
    ]
    for step in report.steps:
        lines.extend(
            (
                "",
                f"[{step.step_id}] {step.title}",
                f"Status: {step.status}",
                f"Purpose: {step.purpose}",
                f"Operation: {step.operation['display']}",
                f"Service interaction: {step.service['interaction']}",
                f"Observed result: {step.response}",
                f"Evidence: {step.persistence_proof}",
                f"Why this matters: {step.why_it_matters}",
            )
        )
    cleanup = payload["cleanup"]
    lines.extend(
        (
            "",
            "Cleanup report:",
            f"  repository={cleanup['repository']}; post_delete={cleanup['post_delete_result']}",
            f"  registry registration={cleanup['registration_id'] or 'not created'}; "
            "registry deregistration is not a supported operation",
            "Strict verification: NOT_RUN (separate command).",
        )
    )
    return "\n".join(lines)
