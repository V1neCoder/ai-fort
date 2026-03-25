# UEFN Toolbelt Integration

This repo vendors the full upstream `undergroundrap/UEFN-TOOLBELT` project in [`vendor/uefn-toolbelt`](/C:/AI%20Fort/unreal-codex-agent/vendor/uefn-toolbelt).

## What Was Imported

- The full upstream file tree is preserved under `vendor/uefn-toolbelt`.
- The editor-side Python package lives at `vendor/uefn-toolbelt/Content/Python/UEFN_Toolbelt`.
- The upstream desktop helpers such as `client.py`, `launcher.py`, `mcp_server.py`, `parse_tools.py`, `docs/`, `tests/`, and `.agents/` are also preserved.

## How Deployment Works Here

This repo already used the vendored `uefn-mcp-server`, and both projects wanted to own `Content/Python/init_unreal.py`.

To keep both systems usable together, the local helper commands now generate a shared `init_unreal.py` in the target UEFN project. That shared init:

1. Starts `uefn_listener.py` when it is present.
2. Imports `uefn_toolbelt_init.py` when the Toolbelt package is present.

The original upstream Toolbelt startup file is preserved as `Content/Python/uefn_toolbelt_init.py` in the target project, so the menu bootstrap and package registration still come from the upstream code.

## Commands

Deploy the full local UEFN stack in one pass:

```bash
python -m apps.mcp_extensions.uefn_tools sync-stack --repo-root .
```

If you prefer the separate steps, those still work:

```bash
python -m apps.mcp_extensions.uefn_tools sync-mcp-listener --repo-root .
python -m apps.mcp_extensions.uefn_tools sync-toolbelt --repo-root .
python -m apps.mcp_extensions.uefn_tools write-mcp-config --repo-root .
```

Inspect the combined status:

```bash
python -m apps.mcp_extensions.uefn_tools status --repo-root .
python -m apps.mcp_extensions.uefn_tools toolbelt-status --repo-root .
python scripts/check_uefn_setup.py --repo-root .
```

Inspect the vendored Toolbelt source catalog:

```bash
python -m apps.mcp_extensions.uefn_tools toolbelt-source-tools --repo-root .
```

Inspect the live registered Toolbelt tools in the connected editor:

```bash
python -m apps.mcp_extensions.uefn_tools toolbelt-live-tools --repo-root .
```

Run the upstream Toolbelt smoke test through the existing local MCP bridge:

```bash
python -m apps.mcp_extensions.uefn_tools toolbelt-smoke-test --repo-root .
```

Run any Toolbelt tool directly from this repo:

```bash
python -m apps.mcp_extensions.uefn_tools toolbelt-run arena_generate --repo-root . --kwargs-json "{\"size\":\"small\"}"
```

The invasive upstream integration test is also exposed, but it now requires an explicit confirmation flag so you do not accidentally run it in a production map:

```bash
python -m apps.mcp_extensions.uefn_tools toolbelt-integration-test --repo-root . --confirm-invasive
```

## Codex Notes

- The upstream repo still includes its original `CLAUDE.md` because it is part of the open-source source tree.
- In this workspace, the active local MCP flow remains Codex-oriented via the existing `.mcp.json` generation and `apps/mcp_extensions/uefn_tools.py`.
- If you want to improve the vendored Toolbelt locally, make changes in `vendor/uefn-toolbelt` and redeploy with `sync-toolbelt`.
