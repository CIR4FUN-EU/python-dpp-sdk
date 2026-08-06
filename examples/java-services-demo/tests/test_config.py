from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from dpp_java_services_demo.config import DemoConfig, load_config

PINNED_REPO = (
    "ghcr.io/cir4fun-eu/dpp-repo-api:"
    "sha-4d3d280227b8349f4e6fa7af732803976615eef6"
    "@sha256:bf36c904a7af28bdf8c08c774007b0c224137b31bcbe92e70647f1386bd5a04a"
)
PINNED_REGISTRY = (
    "ghcr.io/cir4fun-eu/dpp-registry-api:"
    "sha-4d3d280227b8349f4e6fa7af732803976615eef6"
    "@sha256:3d25555e08c05f3462e45e8bc3f11b1bddd8d01541d7dfabd3240b8c03ca9560"
)
_CONFIG_ENVIRONMENT_KEYS = (
    "DPP_REPO_IMAGE",
    "DPP_REGISTRY_IMAGE",
    "DPP_REPO_BASE_URL",
    "DPP_REGISTRY_BASE_URL",
    "DPP_REPO_PORT",
    "DPP_REGISTRY_PORT",
    "DPP_STARTUP_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def isolated_configuration_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make profile/default assertions independent of the caller's shell."""
    for key in _CONFIG_ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)


def _write_env(path: Path, *, repo_image: str = PINNED_REPO) -> None:
    path.write_text(
        "\n".join(
            (
                f"DPP_REPO_IMAGE={repo_image}",
                f"DPP_REGISTRY_IMAGE={PINNED_REGISTRY}",
                "DPP_REPO_BASE_URL=http://localhost:8080",
                "DPP_REGISTRY_BASE_URL=http://localhost:8081",
                "DPP_STARTUP_TIMEOUT_SECONDS=90",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def test_load_config_reads_explicit_profile(tmp_path: Path) -> None:
    env_file = tmp_path / "pinned.env"
    _write_env(env_file)

    config = load_config(env_file)

    assert config == DemoConfig(
        repo_base_url="http://localhost:8080",
        registry_base_url="http://localhost:8081",
        repo_image=PINNED_REPO,
        registry_image=PINNED_REGISTRY,
        env_file=env_file.resolve(),
        startup_timeout_seconds=90.0,
        legacy=False,
    )


def test_environment_overrides_file_without_mutating_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / "pinned.env"
    _write_env(env_file)
    monkeypatch.setenv("DPP_REPO_BASE_URL", "http://127.0.0.1:18080")
    monkeypatch.setenv("DPP_REGISTRY_BASE_URL", "http://127.0.0.1:18081")
    monkeypatch.setenv("DPP_REPO_IMAGE", "example.invalid/repository:override")

    config = load_config(env_file)

    assert config.repo_base_url == "http://127.0.0.1:18080"
    assert config.registry_base_url == "http://127.0.0.1:18081"
    assert config.repo_image == "example.invalid/repository:override"
    assert "127.0.0.1" not in env_file.read_text(encoding="utf-8")


def test_removing_process_overrides_restores_profile_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / "pinned.env"
    _write_env(env_file)
    monkeypatch.setenv("DPP_REPO_BASE_URL", "http://localhost:18080")
    monkeypatch.setenv("DPP_REGISTRY_BASE_URL", "http://localhost:18081")

    overridden = load_config(env_file)
    monkeypatch.delenv("DPP_REPO_BASE_URL")
    monkeypatch.delenv("DPP_REGISTRY_BASE_URL")
    restored = load_config(env_file)

    assert (overridden.repo_base_url, overridden.registry_base_url) == (
        "http://localhost:18080",
        "http://localhost:18081",
    )
    assert (restored.repo_base_url, restored.registry_base_url) == (
        "http://localhost:8080",
        "http://localhost:8081",
    )


def test_repeated_configuration_construction_reads_current_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / "pinned.env"
    _write_env(env_file)
    monkeypatch.setenv("DPP_REPO_BASE_URL", "http://localhost:18080")

    first = load_config(env_file)
    monkeypatch.setenv("DPP_REPO_BASE_URL", "http://localhost:19090")
    second = load_config(env_file)

    assert first.repo_base_url == "http://localhost:18080"
    assert second.repo_base_url == "http://localhost:19090"


def test_import_order_does_not_capture_environment_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / "pinned.env"
    _write_env(env_file)
    config_module = importlib.import_module("dpp_java_services_demo.config")
    monkeypatch.setenv("DPP_REPO_BASE_URL", "http://localhost:18080")

    reloaded_module = importlib.reload(config_module)

    assert reloaded_module.load_config(env_file).repo_base_url == "http://localhost:18080"


def test_default_configuration_uses_local_dotenv_from_the_demo_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    _write_env(dotenv)
    (tmp_path / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.env_file == dotenv.resolve()


def test_legacy_profile_requires_explicit_flag(tmp_path: Path) -> None:
    env_file = tmp_path / "0.4.0.env"
    _write_env(env_file, repo_image="ghcr.io/cir4fun-eu/dpp-repo-api:0.4.0")

    with pytest.raises(ValueError, match="--legacy"):
        load_config(env_file)

    assert load_config(env_file, legacy=True).legacy is True


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("DPP_REPO_IMAGE=\n", "DPP_REPO_IMAGE"),
        ("DPP_STARTUP_TIMEOUT_SECONDS=zero\n", "DPP_STARTUP_TIMEOUT_SECONDS"),
    ],
)
def test_invalid_configuration_is_rejected(tmp_path: Path, line: str, message: str) -> None:
    env_file = tmp_path / "invalid.env"
    _write_env(env_file)
    contents = env_file.read_text(encoding="utf-8")
    key = line.split("=", maxsplit=1)[0]
    contents = "\n".join(item for item in contents.splitlines() if not item.startswith(f"{key}="))
    env_file.write_text(f"{contents}\n{line}", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_config(env_file)
