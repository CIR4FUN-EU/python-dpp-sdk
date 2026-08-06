from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from dpp_sdk.clients import DppHttpClientError

from dpp_java_services_demo.config import DemoConfig
from dpp_java_services_demo.fixtures import DemoIdentity
from dpp_java_services_demo.image_identity import RuntimeImageIdentity
from dpp_java_services_demo.integration_scenarios import (
    IntegrationRunContext,
    integration_payload,
    render_integration_text,
    run_integration_scenarios,
)


class _StatefulRepository:
    def __init__(self, *, ready: object = True) -> None:
        self.ready = ready
        self.original = None
        self.current = None
        self.history_reads = 0
        self.create_calls = 0

    def health_check(self) -> object:
        return self.ready

    def create_dpp(self, dpp: object) -> SimpleNamespace:
        self.create_calls += 1
        self.original = self.current = dpp
        return SimpleNamespace(dppId=dpp.dpp_id)

    def _read(self, dpp_id: str) -> object:
        if self.current is None or dpp_id != self.current.dpp_id:
            raise DppHttpClientError("missing", 404, "{}")
        return self.current

    def read_dpp_by_id(self, dpp_id: str) -> object:
        return self._read(dpp_id)

    def read_dpp_by_product_id(self, product_id: str) -> object:
        if self.current is None or product_id != self.current.product_id:
            raise DppHttpClientError("missing", 404, "{}")
        return self.current

    def read_dpp_ids_by_product_ids(
        self, product_ids: list[str], *, limit: int, cursor: str
    ) -> SimpleNamespace:
        assert limit == 10 and cursor == "0"
        identifiers = [self.current.dpp_id] if self.current.product_id in product_ids else []
        return SimpleNamespace(dppIdentifiers=identifiers)

    def update_dpp_by_id(self, dpp_id: str, patch: object) -> object:
        current = self._read(dpp_id)
        if "passportMetadata" in patch:
            raise DppHttpClientError("invalid patch", 400, "{}")
        characteristics = current.characteristics.with_updates(
            productName=patch["characteristics"]["productName"]
        )
        self.current = current.with_updates(characteristics=characteristics)
        return self.current

    def read_dpp_version_by_id_and_date(self, dpp_id: str, _at: datetime) -> object:
        self._read(dpp_id)
        self.history_reads += 1
        return self.original if self.history_reads == 1 else self.current

    def read_data_element(self, dpp_id: str, selector: str) -> str:
        assert selector == "$.characteristics.productName"
        return self._read(dpp_id).productName

    def update_data_element(self, dpp_id: str, selector: str, value: str) -> str:
        assert selector == "$.characteristics.productName"
        current = self._read(dpp_id)
        self.current = current.with_updates(
            characteristics=current.characteristics.with_updates(productName=value)
        )
        return value

    def delete_dpp_by_id(self, dpp_id: str) -> SimpleNamespace:
        self._read(dpp_id)
        self.current = None
        return SimpleNamespace()

    def close(self) -> None:
        pass


class _StatefulRegistry:
    def __init__(self, repository: _StatefulRepository, *, ready: object = True) -> None:
        self.repository = repository
        self.ready = ready
        self.registration_calls = 0

    def health_check(self) -> object:
        return self.ready

    def post_new_dpp_to_registry(self, request: object) -> SimpleNamespace:
        self.registration_calls += 1
        assert self.repository.current is not None
        return SimpleNamespace(registrationId=f"registration-{request.digitalProductPassportId}")

    def close(self) -> None:
        pass


def _config() -> DemoConfig:
    return DemoConfig(
        repo_base_url="http://localhost:18080",
        registry_base_url="http://localhost:18081",
        repo_image="example/repository@sha256:repo",
        registry_image="example/registry@sha256:registry",
        env_file=Path(__file__),
        startup_timeout_seconds=2.0,
        legacy=False,
    )


def test_integration_journey_has_stable_connected_steps() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    report = run_integration_scenarios(identity, config=None, repository=None, registry=None)

    assert tuple(step.step_id for step in report.steps) == tuple(
        f"INT-{index:02d}" for index in range(1, 15)
    )
    assert all(
        step.purpose and step.input and step.operation and step.explanation for step in report.steps
    )
    assert all(step.why_it_matters for step in report.steps)
    assert all(step.status == "BLOCKED" for step in report.steps)
    assert all(step.service["name"] == "not contacted" for step in report.steps)
    assert all(step.response == {"result": "not attempted"} for step in report.steps)
    assert all("blocked_by" in step.persistence_proof for step in report.steps)


