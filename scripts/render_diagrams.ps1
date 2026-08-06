<#
Verifies or renders the repository's canonical Mermaid sources with a pinned,
documentation-only Mermaid CLI container. Run from the repository root:
  powershell -ExecutionPolicy Bypass -File scripts/render_diagrams.ps1 -VerifyOnly

Prerequisite for rendering: Docker. VerifyOnly checks that each tracked Mermaid
source already has a tracked SVG sibling and does not start Docker.
#>
[CmdletBinding()]
param([switch]$VerifyOnly)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$architectureDirectory = Join-Path $repositoryRoot "docs\architecture"
$renderer = "ghcr.io/mermaid-js/mermaid-cli/mermaid-cli:11.4.2@sha256:99c983b3ab4e14033f2880bc1b9de17e5090b4515dabd63fe9cf8c0ae6130956"
$sources = Get-ChildItem -LiteralPath $architectureDirectory -Filter *.mmd -File | Sort-Object Name
if ($sources.Count -eq 0) { throw "No canonical Mermaid sources found" }

foreach ($source in $sources) {
    $output = Join-Path $architectureDirectory ($source.BaseName + ".svg")
    if (!$VerifyOnly) {
        & docker run --rm -v "${repositoryRoot}:/data" $renderer `
            -i "/data/docs/architecture/$($source.Name)" `
            -o "/data/docs/architecture/$($source.BaseName).svg"
        if ($LASTEXITCODE -ne 0) { throw "Mermaid render failed: $($source.Name)" }
    }
    if (!(Test-Path -LiteralPath $output)) { throw "Missing rendered asset: $output" }
}

Write-Host "Verified $($sources.Count) Mermaid source/render pairs using $renderer"
