"""REP-01 through REP-15 against an already-running Java repository service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic, perf_counter, sleep
from typing import Any, Protocol
from uuid import uuid4

from dpp_sdk import Dpp4Fun, Dpp4FunJsonCodec, validate_dpp4fun
from dpp_sdk.clients import (
    CreateDppResponse,
    DeleteDppResponse,
    DppHttpClientError,
    DppRepoClient,
    ReadDppIdsResponse,
)

from .config import DemoConfig
from .fixtures import DemoIdentity, build_complete_fixture
from .readiness import wait_for_health
from .reporting import LiveRun, ScenarioResult, ScenarioStatus


class RepositoryClient(Protocol):
    def health_check(self) -> bool: ...

    def create_dpp(self, dpp: Dpp4Fun) -> CreateDppResponse: ...

    def read_dpp_by_id(self, dpp_id: str) -> Dpp4Fun: ...

    def read_compressed_dpp_by_id(self, dpp_id: str) -> Any: ...

    def read_dpp_by_product_id(self, product_id: str) -> Dpp4Fun: ...

    def read_dpp_version_by_id_and_date(self, dpp_id: str, at: datetime) -> Dpp4Fun: ...

    def read_dpp_ids_by_product_ids(
        self, product_ids: list[str], limit: int | None = None, cursor: str | None = None
    ) -> ReadDppIdsResponse: ...

    def update_dpp_by_id(self, dpp_id: str, partial_dpp: Any) -> Dpp4Fun: ...

    def read_data_element(self, dpp_id: str, element_path: str) -> Any: ...

    def update_data_element(self, dpp_id: str, element_path: str, payload: Any) -> Any: ...

    def delete_dpp_by_id(self, dpp_id: str) -> DeleteDppResponse: ...

    def close(self) -> None: ...


_NAMES = {
    "REP-01": "Repository functional readiness",
    "REP-02": "Create DPP",
    "REP-03": "Read DPP by identifier",
    "REP-04": "Read compressed DPP",
    "REP-05": "Read DPP by product identifier",
    "REP-06": "Read historical DPP snapshots",
    "REP-07": "Bulk product identifier lookup",
    "REP-08": "Merge-patch full DPP",
    "REP-09": "Read fine-grained elements",
    "REP-10": "Update fine-grained element",
    "REP-11": "Delete and verify post-delete state",
    "REP-12": "Reject duplicate creation",
    "REP-13": "Reject unknown DPP and product",
    "REP-14": "Reject invalid merge patch atomically",
    "REP-15": "Reject invalid fine-grained selectors",
}


def _result(
    scenario_id: str,
    operation: Callable[[], str],
) -> ScenarioResult:
    started = perf_counter()
    try:
        details = operation()
    except Exception as exc:  # noqa: BLE001 - live boundary records exact unexpected category
        return ScenarioResult(
            scenario_id=scenario_id,
            name=_NAMES[scenario_id],
            category="LIVE_050",
            status=ScenarioStatus.FAILED,
            duration_seconds=perf_counter() - started,
            summary="Live repository assertion failed",
            details=f"{type(exc).__name__}: {exc}",
        )
    return ScenarioResult(
        scenario_id=scenario_id,
        name=_NAMES[scenario_id],
        category="LIVE_050",
        status=ScenarioStatus.PASSED,
        duration_seconds=perf_counter() - started,
        summary="Live repository assertion passed",
        details=details,
    )


def _expected_http(operation: Callable[[], object], status_code: int, context: str) -> None:
    try:
        operation()
    except DppHttpClientError as exc:
        if exc.status_code != status_code:
            raise AssertionError(
                f"{context}: expected HTTP {status_code}, got {exc.status_code}"
            ) from exc
        return
    raise AssertionError(f"{context}: expected DppHttpClientError HTTP {status_code}")


def wait_for_repository(
    config: DemoConfig,
    *,
    client: RepositoryClient | None = None,
    clock: Callable[[], float] = monotonic,
    pause: Callable[[float], object] = sleep,
    interval_seconds: float = 0.25,
) -> ScenarioResult:
    """Wait for repository public health without managing Docker."""

    owned = client is None
    resolved = client or DppRepoClient(
        config.repo_base_url,
        Dpp4FunJsonCodec(),
        validate_dpp4fun,
    )
    try:
        return wait_for_health(
            scenario_id="REP-01",
            name=_NAMES["REP-01"],
            client=resolved,
            timeout_seconds=config.startup_timeout_seconds,
            endpoint=config.repo_base_url,
            clock=clock,
            pause=pause,
            interval_seconds=interval_seconds,
        )
    finally:
        if owned:
            resolved.close()


def _dependency_failures(start: int, reason: str) -> dict[str, ScenarioResult]:
    return {
        f"REP-{index:02d}": ScenarioResult(
            scenario_id=f"REP-{index:02d}",
            name=_NAMES[f"REP-{index:02d}"],
            category="LIVE_050",
            status=ScenarioStatus.FAILED,
            duration_seconds=0.0,
            summary="Required repository prerequisite failed",
            details=reason,
        )
        for index in range(start, 16)
    }


def run_repository_scenarios(
    config: DemoConfig,
    identity: DemoIdentity,
    *,
    client: RepositoryClient | None = None,
) -> LiveRun:
    """Run the complete maintained repository lifecycle and natural negatives."""

    owned = client is None
    resolved = client or DppRepoClient(
        config.repo_base_url,
        Dpp4FunJsonCodec(),
        validate_dpp4fun,
    )
    fixture = build_complete_fixture(identity)
    dpp_id = fixture.dpp_id
    product_id = fixture.product_id
    results: dict[str, ScenarioResult] = {}
    cleanup_warnings: list[str] = []
    active = False
    created_at: datetime | None = None
    updated_fixture: Dpp4Fun | None = None
    try:
        results["REP-01"] = wait_for_repository(config, client=resolved)
        if results["REP-01"].status is not ScenarioStatus.PASSED:
            results.update(_dependency_failures(2, "REP-01 readiness failed"))
            return LiveRun(tuple(results[f"REP-{index:02d}"] for index in range(1, 16)))

        def create() -> str:
            nonlocal active, created_at
            validate_dpp4fun(fixture)
            response = resolved.create_dpp(fixture)
            if response.dppId != dpp_id:
                raise AssertionError(f"expected created dppId {dpp_id}, got {response.dppId}")
            active = True
            created_at = datetime.now(UTC)
            return f"created dppId={dpp_id}"

        results["REP-02"] = _result("REP-02", create)
        if results["REP-02"].status is not ScenarioStatus.PASSED:
            results.update(_dependency_failures(3, "REP-02 create failed"))
            return LiveRun(tuple(results[f"REP-{index:02d}"] for index in range(1, 16)))

        def read_by_id() -> str:
            stored = resolved.read_dpp_by_id(dpp_id)
            if stored != fixture:
                raise AssertionError("decoded DPP differs from the created fixture")
            return "decoded domain value equals created fixture"

        results["REP-03"] = _result("REP-03", read_by_id)

        def read_compressed() -> str:
            compressed = resolved.read_compressed_dpp_by_id(dpp_id)
            if not isinstance(compressed, dict):
                actual_type = type(compressed).__name__
                raise AssertionError(f"expected compressed mapping, got {actual_type}")
            return f"compressed keys={sorted(compressed)}"

        results["REP-04"] = _result("REP-04", read_compressed)

        def read_by_product() -> str:
            stored = resolved.read_dpp_by_product_id(product_id)
            if stored.dpp_id != dpp_id or stored.product_id != product_id:
                raise AssertionError("product lookup returned different identifiers")
            return f"productId={product_id} resolves dppId={dpp_id}"

        results["REP-05"] = _result("REP-05", read_by_product)

        results["REP-12"] = _result(
            "REP-12",
            lambda: (
                _expected_http(lambda: resolved.create_dpp(fixture), 409, "duplicate create")
                or "duplicate create returned HTTP 409"
            ),
        )

        def missing_reads() -> str:
            _expected_http(
                lambda: resolved.read_dpp_by_id(str(uuid4())),
                404,
                "unknown DPP",
            )
            _expected_http(
                lambda: resolved.read_dpp_by_product_id(f"missing-{uuid4().hex}"),
                404,
                "unknown product",
            )
            return "unknown DPP and product returned HTTP 404"

        results["REP-13"] = _result("REP-13", missing_reads)

        def invalid_patch() -> str:
            before = resolved.read_dpp_by_id(dpp_id)
            _expected_http(
                lambda: resolved.update_dpp_by_id(
                    dpp_id,
                    {"passportMetadata": {"uniqueProductIdentifier": str(uuid4())}},
                ),
                400,
                "immutable identifier patch",
            )
            after = resolved.read_dpp_by_id(dpp_id)
            if after != before:
                raise AssertionError("invalid patch changed the stored record")
            return "HTTP 400 and stored record remained unchanged"

        results["REP-14"] = _result("REP-14", invalid_patch)

        def update_full() -> str:
            nonlocal updated_fixture
            updated_name = f"CIR4FUN Demo Chair updated {identity.run_id.hex[:8]}"
            updated_fixture = fixture.with_updates(
                characteristics=fixture.characteristics.with_updates(productName=updated_name)
            )
            returned = resolved.update_dpp_by_id(
                dpp_id,
                {"characteristics": {"productName": updated_name}},
            )
            if returned.productName != updated_name:
                raise AssertionError("merge patch response did not contain updated product name")
            if fixture.productName == updated_name:
                raise AssertionError("original fixture was mutated")
            stored = resolved.read_dpp_by_id(dpp_id)
            if stored.productName != updated_name:
                raise AssertionError("updated DPP was not persisted")
            return "merge patch persisted while original fixture remained unchanged"

        results["REP-08"] = _result("REP-08", update_full)

        def history() -> str:
            if created_at is None or updated_fixture is None:
                raise AssertionError("create/update timestamps are unavailable")
            historical = resolved.read_dpp_version_by_id_and_date(dpp_id, created_at)
            current = resolved.read_dpp_version_by_id_and_date(dpp_id, datetime.now(UTC))
            if historical.productName != fixture.productName:
                raise AssertionError("historical snapshot did not resolve the created version")
            if current.productName != updated_fixture.productName:
                raise AssertionError("current snapshot did not resolve the merge-patched version")
            return (
                f"aware UTC history resolved {historical.productName!r} "
                f"then {current.productName!r}"
            )

        results["REP-06"] = _result("REP-06", history)

        def bulk_lookup() -> str:
            response = resolved.read_dpp_ids_by_product_ids([product_id], limit=10, cursor="0")
            if response.dppIdentifiers is None or dpp_id not in response.dppIdentifiers:
                raise AssertionError("bulk lookup omitted created dppId")
            return f"bulk lookup returned {len(response.dppIdentifiers)} identifier(s)"

        results["REP-07"] = _result("REP-07", bulk_lookup)

        def read_elements() -> str:
            current_name = resolved.read_data_element(dpp_id, "$.characteristics.productName")
            material_name = resolved.read_data_element(
                dpp_id, "$.billOfMaterials.materials[0].name"
            )
            if updated_fixture is None or current_name != updated_fixture.productName:
                raise AssertionError("productName fine read differs from updated DPP")
            if fixture.billOfMaterials is None:
                raise AssertionError("complete fixture has no Bill of Materials")
            expected_material = fixture.billOfMaterials.materials[0].name
            if material_name != expected_material:
                raise AssertionError("material fine read differs from fixture")
            return "singular member and indexed BOM selectors returned expected values"

        results["REP-09"] = _result("REP-09", read_elements)

        def update_element() -> str:
            changed_name = f"Fine update {identity.run_id.hex[:8]}"
            returned = resolved.update_data_element(
                dpp_id,
                "$.characteristics.productName",
                changed_name,
            )
            if returned != changed_name:
                raise AssertionError("fine update response differs from direct scalar body")
            read_back = resolved.read_data_element(dpp_id, "$.characteristics.productName")
            if read_back != changed_name:
                raise AssertionError("fine update was not persisted")
            return "direct scalar body returned and persisted"

        results["REP-10"] = _result("REP-10", update_element)

        def fine_errors() -> str:
            cases = (
                ("characteristics.productName", 400, "malformed selector"),
                ("$.characteristics.missing", 404, "no-match selector"),
                ("$.billOfMaterials.materials[*]", 501, "wildcard selector"),
            )
            for path, status, context in cases:
                _expected_http(
                    lambda path=path: resolved.read_data_element(dpp_id, path),
                    status,
                    context,
                )
            _expected_http(
                lambda: resolved.update_data_element(dpp_id, "$", {}),
                400,
                "root replacement",
            )
            return "malformed=400, no-match=404, wildcard=501, root replacement=400"

        results["REP-15"] = _result("REP-15", fine_errors)

        def delete() -> str:
            nonlocal active
            response = resolved.delete_dpp_by_id(dpp_id)
            if response.statusCode is not None and not response.statusCode.is_success:
                raise AssertionError(f"delete returned {response.statusCode}")
            active = False
            _expected_http(lambda: resolved.read_dpp_by_id(dpp_id), 404, "post-delete read")
            return "delete succeeded and post-delete read returned HTTP 404"

        results["REP-11"] = _result("REP-11", delete)
    finally:
        if active:
            try:
                resolved.delete_dpp_by_id(dpp_id)
                active = False
            except Exception as exc:  # noqa: BLE001 - cleanup warning is report evidence
                cleanup_warnings.append(
                    f"repository cleanup for {dpp_id}: {type(exc).__name__}: {exc}"
                )
        if owned:
            resolved.close()

    ordered = tuple(results[f"REP-{index:02d}"] for index in range(1, 16))
    return LiveRun(ordered, tuple(cleanup_warnings))
