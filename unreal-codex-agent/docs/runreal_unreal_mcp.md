# Legacy runreal/unreal-mcp Integration

This document is archived on purpose.

The repo is no longer designed around:

- `runreal/unreal-mcp`
- Unreal Python Remote Execution
- Python Editor Script Plugin as the primary runtime path

The current supported architecture in this repo is:

- UEFN
- Verse-authored devices
- Fortnite devices
- Scene Graph

Use these current docs instead:

- [UEFN-supported workflows](C:/AI%20Fort/unreal-codex-agent/docs/uefn_supported_workflows.md)
- [Architecture](C:/AI%20Fort/unreal-codex-agent/docs/architecture.md)
- [UEFN required project settings](C:/AI%20Fort/unreal-codex-agent/unreal/content_support/required_project_settings.md)

Legacy compatibility wrappers remain only so older local commands do not break immediately:

- [generate_unreal_mcp_config.py](/C:/AI%20Fort/unreal-codex-agent/scripts/generate_unreal_mcp_config.py)
- [check_unreal_mcp.py](/C:/AI%20Fort/unreal-codex-agent/scripts/check_unreal_mcp.py)

Those wrappers now return migration guidance instead of acting as the main setup path.