def test_integration_journey_runs_all_public_operations_and_cleans_repository() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repository = _StatefulRepository()
    report = run_integration_scenarios(
        identity,
        _config(),
        repository=repository,
        registry=_StatefulRegistry(repository),
    )

    assert tuple(step.step_id for step in report.steps) == tuple(
        f"INT-{index:02d}" for index in range(1, 15)
    )
    assert [step.status for step in report.steps] == ["PASS"] * 12 + [
        "EXPECTED_ERROR",
        "PASS",
    ]
    assert report.steps[8].response["historical_productName"] == "CIR4FUN Demo Chair"
    assert (
        report.steps[8].response["updated_historical_productName"]
        == report.steps[8].response["current_productName"]
    )
    assert report.steps[8].response["current_productName"] != "CIR4FUN Demo Chair"
    assert "created_at_utc" in report.steps[8].input
    assert "updated_at_utc" in report.steps[8].input
    assert "current_lookup_at_utc" in report.steps[8].input
    assert report.steps[10].persistence_proof["read_back_value"].endswith("fine")
    assert report.steps[6].response["dpp_ids"] == [str(identity.dpp_id)]
    assert report.steps[6].persistence_proof["includes_created_dpp"] is True
    assert report.steps[4].persistence_proof["read_back_dpp_id_matches_created"] is True
    assert report.steps[5].persistence_proof["resolved_dpp_id_matches_created"] is True
    assert report.steps[8].persistence_proof["created_historical_differs_from_current"] is True
    assert report.steps[8].persistence_proof["updated_historical_matches_current"] is True
    assert report.steps[9].persistence_proof["read_value_matches_full_patch"] is True
    assert (
        report.steps[7].persistence_proof["read_back_productName"]
        == report.steps[7].response["returned_productName"]
    )
    assert report.steps[9].response["value"] == report.steps[7].response["returned_productName"]
    assert (
        report.steps[10].persistence_proof["full_dpp_value"]
        == report.steps[10].persistence_proof["read_back_value"]
    )
    assert isinstance(report.context, IntegrationRunContext)
    assert report.context.run_id == identity.run_id
    assert report.context.dpp_id == identity.dpp_id
    assert report.context.product_id == identity.product_id
    assert report.context.initial_dpp.productName == "CIR4FUN Demo Chair"
    assert report.context.updated_dpp is not None
    assert report.context.updated_dpp.productName.endswith("fine")
    assert report.context.repository_created is True
    assert report.context.registration_id.startswith("registration-")
    assert report.context.repository_cleanup == "deleted"
    assert repository.current is None


def test_integration_stops_when_public_health_check_returns_false() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repository = _StatefulRepository(ready=False)
    report = run_integration_scenarios(
        identity,
        _config(),
        repository=repository,
        registry=_StatefulRegistry(_StatefulRepository()),
    )

    assert report.steps[0].status == "FAIL"
    assert "health_check returned False" in report.steps[0].response["error"]
    assert all(step.status == "BLOCKED" for step in report.steps[1:])
    assert repository.create_calls == 0
    assert integration_payload(report)["cleanup"]["repository"] == "not_created"


def test_integration_stops_when_registry_health_check_returns_false() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repository = _StatefulRepository()
    registry = _StatefulRegistry(repository, ready=False)

    report = run_integration_scenarios(
        identity, _config(), repository=repository, registry=registry
    )

    assert report.steps[0].status == "PASS"
    assert report.steps[1].status == "FAIL"
    assert "health_check returned False" in report.steps[1].response["error"]
    assert all(step.status == "BLOCKED" for step in report.steps[2:])
    assert repository.create_calls == 0
    assert registry.registration_calls == 0


