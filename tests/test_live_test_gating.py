"""Subprocess regressions for the opt-in Mock-service test boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SDK_ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = SDK_ROOT / "examples" / "mock-services-demo"
_SERVICE_ENVIRONMENT_KEYS = (
    "DPP_REPO_BASE_URL",
    "DPP_REGISTRY_BASE_URL",
    "DPP_REPO_PORT",
    "DPP_REGISTRY_PORT",
)


class _RecordingServer(ThreadingHTTPServer):
    records: list[tuple[str, str]]
    dpp: dict[str, Any]
    dpp_id: str


class _RecordingHandler(BaseHTTPRequestHandler):
    server: _RecordingServer

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _send_json(self, payload: Any, status: int = 200) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _record(self) -> tuple[str, str]:
        parsed = urlsplit(self.path)
        item = (self.command, parsed.path)
        self.server.records.append(item)
        return item

    def do_GET(self) -> None:  # noqa: N802
        _, path = self._record()
        if path == "/health":
            self._send_json({"status": "UP"})
        elif "/elements/" in path:
            self._send_json({"statusCode": "Success", "payload": "ErgoChair Pro"})
        elif path.startswith("/v1/dppsByProductId/") or path.startswith("/v1/dpps/"):
            self._send_json({"statusCode": "Success", "payload": self.server.dpp})
        else:
            self._send_json({"statusCode": "Success", "payload": {}})

    def do_POST(self) -> None:  # noqa: N802
        _, path = self._record()
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if path == "/v1/dpps":
            self.server.dpp = json.loads(raw)
            self.server.dpp_id = self.server.dpp["passportMetadata"]["uniqueProductIdentifier"]
            self._send_json(
                {"statusCode": "SuccessCreated", "payload": {"dppId": self.server.dpp_id}}
            )
        elif path == "/v1/dppsByProductIds":
            self._send_json(
                {"statusCode": "Success", "payload": {"dppIdentifiers": [self.server.dpp_id]}}
            )
        else:
            self._send_json(
                {"statusCode": "SuccessCreated", "payload": {"registrationId": "registration-1"}}
            )

    def do_PATCH(self) -> None:  # noqa: N802
        self._record()
        length = int(self.headers.get("Content-Length", "0"))
        self._send_json({"statusCode": "Success", "payload": json.loads(self.rfile.read(length))})

    def do_DELETE(self) -> None:  # noqa: N802
        self._record()
        self._send_json({"statusCode": "SuccessNoContent", "payload": None})


@contextmanager
def _recording_service() -> Iterator[_RecordingServer]:
    service = _RecordingServer(("127.0.0.1", 0), _RecordingHandler)
    service.records = []
    service.dpp = {}
    service.dpp_id = "11111111-1111-1111-1111-111111111111"
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        yield service
    finally:
        service.shutdown()
        thread.join()
        service.server_close()


def _base_url(service: _RecordingServer) -> str:
    host, port = service.server_address[:2]
    return f"http://{host}:{port}"


def _environment(**overrides: str) -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if key not in _SERVICE_ENVIRONMENT_KEYS
    }
    environment.update(overrides)
    return environment


def _pytest(
    command: list[str], *, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *command],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_root_live_tests_do_not_contact_healthy_configured_services_without_opt_in() -> None:
    """Environment-configured healthy services must not bypass ``--run-mock-services``."""
    with _recording_service() as repository, _recording_service() as registry:
        result = _pytest(
            ["tests/test_integration_live.py"],
            cwd=SDK_ROOT,
            env=_environment(
                DPP_REPO_BASE_URL=_base_url(repository),
                DPP_REGISTRY_BASE_URL=_base_url(registry),
            ),
        )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "requires --run-mock-services" in result.stdout
    assert repository.records == []
    assert registry.records == []


def test_default_urls_cannot_enable_root_live_tests(tmp_path: Path) -> None:
    """The default localhost URLs must not be probed when the opt-in flag is absent."""
    record_path = tmp_path / "requests.log"
    sitecustomize = tmp_path / "sitecustomize.py"
    sitecustomize.write_text(
        """
import os
from pathlib import Path
import httpx

_original_request = httpx.Client.request
def _recording_request(self, method, url, *args, **kwargs):
    Path(os.environ['DPP_GATING_RECORD']).open('a', encoding='utf-8').write(f'{method} {url}\\n')
    if str(url).endswith('/health'):
        return httpx.Response(200, json={'status': 'UP'}, request=httpx.Request(method, url))
    return httpx.Response(
        200,
        json={'statusCode': 'Success', 'payload': {}},
        request=httpx.Request(method, url),
    )
httpx.Client.request = _recording_request
""".lstrip(),
        encoding="utf-8",
    )
    result = _pytest(
        ["tests/test_integration_live.py"],
        cwd=SDK_ROOT,
        env=_environment(
            PYTHONPATH=str(tmp_path),
            DPP_GATING_RECORD=str(record_path),
        ),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not record_path.exists() or record_path.read_text(encoding="utf-8") == ""


def test_explicit_opt_in_runs_root_live_tests_against_configured_alternate_ports() -> None:
    with _recording_service() as repository, _recording_service() as registry:
        result = _pytest(
            ["--run-mock-services", "tests/test_integration_live.py"],
            cwd=SDK_ROOT,
            env=_environment(
                DPP_REPO_BASE_URL=_base_url(repository),
                DPP_REGISTRY_BASE_URL=_base_url(registry),
            ),
        )

    assert result.returncode == 0, result.stdout + result.stderr
    assert ("GET", "/health") in repository.records
    assert ("GET", "/health") in registry.records
    assert ("POST", "/v1/dpps") in repository.records
    assert ("POST", "/v1/registerDPP") in registry.records


def test_live_marker_remains_discoverable_and_controlled_client_tests_need_no_services() -> None:
    integration = _pytest(
        ["--collect-only", "-m", "integration", "tests/test_integration_live.py"],
        cwd=SDK_ROOT,
        env=_environment(),
    )
    controlled_clients = _pytest(["tests/test_clients.py"], cwd=SDK_ROOT, env=_environment())

    assert integration.returncode == 0, integration.stdout + integration.stderr
    assert "test_repo_lifecycle_against_external_endpoint" in integration.stdout
    assert "test_registry_register_against_external_endpoint" in integration.stdout
    assert controlled_clients.returncode == 0, controlled_clients.stdout + controlled_clients.stderr


def test_nested_demo_live_tests_remain_opt_in_without_services() -> None:
    result = _pytest(
        ["tests/test_mock_services_integration.py"],
        cwd=DEMO_ROOT,
        env=_environment(),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "requires --run-mock-services" in result.stdout
