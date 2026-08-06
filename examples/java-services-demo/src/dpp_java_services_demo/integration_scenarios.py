"""Connected, educational live Java-service walkthrough using public SDK clients only."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import dpp_sdk
from dpp_sdk import Dpp4FunJsonCodec, validate_dpp4fun
from dpp_sdk.clients import DppHttpClientError, DppRegistryClient, DppRepoClient, RegisterDppRequest

from .config import DemoConfig
from .fixtures import DemoIdentity, build_complete_fixture
from .image_identity import RuntimeImageIdentity

_INTEGRATION_STATUSES = frozenset({"PASS", "EXPECTED_ERROR", "BLOCKED", "SKIP", "FAIL"})
_PROFILE_STEP_IDS = {
    "demo": frozenset({1, 2, 3, 4, 5, 8, 10, 12, 13, 14}),
    "integration": frozenset(range(1, 15)),
}


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
class IntegrationReport:
    identity: DemoIdentity
    config: DemoConfig | None
    steps: tuple[IntegrationStep, ...]
    context: IntegrationRunContext
    image_identity: RuntimeImageIdentity | None = None
    image_identity_error: str = ""
    cleanup_warnings: tuple[str, ...] = ()
    profile: str = "integration"


@dataclass(frozen=True)
class IntegrationRunContext:
    """One generated lifecycle and the resources it owns."""

    run_id: object
    dpp_id: object
    product_id: str
    initial_dpp: object
    updated_dpp: object | None = None
    registration_id: str = ""
    repository_created: bool = False
    repository_cleanup: str = "not_created"
    post_delete_result: str = "not_attempted"
    registry_state: str = "not_attempted"


def _step(
    step_id: str,
    stage: str,
    title: str,
    purpose: str,
    operation: str,
    service: dict[str, str],
    *,
    input: dict[str, object] | None = None,
    response: dict[str, object] | None = None,
    proof: dict[str, object] | None = None,
    explanation: str = "",
    why: str = "",
    status: str = "PASS",
    cleanup: str = "none",
    duration: float = 0.0,
) -> IntegrationStep:
    if status not in _INTEGRATION_STATUSES:
        raise ValueError(f"unsupported integration status: {status}")
    if service:
        service = {
            **service,
            "interaction": f"{service['http_method']} {service['route']}",
        }
    elif status == "BLOCKED":
        service = {
            "name": "not contacted",
            "interaction": "No service request was attempted after the failed prerequisite.",
        }
    else:
        service = {
            "name": "local SDK",
            "interaction": "No external service call; this step runs in the Python SDK process.",
        }
    if response is None:
        if status == "BLOCKED":
            response = {"result": "not attempted"}
        else:
            response = {"result": "not applicable"}
    if proof is None:
        proof = (
            {"blocked_by": "an earlier failed prerequisite"}
            if status == "BLOCKED"
            else {"proof": "not applicable"}
        )
    return IntegrationStep(
        step_id,
        stage,
        title,
        status,
        "SDK_LOCAL" if stage == "local" else "LIVE_JAVA_IMAGE",
        purpose,
        input or {"selected": "not applicable"},
        {"public_api": operation, "display": operation},
        service,
        response,
        proof,
        explanation or "The displayed result was captured from this step.",
        why or "It makes the live workflow explicit and repeatable.",
        cleanup,
        duration,
    )


def _ready_response(ready: object, endpoint: str) -> tuple[dict[str, object], dict[str, object]]:
    """Require a functional public health response before the connected flow proceeds."""

    if ready is False:
        raise RuntimeError(f"health_check returned False for {endpoint}")
    if ready is not True:
        raise RuntimeError(f"health_check must return True for {endpoint}, got {ready!r}")
    return {"ready": True}, {"endpoint": endpoint}


def run_integration_scenarios(
    identity: DemoIdentity,
    config: DemoConfig | None,
    repository: Any = None,
    registry: Any = None,
    profile: str = "integration",
    image_identity: RuntimeImageIdentity | None = None,
    image_identity_error: str = "",
) -> IntegrationReport:
    """Run one DPP lifecycle; tests may pass ``None`` config to inspect blocked shape."""
    if profile not in _PROFILE_STEP_IDS:
        raise ValueError(f"unsupported integration profile: {profile}")
    selected_steps = _PROFILE_STEP_IDS[profile]
    fixture = build_complete_fixture(identity)
    context = IntegrationRunContext(
        run_id=identity.run_id,
        dpp_id=identity.dpp_id,
        product_id=identity.product_id,
        initial_dpp=fixture,
    )
    if config is None:
        steps = tuple(
            _step(
                f"INT-{i:02d}",
                "environment",
                "Configuration required",
                "Use an explicit service profile.",
                "DppRepoClient",
                {},
                status="BLOCKED",
                explanation="No live profile was supplied.",
                why="The demo never guesses an endpoint.",
            )
            for i in sorted(selected_steps)
        )
        return IntegrationReport(
            identity, None, steps, context, image_identity, image_identity_error, profile=profile
        )
    repo = repository or DppRepoClient(config.repo_base_url, Dpp4FunJsonCodec(), validate_dpp4fun)
    reg = registry or DppRegistryClient(config.registry_base_url)
    owned_repo, owned_reg, active, warnings = repository is None, registry is None, False, []
    steps: list[IntegrationStep] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def run(
        i: int,
        stage: str,
        title: str,
        purpose: str,
        operation: str,
        service: dict[str, str],
        action: Any,
        **kwargs: Any,
    ) -> Any:
        start = perf_counter()
        try:
            response, proof = action()
            steps.append(
                _step(
                    f"INT-{i:02d}",
                    stage,
                    title,
                    purpose,
                    operation,
                    service,
                    response=response,
                    proof=proof,
                    duration=perf_counter() - start,
                    **kwargs,
                )
            )
            return response
        except Exception as exc:
            steps.append(
                _step(
                    f"INT-{i:02d}",
                    stage,
                    title,
                    purpose,
                    operation,
                    service,
                    status="FAIL",
                    response={"error": f"{type(exc).__name__}: {exc}"},
                    duration=perf_counter() - start,
                    **kwargs,
                )
            )
            raise

    try:

        def create() -> tuple[dict[str, object], dict[str, object]]:
            nonlocal created_at, context
            response = repo.create_dpp(fixture)
            created_at = datetime.now(UTC)
            context = replace(context, repository_created=True, repository_cleanup="created")
            return {"dppId": str(response.dppId)}, {"submitted_dpp_id": str(identity.dpp_id)}

        def full_update() -> tuple[dict[str, object], dict[str, object]]:
            nonlocal context, updated_at
            updated = repo.update_dpp_by_id(
                str(identity.dpp_id), {"characteristics": {"productName": changed}}
            )
            context = replace(context, updated_dpp=updated)
            updated_at = datetime.now(UTC)
            return (
                {"returned_productName": updated.productName},
                {
                    "read_back_productName": repo.read_dpp_by_id(str(identity.dpp_id)).productName,
                    "original_local_productName": before,
                },
            )

        def bulk_lookup() -> tuple[dict[str, object], dict[str, object]]:
            identifiers = [
                str(value)
                for value in repo.read_dpp_ids_by_product_ids(
                    [identity.product_id], limit=10, cursor="0"
                ).dppIdentifiers
            ]
            includes_created = str(identity.dpp_id) in identifiers
            if not includes_created:
                raise AssertionError("bulk lookup did not include the created DPP")
            return {"dpp_ids": identifiers}, {"includes_created_dpp": includes_created}

        def read_by_dpp_id() -> tuple[dict[str, object], dict[str, object]]:
            read_back = repo.read_dpp_by_id(str(identity.dpp_id))
            matches_created = str(read_back.dpp_id) == str(identity.dpp_id)
            if not matches_created:
                raise AssertionError("read-back DPP ID did not match the created DPP")
            return (
                {"dppId": str(read_back.dpp_id), "productName": read_back.productName},
                {"read_back_dpp_id_matches_created": matches_created},
            )

        def read_by_product_id() -> tuple[dict[str, object], dict[str, object]]:
            resolved = repo.read_dpp_by_product_id(identity.product_id)
            matches_created = str(resolved.dpp_id) == str(identity.dpp_id)
            if not matches_created:
                raise AssertionError("product-ID lookup did not resolve the created DPP")
            return (
                {"dppId": str(resolved.dpp_id), "productId": identity.product_id},
                {"resolved_dpp_id_matches_created": matches_created},
            )

        run(
            1,
            "environment",
            "Repository readiness",
            "Confirm the repository is reachable.",
            "DppRepoClient.health_check()",
            {"name": "repository", "http_method": "GET", "route": "/health"},
            lambda: _ready_response(repo.health_check(), config.repo_base_url),
            input={"endpoint": config.repo_base_url},
            explanation="The repository answered its public health endpoint.",
            why="Business requests should follow a functional readiness check.",
        )
        run(
            2,
            "environment",
            "Registry readiness",
            "Confirm the registry is reachable.",
            "DppRegistryClient.health_check()",
            {"name": "registry", "http_method": "GET", "route": "/health"},
            lambda: _ready_response(reg.health_check(), config.registry_base_url),
            input={"endpoint": config.registry_base_url},
            explanation="The registry answered its public health endpoint.",
            why="Registration needs an available registry service.",
        )
        run(
            3,
            "local",
            "Build and validate a DPP",
            "Construct and validate the typed model before I/O.",
            "validate_dpp4fun(dpp)",
            {},
            lambda: (
                validate_dpp4fun(fixture)
                or (
                    {"model": "Dpp4Fun"},
                    {
                        "productName": fixture.productName,
                        "serialized_preview": Dpp4FunJsonCodec().to_json(fixture)[:160],
                    },
                )
            ),
            input={
                "dppId": str(identity.dpp_id),
                "productId": identity.product_id,
                "productName": fixture.productName,
            },
            explanation="This stage is local only.",
            why="Typed validation catches invalid complete documents before creation.",
        )
        run(
            4,
            "create",
            "Create the DPP",
            "Persist the validated DPP.",
            "DppRepoClient.create_dpp(dpp)",
            {"name": "repository", "http_method": "POST", "route": "/v1/dpps"},
            create,
            input={"dppId": str(identity.dpp_id), "productName": fixture.productName},
            explanation="The SDK serializes the typed DPP and decodes the response.",
            why="Applications use typed values while the Java service owns storage.",
        )
        active = True
        run(
            5,
            "read",
            "Read by DPP ID",
            "Read the stored typed DPP.",
            "DppRepoClient.read_dpp_by_id(dpp_id)",
            {
                "name": "repository",
                "http_method": "GET",
                "route": "/v1/dpps/{dppId}?representation=full",
            },
            read_by_dpp_id,
            input={"dppId": str(identity.dpp_id)},
            explanation="The full response is decoded through the public codec.",
            why="Read-back proves persistence.",
        )
        if 6 in selected_steps:
            run(
                6,
                "read",
                "Read by product ID",
                "Resolve the DPP through its product identifier.",
                "DppRepoClient.read_dpp_by_product_id(product_id)",
                {
                    "name": "repository",
                    "http_method": "GET",
                    "route": "/v1/dppsByProductId/{productId}?representation=full",
                },
                read_by_product_id,
                input={"productId": identity.product_id},
                explanation="The repository supports both public identifiers.",
                why="Consumers need identifier-based access without raw HTTP.",
            )
        if 7 in selected_steps:
            run(
                7,
                "read",
                "Bulk lookup by product ID",
                "Find generated DPP identifiers through the public bulk lookup operation.",
                "DppRepoClient.read_dpp_ids_by_product_ids(product_ids, limit, cursor)",
                {"name": "repository", "http_method": "POST", "route": "/v1/dppsByProductIds"},
                bulk_lookup,
                input={"product_ids": [identity.product_id], "limit": 10, "cursor": "0"},
                explanation="The SDK constructs the bulk request and decodes the identifier page.",
                why="Consumers can locate known product identifiers without one request per DPP.",
            )
        before = fixture.productName
        changed = f"CIR4FUN Demo Chair updated {identity.run_id.hex[:8]}"
        run(
            8,
            "update",
            "Update and read back",
            "Apply a bounded merge patch and prove it persisted.",
            "DppRepoClient.update_dpp_by_id(dpp_id, patch)",
            {"name": "repository", "http_method": "PATCH", "route": "/v1/dpps/{dppId}"},
            full_update,
            input={"before": before, "patch": {"characteristics": {"productName": changed}}},
            explanation="The server validates the resulting complete DPP.",
            why="Partial updates avoid resending unrelated fields.",
        )
        current_lookup_at = datetime.now(UTC)

        def history() -> tuple[dict[str, object], dict[str, object]]:
            historical = repo.read_dpp_version_by_id_and_date(str(identity.dpp_id), created_at)
            updated_historical = repo.read_dpp_version_by_id_and_date(
                str(identity.dpp_id), updated_at
            )
            current = repo.read_dpp_version_by_id_and_date(str(identity.dpp_id), current_lookup_at)
            if historical.productName != fixture.productName:
                raise AssertionError("historical lookup did not return the created version")
            if updated_historical.productName != changed:
                raise AssertionError(
                    "updated historical lookup did not return the full-patch version"
                )
            if current.productName != changed:
                raise AssertionError("current history lookup did not return the updated version")
            return (
                {
                    "historical_productName": historical.productName,
                    "updated_historical_productName": updated_historical.productName,
                    "current_productName": current.productName,
                },
                {
                    "created_historical_differs_from_current": historical.productName
                    != current.productName,
                    "updated_historical_matches_current": updated_historical.productName
                    == current.productName,
                },
            )

        def fine_update() -> tuple[dict[str, object], dict[str, object]]:
            nonlocal context
            updated_value = repo.update_data_element(
                str(identity.dpp_id), "$.characteristics.productName", fine_changed
            )
            updated = repo.read_dpp_by_id(str(identity.dpp_id))
            context = replace(context, updated_dpp=updated)
            return (
                {"updated_value": updated_value},
                {
                    "read_back_value": repo.read_data_element(
                        str(identity.dpp_id), "$.characteristics.productName"
                    ),
                    "full_dpp_value": updated.productName,
                },
            )

        def fine_read() -> tuple[dict[str, object], dict[str, object]]:
            value = repo.read_data_element(str(identity.dpp_id), "$.characteristics.productName")
            matches_full_patch = value == changed
            if not matches_full_patch:
                raise AssertionError("fine-grained read did not match the full update")
            return ({"value": value}, {"read_value_matches_full_patch": matches_full_patch})

        if 9 in selected_steps:
            if created_at is None or updated_at is None:
                raise AssertionError("create/update timestamps were not captured")
            run(
                9,
                "history",
                "Read history",
                "Compare original and current persisted versions.",
                "DppRepoClient.read_dpp_version_by_id_and_date(dpp_id, date)",
                {
                    "name": "repository",
                    "http_method": "GET",
                    "route": "/v1/dppsByIdAndDate/{dppId}",
                },
                history,
                input={
                    "dppId": str(identity.dpp_id),
                    "created_at_utc": created_at.isoformat(),
                    "updated_at_utc": updated_at.isoformat(),
                    "current_lookup_at_utc": current_lookup_at.isoformat(),
                },
                explanation="The public history operation takes an aware UTC instant.",
                why="Consumers can resolve an earlier persisted representation.",
            )
        run(
            10,
            "fine_grained",
            "Read one element",
            "Read the selected product name without fetching a full DPP.",
            "DppRepoClient.read_data_element(dpp_id, element_path)",
            {
                "name": "repository",
                "http_method": "GET",
                "route": "/v1/dpps/{dppId}/elements/{elementPath}",
            },
            fine_read,
            input={"selector": "$.characteristics.productName"},
            explanation="The SDK encodes the bounded selector as one path segment.",
            why="Fine-grained access can reduce response handling.",
        )
        fine_changed = f"{changed} fine"
        if 11 in selected_steps:
            run(
                11,
                "fine_grained",
                "Update one element and read it back",
                "Update the selected product name without replacing the full DPP.",
                "DppRepoClient.update_data_element(dpp_id, element_path, value)",
                {
                    "name": "repository",
                    "http_method": "PATCH",
                    "route": "/v1/dpps/{dppId}/elements/{elementPath}",
                },
                fine_update,
                input={"selector": "$.characteristics.productName", "value": fine_changed},
                explanation=(
                    "The SDK sends the selected element as an encoded dynamic path segment."
                ),
                why=(
                    "Consumers can make a narrow, traceable change when the public service "
                    "supports it."
                ),
            )
        request = RegisterDppRequest(
            uniqueProductIdentifier=identity.product_id,
            digitalProductPassportId=str(identity.dpp_id),
            uniqueEconomicOperatorIdentifier=identity.registry_sensitive_id,
            dppApiEndpoint=config.repo_base_url,
        )

        def register() -> tuple[dict[str, object], dict[str, object]]:
            nonlocal context
            registration = reg.post_new_dpp_to_registry(request)
            context = replace(
                context,
                registration_id=registration.registrationId,
                registry_state="registered_retained_no_public_cleanup",
            )
            return (
                {"registrationId": registration.registrationId},
                {"registry_read_back": "not supported by public SDK"},
            )

        run(
            12,
            "registry",
            "Register the DPP",
            "Register the repository-backed DPP.",
            "DppRegistryClient.post_new_dpp_to_registry(request)",
            {"name": "registry", "http_method": "POST", "route": "/v1/registerDPP"},
            register,
            input=request.model_dump(),
            explanation="The registry verifies the referenced repository DPP.",
            why="Registration connects public DPP metadata to a repository endpoint.",
        )

        def invalid() -> tuple[dict[str, object], dict[str, object]]:
            old = repo.read_dpp_by_id(str(identity.dpp_id)).productName
            try:
                repo.update_dpp_by_id(
                    str(identity.dpp_id), {"passportMetadata": {"uniqueProductIdentifier": "bad"}}
                )
            except DppHttpClientError as exc:
                return {"exception": "DppHttpClientError", "http_status": exc.status_code}, {
                    "unchanged": repo.read_dpp_by_id(str(identity.dpp_id)).productName == old
                }
            raise AssertionError("invalid patch accepted")

        if 13 in selected_steps:
            response, proof = invalid()
            steps.append(
                _step(
                    "INT-13",
                    "error",
                    "Reject invalid patch atomically",
                    "Show a rejected patch does not change storage.",
                    "DppRepoClient.update_dpp_by_id(dpp_id, patch)",
                    {"name": "repository", "http_method": "PATCH", "route": "/v1/dpps/{dppId}"},
                    input={"patch": {"passportMetadata": {"uniqueProductIdentifier": "bad"}}},
                    response=response,
                    proof=proof,
                    status="EXPECTED_ERROR",
                    explanation="The service rejected an immutable identifier change.",
                    why="Atomic rejection prevents partial corrupted state.",
                )
            )
    except Exception:  # noqa: BLE001 - the report records the failed step and blocks dependents
        pass
    finally:
        if active:
            try:
                repo.delete_dpp_by_id(str(identity.dpp_id))
                active = False
                try:
                    repo.read_dpp_by_id(str(identity.dpp_id))
                    raise AssertionError("deleted DPP remained readable")
                except DppHttpClientError as exc:
                    if exc.status_code != 404:
                        raise
                steps.append(
                    _step(
                        "INT-14",
                        "cleanup",
                        "Delete the demonstration DPP",
                        "Remove the repository record created for this run.",
                        "DppRepoClient.delete_dpp_by_id(dpp_id)",
                        {
                            "name": "repository",
                            "http_method": "DELETE",
                            "route": "/v1/dpps/{dppId}",
                        },
                        input={"dppId": str(identity.dpp_id)},
                        response={"deleted": True},
                        proof={"post_delete_read": "HTTP 404"},
                        explanation="Registry cleanup is unavailable through the public SDK.",
                        why="A generated identity makes cleanup safe and scoped.",
                        cleanup="repository deleted; registry cleanup not supported",
                    )
                )
                context = replace(
                    context,
                    repository_cleanup="deleted",
                    post_delete_result="HTTP 404",
                )
            except Exception as exc:
                warnings.append(f"repository cleanup failed: {type(exc).__name__}: {exc}")
                context = replace(context, repository_cleanup="delete_failed")
        if owned_reg:
            reg.close()
        if owned_repo:
            repo.close()
    for i in sorted(selected_steps):
        if any(step.step_id == f"INT-{i:02d}" for step in steps):
            continue
        steps.append(
            _step(
                f"INT-{i:02d}",
                "blocked",
                "Prerequisite failed",
                "A prior live step failed.",
                "not executed",
                {},
                status="BLOCKED",
                explanation="The connected flow stopped safely.",
                why="Dependent operations must not be reported as passed.",
            )
        )
    steps.sort(key=lambda step: step.step_id)
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
    counts = {
        key: sum(step["status"] == key for step in steps)
        for key in ("PASS", "EXPECTED_ERROR", "BLOCKED", "SKIP", "FAIL")
    }
    return {
        "schema_version": 1,
        "report_type": "live_demonstration"
        if report.profile == "demo"
        else "live_integration_demonstration",
        "mode": report.profile,
        "run_id": str(report.identity.run_id),
        "sdk": {"version": dpp_sdk.__version__, "location": str(dpp_sdk.__file__)},
        "services": {
            "repository": {
                "endpoint": report.config.repo_base_url if report.config else "",
                "configured_image": report.config.repo_image if report.config else "",
                "runtime_digest": (
                    report.image_identity.repo_runtime_digest
                    if report.image_identity
                    else "not captured"
                ),
            },
            "registry": {
                "endpoint": report.config.registry_base_url if report.config else "",
                "configured_image": report.config.registry_image if report.config else "",
                "runtime_digest": (
                    report.image_identity.registry_runtime_digest
                    if report.image_identity
                    else "not captured"
                ),
            },
        },
        "image_identity_error": report.image_identity_error,
        "runtime_identity": {
            "status": "CAPTURED" if report.image_identity else "NOT_CAPTURED",
            "reason": report.image_identity_error or "No Compose project was supplied for capture.",
        },
        "steps": steps,
        "summary": {
            "total": len(steps),
            "passed": counts["PASS"],
            "expected_error": counts["EXPECTED_ERROR"],
            "blocked": counts["BLOCKED"],
            "skipped": counts["SKIP"],
            "fail": counts["FAIL"],
            "steps_completed": len(steps) - counts["BLOCKED"] - counts["SKIP"],
            "expected_errors_demonstrated": counts["EXPECTED_ERROR"],
            "blocked_steps": counts["BLOCKED"],
            "skipped_steps": counts["SKIP"],
            "unexpected_failures": counts["FAIL"],
        },
        "cleanup": {
            "repository": report.context.repository_cleanup,
            "public_sdk_deleted": (
                [f"repository_dpp:{report.context.dpp_id}"]
                if report.context.repository_cleanup == "deleted"
                else []
            ),
            "post_delete_result": report.context.post_delete_result,
            "registry": "not_supported_public_api",
            "registry_state": report.context.registry_state,
            "docker_project_cleanup": "separate operator responsibility",
            "warnings": list(report.cleanup_warnings),
        },
        "strict_verification": {"status": "NOT_RUN", "next_command": "verify"},
        "verdict": (
            "LIVE_DEMONSTRATION_PASSED"
            if report.profile == "demo" and not counts["FAIL"] and not counts["BLOCKED"]
            else "LIVE_DEMONSTRATION_BLOCKED"
            if report.profile == "demo" and counts["BLOCKED"] and not counts["FAIL"]
            else "LIVE_DEMONSTRATION_FAILED"
            if report.profile == "demo"
            else "LIVE_INTEGRATION_DEMONSTRATION_PASSED"
            if not counts["FAIL"] and not counts["BLOCKED"]
            else "LIVE_INTEGRATION_DEMONSTRATION_FAILED"
        ),
        "exit_outcome": "SUCCESS" if not counts["FAIL"] and not counts["BLOCKED"] else "FAILURE",
    }


def render_integration_text(report: IntegrationReport) -> str:
    payload = integration_payload(report)
    lines = [
        "DPP Python SDK - Live Java Integration Demonstration",
        "=" * 52,
        f"Python SDK: {payload['sdk']['version']}",
        "Mode: Live educational walkthrough",
        "Scope: selected public SDK calls against already-running Java services.",
        "Configured images:",
        "  repository: "
        f"{payload['services']['repository']['configured_image'] or 'not configured'}",
        f"  registry: {payload['services']['registry']['configured_image'] or 'not configured'}",
        "Runtime digests:",
        f"  repository: {payload['services']['repository']['runtime_digest']}",
        f"  registry: {payload['services']['registry']['runtime_digest']}",
    ]
    if payload["runtime_identity"]["status"] == "NOT_CAPTURED":
        lines.append(f"  reason: {payload['runtime_identity']['reason']}")
    stage_headings = {
        "environment": "Environment and readiness",
        "local": "Local DPP preparation",
        "create": "Repository creation and reads",
        "read": "Repository creation and reads",
        "update": "Updates and history",
        "history": "Updates and history",
        "fine_grained": "Fine-grained access",
        "registry": "Registry interaction",
        "error": "Expected errors",
        "cleanup": "Cleanup",
        "blocked": "Blocked steps",
    }
    previous_heading = ""
    for step in report.steps:
        heading = stage_headings.get(step.stage, step.stage.replace("_", " ").title())
        if heading != previous_heading:
            lines += ["", heading, "-" * len(heading)]
            previous_heading = heading
        lines += [
            "",
            f"[{step.step_id}] {step.title}",
            f"Status: {step.status}",
            f"Evidence: {step.evidence_class}",
            "Purpose",
            f"  {step.purpose}",
            "Input",
        ]
        lines += [f"  {k}: {v}" for k, v in step.input.items()]
        lines += ["SDK operation", f"  {step.operation['display']}"]
        lines += ["Service interaction", f"  {step.service['interaction']}"]
        lines += ["Observed result"]
        lines += [f"  {k}: {v}" for k, v in step.response.items()]
        lines += (
            ["Persistence proof"]
            + [f"  {k}: {v}" for k, v in step.persistence_proof.items()]
            + [
                "Explanation",
                f"  {step.explanation}",
                "Why this matters",
                f"  {step.why_it_matters}",
            ]
        )
    lines += [
        "",
        "Summary:",
        "  steps completed={steps_completed}; expected errors demonstrated="
        "{expected_errors_demonstrated}; blocked steps={blocked_steps}; skipped steps="
        "{skipped_steps}; unexpected failures={unexpected_failures}".format(**payload["summary"]),
        "Cleanup report:",
        "  repository={repository}; post_delete={post_delete_result}; public_sdk_deleted="
        "{public_sdk_deleted}".format(**payload["cleanup"]),
        "  registry=not supported by public SDK; state={registry_state}; docker project cleanup="
        "separate operator responsibility".format(**payload["cleanup"]),
        "Strict verification: NOT_RUN (separate command).",
        "Next step: run verify with --compose-project and --sdk-wheel for strict evidence.",
    ]
    return "\n".join(lines)