def test_integration_blocks_after_timeout_connection_refusal_or_malformed_health() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))

    class _RaisingRepository(_StatefulRepository):
        def __init__(self, error: Exception) -> None:
            super().__init__()
            self.error = error

        def health_check(self) -> object:
            raise self.error

    for error, label in (
        (TimeoutError("health request timed out"), "TimeoutError"),
        (ConnectionRefusedError("connection refused"), "ConnectionRefusedError"),
    ):
        repository = _RaisingRepository(error)
        report = run_integration_scenarios(
            identity, _config(), repository=repository, registry=_StatefulRegistry(repository)
        )
        assert report.steps[0].status == "FAIL"
        assert label in report.steps[0].response["error"]
        assert all(step.status == "BLOCKED" for step in report.steps[1:])
        assert repository.create_calls == 0

    malformed = _StatefulRepository(ready="UP")
    report = run_integration_scenarios(
        identity, _config(), repository=malformed, registry=_StatefulRegistry(malformed)
    )
    assert report.steps[0].status == "FAIL"
    assert "must return True" in report.steps[0].response["error"]
    assert malformed.create_calls == 0


def test_integration_blocks_when_registry_readiness_is_not_a_true_response() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))

    class _RaisingRegistry(_StatefulRegistry):
        def __init__(self, repository: _StatefulRepository, error: Exception) -> None:
            super().__init__(repository)
            self.error = error

        def health_check(self) -> object:
            raise self.error

    for error, label in (
        (TimeoutError("registry health request timed out"), "TimeoutError"),
        (ConnectionRefusedError("registry connection refused"), "ConnectionRefusedError"),
    ):
        repository = _StatefulRepository()
        report = run_integration_scenarios(
            identity, _config(), repository=repository, registry=_RaisingRegistry(repository, error)
        )
        assert [step.status for step in report.steps[:2]] == ["PASS", "FAIL"]
        assert label in report.steps[1].response["error"]
        assert all(step.status == "BLOCKED" for step in report.steps[2:])
        assert repository.create_calls == 0

    repository = _StatefulRepository()
    malformed = _StatefulRegistry(repository, ready={"status": "UP"})
    report = run_integration_scenarios(
        identity, _config(), repository=repository, registry=malformed
    )
    assert report.steps[1].status == "FAIL"
    assert "must return True" in report.steps[1].response["error"]
    assert repository.create_calls == 0


def test_integration_history_does_not_claim_distinct_versions_without_evidence() -> None:
    class _NoHistoryRepository(_StatefulRepository):
        def read_dpp_version_by_id_and_date(self, dpp_id: str, _at: datetime) -> object:
            return self._read(dpp_id)

    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repository = _NoHistoryRepository()
    report = run_integration_scenarios(
        identity,
        _config(),
        repository=repository,
        registry=_StatefulRegistry(repository),
    )

    assert report.steps[8].status == "FAIL"
    assert (
        "historical lookup did not return the created version" in report.steps[8].response["error"]
    )


def test_integration_output_identifies_images_stages_and_cleanup() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repository = _StatefulRepository()
    report = run_integration_scenarios(
        identity,
        _config(),
        repository=repository,
        registry=_StatefulRegistry(repository),
    )

    payload = integration_payload(report)
    text = render_integration_text(report)

    assert payload["services"]["repository"]["configured_image"].endswith("sha256:repo")
    assert payload["services"]["registry"]["configured_image"].endswith("sha256:registry")
    assert "Environment and readiness" in text
    assert text.count("Repository creation and reads") == 1
    assert text.count("Updates and history\n-------------------") == 1
    local_section = text.split("[INT-03]", maxsplit=1)[1].split("[INT-04]", maxsplit=1)[0]
    assert "Service interaction" in local_section
    assert "No external service call" in local_section
    assert "Cleanup report:" in text
    assert "repository=deleted; post_delete=HTTP 404" in text
    assert (
        "registry=not supported by public SDK; state=registered_retained_no_public_cleanup" in text
    )
    assert payload["cleanup"] == {
        "repository": "deleted",
        "public_sdk_deleted": [f"repository_dpp:{identity.dpp_id}"],
        "post_delete_result": "HTTP 404",
        "registry": "not_supported_public_api",
        "registry_state": "registered_retained_no_public_cleanup",
        "docker_project_cleanup": "separate operator responsibility",
        "warnings": [],
    }


