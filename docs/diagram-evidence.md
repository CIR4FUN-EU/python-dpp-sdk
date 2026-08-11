# Python SDK diagram publication evidence

## Purpose and convention

Every consumer-facing diagram keeps an editable Mermaid source and a committed SVG rendered with
the pinned Mermaid CLI in [`../scripts/render_diagrams.ps1`](../scripts/render_diagrams.ps1).
Markdown publishes the SVG
with a repository-relative forward-slash path, alt text, and a caption. Do not embed a Mermaid or
Draw.io source as an image, and do not rely solely on GitLab Mermaid rendering.

## Render and verify

**Purpose:** generate or verify all Mermaid source/render pairs. **Run from:** repository root.
**Prerequisites:** Docker can pull the pinned
`ghcr.io/mermaid-js/mermaid-cli/mermaid-cli:11.4.2` image with digest
`sha256:99c983b3ab4e14033f2880bc1b9de17e5090b4515dabd63fe9cf8c0ae6130956`.

### PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File scripts/render_diagrams.ps1
powershell -ExecutionPolicy Bypass -File scripts/render_diagrams.ps1 -VerifyOnly
```

### Linux/macOS

```bash
pwsh -ExecutionPolicy Bypass -File scripts/render_diagrams.ps1
pwsh -ExecutionPolicy Bypass -File scripts/render_diagrams.ps1 -VerifyOnly
```

**Expected result:** each `.mmd` has a sibling `.svg`; `-VerifyOnly` does not generate assets.
**Cleanup:** none. Review regenerated SVG diffs before adding them to a change.

## Consumer diagram inventory

| ID | Editable source | Rendered asset | References | Source evidence |
|---|---|---|---|---|
| Python SDK overview | [`python-sdk-overview.mmd`](architecture/python-sdk-overview.mmd) | [`python-sdk-overview.svg`](architecture/python-sdk-overview.svg) | Root README and `docs/overview.md` | Current package exports and import direction |
| Client request flow | [`python-client-request-flow.mmd`](architecture/python-client-request-flow.mmd) | [`python-client-request-flow.svg`](architecture/python-client-request-flow.svg) | Clients README | Public `DppRepoClient` and `DppRegistryClient` methods |
| Core boundary | [`python-core-model.mmd`](architecture/python-core-model.mmd) | [`python-core-model.svg`](architecture/python-core-model.svg) | Core README | Core model and validation ownership |
| DPP4Fun boundary | [`python-dpp4fun-model.mmd`](architecture/python-dpp4fun-model.mmd) | [`python-dpp4fun-model.svg`](architecture/python-dpp4fun-model.svg) | DPP4Fun README | Aggregate, validation, and transport ownership |

The editable sources and rendered SVGs use safe lowercase hyphenated names without spaces or URL
encoding. Architecture evidence not referenced by maintained Python consumer documentation is
outside this publication inventory.
