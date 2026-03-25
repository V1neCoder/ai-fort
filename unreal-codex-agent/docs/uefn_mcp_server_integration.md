# UEFN MCP Server Integration

This repo vendors [KirChuvakov/uefn-mcp-server](https://github.com/KirChuvakov/uefn-mcp-server) under:

- `vendor/uefn-mcp-server`

The bridge gives the local scaffold a direct UEFN editor path for:

- reading live actors
- reading level info
- running editor-side Python
- supporting future direct placement and viewport tooling

## What gets deployed into the island project

Use:

```bash
python -m apps.mcp_extensions.uefn_tools sync-mcp-listener --repo-root .
```

That copies these files into `<YourProject>/Content/Python/`:

- `uefn_listener.py`
- `init_unreal.py`

With those in place, UEFN can auto-start the listener on project open when Python scripting is enabled.

## Client config

Use:

```bash
python -m apps.mcp_extensions.uefn_tools write-mcp-config --repo-root .
```

That writes `.mcp.json` in the repo root and points it at the vendored `mcp_server.py`.

## Required local install

The external MCP server needs:

```bash
pip install mcp
```

This repo now includes `mcp` in `requirements.txt` and `pyproject.toml`.

## Repo behavior

When `scene_state.backend` is `auto`, the repo now tries scene backends in this order:

1. `uefn_mcp` if the listener is running
2. `uefn_session_export` if a saved scene export exists
3. `fallback`

That keeps the local loop stable while still preferring live UEFN data when available.

## Useful commands

```bash
python -m apps.mcp_extensions.uefn_tools mcp-status --repo-root .
python -m apps.mcp_extensions.uefn_tools sync-mcp-listener --repo-root .
python -m apps.mcp_extensions.uefn_tools write-mcp-config --repo-root .
python scripts/check_uefn_setup.py --repo-root .
```

## Important note

This bridge is unofficial and separate from Epic's supported Verse/device workflow. In this repo it is treated as:

- preferred for live editor reads
- optional for direct editor control
- safe to fall back from when unavailable
