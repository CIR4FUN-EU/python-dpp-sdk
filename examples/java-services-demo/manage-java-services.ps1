[CmdletBinding()]
param(
    [ValidateSet("Start", "Status", "Logs", "Stop", "Delete")]
    [string]$Action = "Start",

    [Parameter(Mandatory)]
    [string]$Project,

    [string]$EnvFile = "",

    [string]$RepoUrl = $(if ($env:DPP_REPO_BASE_URL) { $env:DPP_REPO_BASE_URL } else { "http://localhost:8080" }),

    [string]$RegistryUrl = $(if ($env:DPP_REGISTRY_BASE_URL) { $env:DPP_REGISTRY_BASE_URL } else { "http://localhost:8081" }),

    [ValidateRange(1, 600)]
    [int]$WaitTimeout = 120,

    [switch]$ConfirmDelete
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$composeFile = Join-Path $PSScriptRoot "compose.yaml"
if (-not $EnvFile) {
    $EnvFile = Join-Path $PSScriptRoot "env/pinned.env"
}

if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Environment profile does not exist: $EnvFile"
}

function Invoke-DemoCompose {
    param([Parameter(ValueFromRemainingArguments)] [string[]]$Arguments)

    & docker compose -f $composeFile -p $Project --env-file $EnvFile @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Compose action failed: $($Arguments -join ' ')"
    }
}

function Assert-ServiceHealth {
    param(
        [string]$Name,
        [string]$BaseUrl
    )

    $health = Invoke-RestMethod -Uri "$BaseUrl/health"
    if ($health.status -ne "UP") {
        throw "$Name health is not UP."
    }
    $health
}

switch ($Action) {
    "Start" {
        Write-Host "Validate the selected Compose configuration."
        Invoke-DemoCompose config --quiet
        Write-Host "Ensure configured images are available (pull missing images only)."
        Invoke-DemoCompose pull --policy missing
        Write-Host "Start the isolated project and wait for Compose readiness."
        Invoke-DemoCompose up -d --wait --wait-timeout $WaitTimeout
        Write-Host "Show the selected project."
        Invoke-DemoCompose ps
        Write-Host "Check public repository and registry readiness."
        Assert-ServiceHealth -Name "Repository" -BaseUrl $RepoUrl
        Assert-ServiceHealth -Name "Registry" -BaseUrl $RegistryUrl
    }
    "Status" {
        Invoke-DemoCompose ps --all
    }
    "Logs" {
        Invoke-DemoCompose logs --no-color --timestamps
    }
    "Stop" {
        Write-Host "Stop the selected project and keep its database volumes."
        Invoke-DemoCompose down --remove-orphans
    }
    "Delete" {
        if (-not $ConfirmDelete) {
            throw "Refusing to delete database volumes. Repeat with -ConfirmDelete after checking the project name."
        }
        Write-Host "Delete the selected project's containers, network, and database volumes."
        Invoke-DemoCompose down --volumes --remove-orphans
    }
}
