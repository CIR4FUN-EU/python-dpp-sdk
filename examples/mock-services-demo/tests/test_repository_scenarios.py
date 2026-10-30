from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

import httpx
from dpp_sdk.clients import (
    CreateDppResponse,
    DppApiClientError,
    DppApiResponse,
    DppMappingClientError,
    DppRepresentation,
    DppStatusCode,
    ReadDppIdsResponse,
)

from dpp_mock_services_demo.config import DemoConfig
from dpp_mock_services_demo.fixtures import DemoIdentity
from dpp_mock_services_demo.reporting import ScenarioStatus
from dpp_mock_services_demo.repository_scenarios import (
    run_repository_scenarios,
    wait_for_repository,
)


class _JsonRepository:
    def __init__(self) -> None:
        self.payload = None
        self.active = False
        self.element_reads = []
        self.element_updates = []

    def create_dpp(self, value, _representation=None):
        if value is None:
            raise DppMappingClientError("null JSON")
        if self.active:
            raise DppApiClientError(
                "duplicate", 409, DppStatusCode.ClientResourceConflict, None, "{}"
            )
        self.payload = value
        self.active = True
        return CreateDppResponse(digital_product_passport_id=value["digitalProductPassportId"])

    def read_dpp_by_id(self, dpp_id, _representation=None):
        if not self.active or self.payload["digitalProductPassportId"] != dpp_id:
            raise DppApiClientError(
                "missing", 404, DppStatusCode.ClientErrorResourceNotFound, None, "{}"
            )
        return DppApiResponse(status_code=DppStatusCode.Success, payload=self.payload)

    def read_dpp_by_product_id(self, product_id, _representation=None):
        if not self.active or self.payload["uniqueProductIdentifier"] != product_id:
            raise DppApiClientError(
                "missing", 404, DppStatusCode.ClientErrorResourceNotFound, None, "{}"
            )
        return DppApiResponse(status_code=DppStatusCode.Success, payload=self.payload)

    def read_dpp_version_by_id_and_date(self, dpp_id, at: datetime, _representation=None):
        assert at.tzinfo is not None
        return self.read_dpp_by_id(dpp_id)

    def read_dpp_ids_by_product_ids(self, product_ids, limit=None, cursor=None):
        assert limit == 10 and cursor == "0"
        ids = (
            [self.payload["digitalProductPassportId"]]
            if self.active and self.payload["uniqueProductIdentifier"] in product_ids
            else []
        )
        return ReadDppIdsResponse(dpp_identifiers=ids)

    def update_dpp_by_id(self, dpp_id, patch, _representation=None):
        self.read_dpp_by_id(dpp_id)
        return DppApiResponse(status_code=DppStatusCode.Success, payload=self.payload)

    def read_data_element(self, dpp_id, path, _representation=None):
        self.read_dpp_by_id(dpp_id)
        if not path.strip():
            raise ValueError("blank element path")
        self.element_reads.append((path, _representation))
        return DppApiResponse(status_code=DppStatusCode.Success, payload="blue")

    def update_data_element(self, dpp_id, path, data, _representation=None):
        self.read_dpp_by_id(dpp_id)
        self.element_updates.append((path, data, _representation))
        return DppApiResponse(status_code=DppStatusCode.Success, payload=data)

    def delete_dpp_by_id(self, _dpp_id):
        self.active = False

    def close(self):
        pass


def _config() -> DemoConfig:
    return DemoConfig(
        repo_base_url="http://localhost:8080",
        registry_base_url="http://localhost:8081",
        repo_image="repo",
        registry_image="registry",
        env_file=Path(__file__),
        startup_timeout_seconds=2.0,
        legacy=False,
    )


def test_repository_readiness_probes_public_http_health_and_retries() -> None:
    responses = iter((503, 200))
    http = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(next(responses)))
    )
    clock_values = iter((0.0, 0.1, 0.2))
    pauses: list[float] = []
    result = wait_for_repository(
        _config(),
        client=http,
        clock=lambda: next(clock_values),
        pause=pauses.append,
        interval_seconds=0.01,
    )
    assert result.status is ScenarioStatus.PASSED
    assert pauses == [0.01]
    assert http.is_closed is False
    http.close()


def test_repository_runner_uses_json_api_operations_and_cleans_up(monkeypatch) -> None:
    import dpp_mock_services_demo.repository_scenarios as module
    from dpp_mock_services_demo.reporting import ScenarioResult

    monkeypatch.setattr(
        module,
        "wait_for_repository",
        lambda *_args, **_kwargs: ScenarioResult(
            "REP-01", "ready", "test", ScenarioStatus.PASSED, 0, "ready"
        ),
    )
    identity = DemoIdentity.from_run_id(UUID("12345678-1234-5678-9234-567812345678"))
    client = _JsonRepository()
    run = run_repository_scenarios(_config(), identity, client=client)
    assert tuple(result.scenario_id for result in run.results) == tuple(
        f"REP-{i:02d}" for i in range(1, 16)
    )
    assert [item.status for item in run.results] == [
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.PASSED,
        ScenarioStatus.EXPECTED_ERROR,
        ScenarioStatus.EXPECTED_ERROR,
        ScenarioStatus.EXPECTED_ERROR,
        ScenarioStatus.EXPECTED_ERROR,
    ]
    assert client.active is False
    read_path, read_representation = client.element_reads[0]
    update_path, update_data, update_representation = client.element_updates[0]
    assert read_path == update_path
    characteristics_index = next(
        index
        for index, element in enumerate(client.payload["elements"])
        if element["elementId"] == "characteristics"
    )
    color_index = next(
        index
        for index, element in enumerate(
            client.payload["elements"][characteristics_index]["elements"]
        )
        if element["elementId"] == "color"
    )
    assert read_path == f"$.elements[{characteristics_index}].elements[{color_index}]"
    assert read_representation is DppRepresentation.FULL
    assert update_representation is DppRepresentation.FULL
    assert update_data["objectType"] == "SingleValuedDataElement"
    assert update_data["elementId"] == "color"
    assert update_data["value"] == "green"
    assert run.cleanup_warnings == ()


def test_live_inventory_uses_full_representation_and_no_removed_codec_injection() -> None:
    from dpp_mock_services_demo.repository_scenarios import _NAMES

    assert tuple(_NAMES) == tuple(f"REP-{index:02d}" for index in range(1, 16))
    assert _NAMES["REP-04"] == "Read explicit FULL representation"
