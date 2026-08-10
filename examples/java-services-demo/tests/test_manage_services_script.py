"""Regression checks for the copyable Java-services lifecycle wrapper."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_lifecycle_script_is_project_scoped_and_guards_volume_deletion() -> None:
    script = (PROJECT_ROOT / "manage-java-services.ps1").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    assert '[ValidateSet("Start", "Status", "Logs", "Stop", "Delete")]' in script
    assert '[string]$Project = ""' in script
    assert '[string]$EnvFile = ""' in script
    assert "if (-not $EnvFile) {" in script
    assert 'Join-Path $PSScriptRoot ".env"' in script
    assert "COMPOSE_PROJECT_NAME must be configured" in script
    assert "--policy missing" in script
    assert '"$BaseUrl/health"' in script
    assert "-BaseUrl $RepoUrl" in script
    assert "-BaseUrl $RegistryUrl" in script
    assert 'status -ne "UP"' in script
    assert "-p $Project" in script
    assert "-ConfirmDelete" in script
    assert "down --volumes --remove-orphans" in script
    assert "Copy-Item .\\examples\\java-services-demo\\.env.example" in guide
    assert "project-prefixed container names" in guide
    assert "Docker Engine or Docker Desktop must be running" in guide
    assert "Optional PowerShell convenience wrapper" in guide
    assert guide.index(
        "docker compose -f $composeFile -p $project --env-file $envFile config --quiet"
    ) < guide.index("& $serviceScript -Action Start -EnvFile $envFile")
    assert "COMPOSE_PROJECT_NAME=" in example
    assert "MOCK_REPO_PORT=" in example
    assert "MOCK_REGISTRY_PORT=" in example
