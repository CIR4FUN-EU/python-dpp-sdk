"""Configuration for the repository-only Java-services consumer demo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_REQUIRED_KEYS = (
    "DPP_REPO_IMAGE",
    "DPP_REGISTRY_IMAGE",
    "DPP_REPO_BASE_URL",
    "DPP_REGISTRY_BASE_URL",
)
_TIMEOUT_KEY = "DPP_STARTUP_TIMEOUT_SECONDS"
_DEFAULT_TIMEOUT = 120.0


@dataclass(frozen=True)
class DemoConfig:
    """Resolved, immutable demo configuration."""

    repo_base_url: str
    registry_base_url: str
    repo_image: str
    registry_image: str
    env_file: Path
    startup_timeout_seconds: float
    legacy: bool


def _project_root() -> Path:
    working_directory = Path.cwd().resolve()
    if (working_directory / "compose.yaml").is_file() and (
        working_directory / "env" / "pinned.env"
    ).is_file():
        return working_directory
    return Path(__file__).resolve().parents[2]


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ValueError(f"Environment profile does not exist: {path}")
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            raise ValueError(f"Invalid environment entry at {path}:{line_number}")
        values[key.strip()] = value.strip()
    return values


def _required_value(values: dict[str, str], key: str) -> str:
    value = os.environ.get(key, values.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} must be configured")
    return value


def _timeout(values: dict[str, str]) -> float:
    raw_value = os.environ.get(_TIMEOUT_KEY, values.get(_TIMEOUT_KEY, str(_DEFAULT_TIMEOUT)))
    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{_TIMEOUT_KEY} must be a positive number") from exc
    if timeout <= 0:
        raise ValueError(f"{_TIMEOUT_KEY} must be a positive number")
    return timeout


def _is_legacy_profile(path: Path, repo_image: str, registry_image: str) -> bool:
    return path.name == "0.4.0.env" or (":0.4.0" in repo_image and ":0.4.0" in registry_image)


def load_config(env_file: Path | None = None, *, legacy: bool = False) -> DemoConfig:
    """Load one profile, with process environment values taking precedence."""

    path = (env_file or (_project_root() / "env" / "pinned.env")).resolve()
    values = _parse_env_file(path)
    resolved = {key: _required_value(values, key) for key in _REQUIRED_KEYS}
    is_legacy = _is_legacy_profile(
        path,
        resolved["DPP_REPO_IMAGE"],
        resolved["DPP_REGISTRY_IMAGE"],
    )
    if is_legacy and not legacy:
        raise ValueError("The 0.4.0 profile requires the explicit --legacy flag")
    if legacy and not is_legacy:
        raise ValueError("--legacy may only be used with the 0.4.0 profile")
    return DemoConfig(
        repo_base_url=resolved["DPP_REPO_BASE_URL"],
        registry_base_url=resolved["DPP_REGISTRY_BASE_URL"],
        repo_image=resolved["DPP_REPO_IMAGE"],
        registry_image=resolved["DPP_REGISTRY_IMAGE"],
        env_file=path,
        startup_timeout_seconds=_timeout(values),
        legacy=is_legacy,
    )
