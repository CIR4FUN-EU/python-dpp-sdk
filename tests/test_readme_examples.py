"""No-network examples kept in lockstep with the README's public guidance."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

import httpx

from dpp_sdk import Dpp4Fun, DppHeader, Granularity, from_json, to_json, validate_dpp4fun
from dpp_sdk.clients import (
    RegisterDppRequest,
    RegisterDppResponse,
)
from dpp_sdk.dpp4fun import Nameplate

README = Path(__file__).parents[1] / "README.md"
LIFECYCLE_EXAMPLE = README.parent / "examples" / "consumer_lifecycle.py"
MODULE_READMES = {
    "core": README.parent / "src" / "dpp_sdk" / "core" / "README.md",
    "dpp4fun": README.parent / "src" / "dpp_sdk" / "dpp4fun" / "README.md",
    "clients": README.parent / "src" / "dpp_sdk" / "clients" / "README.md",
}


def test_readme_documents_current_model_and_client_contracts() -> None:
    readme = README.read_text(encoding="utf-8")
    normalized_readme = re.sub(r"\s+", " ", readme)
    for required_text in (
        "DppRepresentation",
        "## Standards and limitations",
        "EN 18222:2026",
        "not a claim of full conformance",
        "JSON Merge Patch (RFC 7396)",
        "JSONPath (RFC 9535)",
        "no lifecycle-event history",
        "pip install dpp-sdk",
    ):
        assert required_text in normalized_readme
    contributing = (README.parent / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert 'pip install -e ".[dev,release]"' in contributing
    assert "dpp-sdk==0.4.0" not in readme
    assert "dpp-sdk~=0.4.0" not in readme
    model = (README.parent / "docs/model-guide.md").read_text(encoding="utf-8")
    clients = (README.parent / "docs/clients-guide.md").read_text(encoding="utf-8")
    assert "ordered" in model and "immutable" in model
    for detail in ("POST /v1/registerDPP", "DppMappingClientError", "caller owned"):
        assert detail in clients
    assert 'dpp_api_endpoint=f"{REPO_URL}/v1/dpps"' in readme
    assert "dpp_api_endpoint=local_repo_base_url()" not in readme
    lifecycle = LIFECYCLE_EXAMPLE.read_text(encoding="utf-8")
    assert "with_updates" in lifecycle
    assert "read_dpp_version_by_id_and_date" in lifecycle


def test_readme_model_example_uses_immutable_updates_and_canonical_json() -> None:
    header = DppHeader(
        digital_product_passport_id="urn:example:dpp:1",
        unique_product_identifier="urn:example:product:1",
        granularity=Granularity.MODEL,
        dpp_schema_version="1.0",
        dpp_status="active",
        last_updated=datetime(2026, 1, 1, tzinfo=UTC),
        economic_operator_id="urn:example:operator:1",
    )
    passport = Dpp4Fun.create(header, Nameplate.create(manufacturerName="Example"))
    assert validate_dpp4fun(passport).is_valid
    nameplate = passport.typed_aspect(Nameplate)
    assert nameplate is not None
    updated = passport.with_updates(
        aspects=(nameplate.with_field("manufacturerName", "Example 2"),)
    )
    assert validate_dpp4fun(updated).is_valid
    assert updated is not passport
    assert json.loads(to_json(updated))["elements"][0]["elements"][0]["value"] == "Example 2"
    assert from_json(to_json(updated)) == updated


def test_readme_registry_example_emits_canonical_names_without_network() -> None:
    request = RegisterDppRequest(
        unique_product_identifier="GTIN-0001",
        digital_product_passport_id="DPP-1",
        unique_economic_operator_identifier="operator-123",
        dpp_api_endpoint="https://repo.example.com",
    )
    response = RegisterDppResponse(registration_id="REG-1")

    assert request.model_dump(by_alias=True) == {
        "uniqueProductIdentifier": "GTIN-0001",
        "digitalProductPassportId": "DPP-1",
        "uniqueEconomicOperatorIdentifier": "operator-123",
        "dppApiEndpoint": "https://repo.example.com",
    }
    assert response.registration_id == "REG-1"


def test_module_readmes_point_to_the_guides_instead_of_repeating_them() -> None:
    required_text = {
        "core": ("# DPP SDK core module", "DppValidator", "../../../docs/model-guide.md"),
        "dpp4fun": (
            "# DPP SDK DPP4Fun module",
            "Dpp4FunJsonCodec",
            "../../../docs/dpp4fun-fields.md",
        ),
        "clients": ("# DPP SDK clients module", "DppRepoClient", "../../../docs/clients-guide.md"),
    }

    for module, expected in required_text.items():
        content = MODULE_READMES[module].read_text(encoding="utf-8")
        for text in expected:
            assert text in content
        assert "[Contributing](../../../CONTRIBUTING.md)" in content
        assert "```" not in content
        assert "![" not in content  # images break once the README ships outside the repository


def test_readme_workflow_runs_with_mocked_repository_and_registry(monkeypatch, capsys) -> None:
    blocks = re.findall(r"(?ms)^```python\s*\n(.*?)^```\s*$", README.read_text(encoding="utf-8"))
    calls: list[tuple[str, str, dict[str, object]]] = []
    stored: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        calls.append((request.method, request.url.path, body))
        if request.method == "GET":
            assert request.url.params["representation"] == "full"
            return httpx.Response(200, json={"statusCode": "Success", "payload": stored})
        if request.url.path == "/v1/dpps":
            stored.update(body)
            assert request.url.params["representation"] == "full"
            return httpx.Response(
                201,
                json={
                    "statusCode": "SuccessCreated",
                    "payload": {"digitalProductPassportId": body["digitalProductPassportId"]},
                },
            )
        assert request.url.path == "/v1/registerDPP"
        return httpx.Response(
            201, json={"statusCode": "SuccessCreated", "payload": {"registrationId": "REG-1"}}
        )

    import dpp_sdk.clients._http as client_http

    monkeypatch.setattr(
        client_http, "build_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    exec(compile(blocks[0], str(README), "exec"), {})

    assert [(method, path) for method, path, _ in calls] == [
        ("POST", "/v1/dpps"),
        ("POST", "/v1/registerDPP"),
        ("GET", f"/v1/dpps/{calls[0][2]['digitalProductPassportId']}"),
    ]
    passport_id = calls[0][2]["digitalProductPassportId"]
    assert calls[1][2]["digitalProductPassportId"] == passport_id
    assert calls[1][2]["dppApiEndpoint"] == "http://localhost:8080/v1/dpps"
    output = capsys.readouterr().out
    assert f"Saved passport: {passport_id}" in output
    assert "Registered: REG-1" in output
    assert "Manufacturer: Example Furniture" in output


def test_lifecycle_example_runs_with_mocked_repository_and_registry(monkeypatch) -> None:
    source = LIFECYCLE_EXAMPLE.read_text(encoding="utf-8")
    state: dict[str, object] = {
        "initial": None,
        "stored": None,
        "created_at": None,
        "updated_at": None,
        "history_at": None,
        "calls": [],
    }

    def repository_handler(request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        calls = state["calls"]
        assert isinstance(calls, list)
        calls.append((request.method, path))
        if request.method == "POST" and path == "/v1/dpps":
            stored = json.loads(request.content)
            state["initial"] = stored
            state["stored"] = stored
            state["created_at"] = datetime.now(UTC)
            return httpx.Response(
                201,
                json={
                    "statusCode": "SuccessCreated",
                    "payload": {"digitalProductPassportId": stored["digitalProductPassportId"]},
                },
            )
        if request.method == "PATCH" and path.startswith("/v1/dpps/"):
            stored = state["stored"]
            assert isinstance(stored, dict)
            updated = {**stored, **json.loads(request.content)}
            state["stored"] = updated
            state["updated_at"] = datetime.now(UTC)
            return httpx.Response(200, json={"statusCode": "Success", "payload": updated})
        if request.method == "GET" and path.startswith("/v1/dppsByIdAndDate/"):
            at = datetime.fromisoformat(request.url.params["date"].replace("Z", "+00:00"))
            assert at.utcoffset() is not None
            state["history_at"] = at
            created_at = state["created_at"]
            updated_at = state["updated_at"]
            assert isinstance(created_at, datetime)
            if at < created_at:
                return httpx.Response(
                    404,
                    json={
                        "statusCode": "ClientErrorResourceNotFound",
                        "message": [
                            {"messageType": "Error", "text": "No DPP version at this date"}
                        ],
                    },
                )
            if isinstance(updated_at, datetime) and at >= updated_at:
                return httpx.Response(
                    200, json={"statusCode": "Success", "payload": state["stored"]}
                )
            return httpx.Response(200, json={"statusCode": "Success", "payload": state["initial"]})
        if request.method == "GET" and path.startswith("/v1/dpps/"):
            return httpx.Response(200, json={"statusCode": "Success", "payload": state["stored"]})
        if request.method == "DELETE" and path.startswith("/v1/dpps/"):
            return httpx.Response(204)
        raise AssertionError(f"unexpected request: {request.method} {path}")

    registry_calls: list[str] = []

    def registry_handler(request: httpx.Request) -> httpx.Response:
        registry_calls.append(unquote(request.url.path))
        assert request.method == "POST" and request.url.path == "/v1/registerDPP"
        assert json.loads(request.content)["dppApiEndpoint"] == "http://repository.test/v1/dpps"
        return httpx.Response(
            201, json={"statusCode": "SuccessCreated", "payload": {"registrationId": "REG-1"}}
        )

    import dpp_sdk.clients._http as client_http

    clients = iter(
        (
            httpx.Client(transport=httpx.MockTransport(repository_handler)),
            httpx.Client(transport=httpx.MockTransport(registry_handler)),
        )
    )
    monkeypatch.setattr(client_http, "build_client", lambda: next(clients))
    namespace: dict[str, object] = {}
    exec(compile(source, str(LIFECYCLE_EXAMPLE), "exec"), namespace)
    workflow = namespace["run_consumer_workflow"]
    assert callable(workflow)
    result = workflow("http://repository.test", "http://registry.test")
    assert result["updated_manufacturer"] == "Example Furniture Ltd."
    historical = result["historical_passport"].typed_aspect(Nameplate)
    assert historical is not None
    assert historical.field("manufacturerName").value == "Example Furniture"
    assert result["registration_id"] == "REG-1"
    assert result["repository_cleanup_status"].value == "SuccessNoContent"
    assert len(json.loads(result["full_json"])["elements"]) == 2
    assert json.loads(result["compressed_json"])
    assert registry_calls == ["/v1/registerDPP"]
    assert [method for method, _ in state["calls"]] == [
        "POST",
        "GET",
        "PATCH",
        "GET",
        "GET",
        "DELETE",
    ]
    created_at = state["created_at"]
    updated_at = state["updated_at"]
    history_at = state["history_at"]
    assert isinstance(created_at, datetime)
    assert isinstance(updated_at, datetime)
    assert isinstance(history_at, datetime)
    content_updated_at = result["historical_passport"].header.last_updated
    assert content_updated_at is not None
    assert content_updated_at < created_at
    assert created_at <= history_at < updated_at
    passport_id = result["passport_id"]

    def historical_response(at: datetime) -> httpx.Response:
        return repository_handler(
            httpx.Request(
                "GET",
                f"http://repository.test/v1/dppsByIdAndDate/{passport_id}",
                params={"date": at.isoformat()},
            )
        )

    assert historical_response(created_at - timedelta(microseconds=1)).status_code == 404
    assert historical_response(content_updated_at).status_code == 404
    assert historical_response(created_at).json()["payload"] == state["initial"]
    assert (
        historical_response(updated_at - timedelta(microseconds=1)).json()["payload"]
        == state["initial"]
    )
    assert historical_response(updated_at).json()["payload"] == state["stored"]