def test_integration_reports_failed_repository_cleanup_without_claiming_delete() -> None:
    class _DeleteFailingRepository(_StatefulRepository):
        def delete_dpp_by_id(self, dpp_id: str) -> SimpleNamespace:
            self._read(dpp_id)
            raise DppHttpClientError("delete failed", 503, "{}")

    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repository = _DeleteFailingRepository()
    report = run_integration_scenarios(
        identity,
        _config(),
        repository=repository,
        registry=_StatefulRegistry(repository),
    )

    payload = integration_payload(report)
    assert report.context.repository_cleanup == "delete_failed"
    assert report.context.post_delete_result == "not_attempted"
    assert payload["cleanup"]["public_sdk_deleted"] == []
    assert payload["cleanup"]["repository"] == "delete_failed"
    assert payload["cleanup"]["warnings"] == [
        "repository cleanup failed: DppHttpClientError: delete failed"
    ]


def test_integration_payload_distinguishes_runtime_identity_from_configured_reference() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repository = _StatefulRepository()
    image_identity = RuntimeImageIdentity(
        repo_runtime_digest="sha256:" + "c" * 64,
        registry_runtime_digest="sha256:" + "d" * 64,
    )

    report = run_integration_scenarios(
        identity,
        _config(),
        repository=repository,
        registry=_StatefulRegistry(repository),
        image_identity=image_identity,
    )

    payload = integration_payload(report)
    assert payload["services"]["repository"] == {
        "endpoint": "http://localhost:18080",
        "configured_image": "example/repository@sha256:repo",
        "runtime_digest": "sha256:" + "c" * 64,
    }
    assert payload["services"]["registry"]["runtime_digest"] == "sha256:" + "d" * 64


def test_integration_report_has_complete_bounded_teaching_evidence_in_text_and_json() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repository = _StatefulRepository()
    report = run_integration_scenarios(
        identity,
        _config(),
        repository=repository,
        registry=_StatefulRegistry(repository),
    )

    payload = integration_payload(report)
    rendered = render_integration_text(report)
    expected_fields = {
        "step_id",
        "stage",
        "title",
        "status",
        "evidence_class",
        "purpose",
        "input",
        "operation",
        "service",
        "response",
        "persistence_proof",
        "explanation",
        "why_it_matters",
        "cleanup_effect",
        "duration_seconds",
    }
    assert all(set(step) == expected_fields for step in payload["steps"])
    assert {step["status"] for step in payload["steps"]} == {"PASS", "EXPECTED_ERROR"}
    assert all(step["input"] and step["operation"] and step["service"] for step in payload["steps"])
    assert all("interaction" in step["service"] for step in payload["steps"])
    assert all(step["response"] and step["persistence_proof"] for step in payload["steps"])
    assert all(step["explanation"] and step["why_it_matters"] for step in payload["steps"])
    assert set(payload["summary"]) == {
        "total",
        "passed",
        "expected_error",
        "blocked",
        "skipped",
        "fail",
        "steps_completed",
        "expected_errors_demonstrated",
        "blocked_steps",
        "skipped_steps",
        "unexpected_failures",
    }
    assert payload["strict_verification"] == {"status": "NOT_RUN", "next_command": "verify"}
    json.dumps(payload, allow_nan=False, sort_keys=True)
    assert "0x" not in json.dumps(payload, sort_keys=True)
    for heading in (
        "Environment and readiness",
        "Local DPP preparation",
        "Repository creation and reads",
        "Updates and history",
        "Fine-grained access",
        "Registry interaction",
        "Expected errors",
        "Cleanup",
    ):
        assert heading in rendered
    assert rendered.count("Service interaction") == 14
    assert "Strict verification: NOT_RUN (separate command)" in rendered


def test_demo_profile_executes_only_the_curated_connected_journey() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repository = _StatefulRepository()
    report = run_integration_scenarios(
        identity,
        _config(),
        repository=repository,
        registry=_StatefulRegistry(repository),
        profile="demo",
    )

    assert report.profile == "demo"
    assert [step.step_id for step in report.steps] == [
        "INT-01",
        "INT-02",
        "INT-03",
        "INT-04",
        "INT-05",
        "INT-08",
        "INT-10",
        "INT-12",
        "INT-13",
        "INT-14",
    ]
    assert integration_payload(report)["verdict"] == "LIVE_DEMONSTRATION_PASSED"
