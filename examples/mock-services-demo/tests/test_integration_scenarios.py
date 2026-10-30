from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from dpp_sdk.clients import (
    CreateDppResponse,
    DppApiClientError,
    DppApiResponse,
    DppStatusCode,
    RegisterDppResponse,
)

from dpp_mock_services_demo.config import DemoConfig
from dpp_mock_services_demo.fixtures import DemoIdentity
from dpp_mock_services_demo.integration_scenarios import (
    IntegrationRunContext,
    integration_payload,
    render_integration_text,
    run_integration_scenarios,
)
from dpp_mock_services_demo.reporting import ScenarioResult, ScenarioStatus


def _config() -> DemoConfig:
    return DemoConfig(
        repo_base_url="http://localhost:18080",
        registry_base_url="http://localhost:18081",
        repo_image="example/repository:current",
        registry_image="example/registry:current",
        env_file=Path(__file__),
        startup_timeout_seconds=0.1,
        legacy=False,
    )


class _Repository:
    def __init__(self, *, fail_delete: bool = False) -> None:
        self.payload = None
        self.fail_delete = fail_delete
        self.closed = False

    def create_dpp(self, dpp, _representation=None):
        self.payload = dpp
        return CreateDppResponse(digital_product_passport_id=dpp["digitalProductPassportId"])

    def read_dpp_by_id(self, dpp_id, _representation=None):
        if self.payload is None or self.payload["digitalProductPassportId"] != dpp_id:
            raise DppApiClientError(
                "missing", 404, DppStatusCode.ClientErrorResourceNotFound, None, "{}"
            )
        return DppApiResponse(status_code=DppStatusCode.Success, payload=self.payload)

    def delete_dpp_by_id(self, _dpp_id):
        if self.fail_delete:
            raise RuntimeError("delete unavailable")
        self.payload = None

    def close(self):
        self.closed = True


class _Registry:
    def __init__(self) -> None:
        self.request = None
        self.closed = False

    def post_new_dpp_to_registry(self, request):
        self.request = request
        return RegisterDppResponse(registration_id="registration-1")

    def close(self):
        self.closed = True


def _ready(**kwargs):
    return ScenarioResult(
        kwargs["scenario_id"],
        kwargs["name"],
        "LIVE_MOCK_IMAGE",
        ScenarioStatus.PASSED,
        0.0,
        "ready",
        f"GET {kwargs['endpoint']}/health returned HTTP 200",
    )


def test_unconfigured_run_is_bounded_and_makes_no_service_calls() -> None:
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    report = run_integration_scenarios(identity, config=None)
    assert tuple(step.step_id for step in report.steps) == tuple(
        f"INT-{i:02d}" for i in range(1, 9)
    )
    assert all(step.status == "BLOCKED" for step in report.steps)
    assert all(step.service["name"] == "not contacted" for step in report.steps)


def test_connected_flow_uses_json_clients_and_cleans_created_dpp(monkeypatch) -> None:
    import dpp_mock_services_demo.integration_scenarios as module

    monkeypatch.setattr(module, "wait_for_health", _ready)
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repository = _Repository()
    registry = _Registry()
    report = run_integration_scenarios(identity, _config(), repository, registry)

    assert tuple(step.step_id for step in report.steps) == tuple(
        f"INT-{i:02d}" for i in range(1, 9)
    )
    assert [step.status for step in report.steps] == [
        "PASS",
        "PASS",
        "PASS",
        "PASS",
        "PASS",
        "PASS",
        "EXPECTED_ERROR",
        "PASS",
    ]
    assert report.context.repository_created is True
    assert report.context.repository_cleanup == "deleted"
    assert report.context.registration_id == "registration-1"
    assert repository.payload is None
    assert registry.request.model_dump(by_alias=True)["digitalProductPassportId"] == str(
        identity.dpp_id
    )
    assert not repository.closed and not registry.closed


def test_cleanup_failure_is_reported_without_claiming_success(monkeypatch) -> None:
    import dpp_mock_services_demo.integration_scenarios as module

    monkeypatch.setattr(module, "wait_for_health", _ready)
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    report = run_integration_scenarios(
        identity, _config(), _Repository(fail_delete=True), _Registry()
    )
    assert report.context.repository_cleanup == "delete_failed"
    assert report.cleanup_warnings == (
        "repository cleanup failed: RuntimeError: delete unavailable",
    )
    assert integration_payload(report)["cleanup"]["public_sdk_deleted"] == []


def test_report_keeps_machine_readable_json_and_interaction_evidence(monkeypatch) -> None:
    import dpp_mock_services_demo.integration_scenarios as module

    monkeypatch.setattr(module, "wait_for_health", _ready)
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    report = run_integration_scenarios(identity, _config(), _Repository(), _Registry())
    payload = integration_payload(report)
    json.dumps(payload, allow_nan=False)
    assert len(payload["steps"]) == 8
    assert all("interaction" in step["service"] for step in payload["steps"])
    assert "DppRepoClient.create_dpp(json_value, FULL)" in render_integration_text(report)
    assert "registry deregistration is not a supported operation" in render_integration_text(report)
    assert isinstance(report.context, IntegrationRunContext)


def test_readiness_failure_blocks_requests_and_cleanup(monkeypatch) -> None:
    import dpp_mock_services_demo.integration_scenarios as module

    def failed(**kwargs):
        if kwargs["scenario_id"] == "INT-01":
            return ScenarioResult(
                "INT-01",
                "Repository",
                "LIVE_MOCK_IMAGE",
                ScenarioStatus.FAILED,
                0.0,
                "failed",
                "HTTP 503",
            )
        return _ready(**kwargs)

    monkeypatch.setattr(module, "wait_for_health", failed)
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    repository = _Repository()
    report = run_integration_scenarios(identity, _config(), repository, _Registry())
    assert report.steps[0].status == "FAIL"
    assert repository.payload is None
    assert all(step.status != "PASS" for step in report.steps[1:])
