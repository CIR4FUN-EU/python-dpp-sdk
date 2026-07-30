"""Default endpoint configuration for the DPP mock services.

The Java reference SDK keeps the client constructors URL-required and resolves the
mock-service defaults in the demo runner (``HttpServiceDemoRunner`` /
``DemoServicePreflight``). We mirror that split here: the clients still require a
``base_url``, while these helpers provide the local mock defaults used by the
``for_local_mock`` factories.

Defaults match ``dpp-sdk-demo``: the mock repo on ``http://localhost:8080`` and the
mock registry on ``http://localhost:8081``. Both are env-overridable — a full-URL
override (``DPP_REPO_BASE_URL`` / ``DPP_REGISTRY_BASE_URL``) takes precedence, otherwise
the port is taken from ``DPP_REPO_PORT`` / ``DPP_REGISTRY_PORT`` (matching the Java
``defaultRepoLocalUrl()`` / ``defaultRegistryLocalUrl()``).
"""

from __future__ import annotations

import os

DEFAULT_REPO_PORT = 8080
DEFAULT_REGISTRY_PORT = 8081

DEFAULT_REPO_BASE_URL = f"http://localhost:{DEFAULT_REPO_PORT}"
DEFAULT_REGISTRY_BASE_URL = f"http://localhost:{DEFAULT_REGISTRY_PORT}"


def _local_base_url(url_env: str, port_env: str, default_port: int) -> str:
    override = os.environ.get(url_env)
    if override and override.strip():
        return override.strip()
    port = os.environ.get(port_env, str(default_port)).strip() or str(default_port)
    return f"http://localhost:{port}"


def local_repo_base_url() -> str:
    """Resolve the local mock-repo base URL, honoring env overrides at call time."""
    return _local_base_url("DPP_REPO_BASE_URL", "DPP_REPO_PORT", DEFAULT_REPO_PORT)


def local_registry_base_url() -> str:
    """Resolve the local mock-registry base URL, honoring env overrides at call time."""
    return _local_base_url("DPP_REGISTRY_BASE_URL", "DPP_REGISTRY_PORT", DEFAULT_REGISTRY_PORT)
