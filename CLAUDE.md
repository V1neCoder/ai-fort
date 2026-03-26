# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workspace Overview

**AI Fort** is a monorepo containing several distinct AI and game development projects. This is a portfolio workspace — projects are independently developed but versioned together under one Git repository.

### Directory Structure

| Project | Purpose | Language | Key File |
|---------|---------|----------|----------|
| **UEFN-TOOLBELT-latest/** | 237-tool UEFN automation framework | Python 3.11 | `UEFN-TOOLBELT-latest/CLAUDE.md` |
| **unreal-codex-agent/** | Desktop Electron app (UEFN tools + AI planning UI) | Python + TypeScript/React | `unreal-codex-agent/README.md` |
| **everything-claude-code/** | Claude Code plugin framework (agents, skills, hooks) | JavaScript + Markdown | `everything-claude-code/CLAUDE.md` |
| **agentscope/** | Multi-agent framework (Alibaba) | Python | `agentscope/README.md` |
| **editor-reference/** | Editor reference implementation | TypeScript | `editor-reference/CLAUDE.md` |
| **uefn/** | UEFN project template/samples | Python | (no CLAUDE.md) |

## Quick Navigation

**Before starting work, read the CLAUDE.md for the specific project you're modifying.** Each has unique rules and patterns:

- Working on UEFN tools? → `UEFN-TOOLBELT-latest/CLAUDE.md`
  - ⚠️ **Mandatory**: test every change in the UEFN editor before committing
  - All PySide6 windows must subclass `ToolbeltWindow` and match the theme
  - 237 tools, fully structured dict returns, MCP-ready

- Working on the Electron desktop app? → `unreal-codex-agent/README.md` + `DEVELOPMENT.md`
  - Full-stack (Python FastAPI backend + React frontend)
  - Setup: `npm install`, virtual environment, `npm start`

- Working on Claude Code plugins/skills? → `everything-claude-code/CLAUDE.md`
  - Conventional commits, modular architecture, separate test layout
  - Agent format: Markdown with YAML frontmatter
  - Skill format: Markdown with clear sections

- Working with AgentScope? → `agentscope/README.md`
  - Multi-agent framework with ReAct, message hub, realtime voice
  - Production-ready, deploy locally or cloud

## Workspace Git Workflow

This workspace tracks all projects under one Git repository. Each subproject may have been cloned from its own upstream (agentscope, everything-claude-code, editor-reference, UEFN-TOOLBELT) but is now versioned here.

### Committing Changes

```bash
cd "C:/AI Fort"

# Stage relevant files
git add UEFN-TOOLBELT-latest/...
# OR
git add everything-claude-code/...
# etc.

# Commit with clear message (project prefix recommended)
git commit -m "uefn-toolbelt: fix verse device property schema validation"
# OR
git commit -m "electron-app: update dashboard UI colors"

# Push to origin
git push origin master
```

**Commit Format** (optional but recommended for clarity in a monorepo):
- `[project-name]: description`
- Projects: `uefn-toolbelt`, `electron-app`, `claude-code-plugin`, `agentscope`, `editor`, `uefn`
- Example: `uefn-toolbelt: add zone_fill_scatter tool`

### Reverting Changes

All changes are reversible via Git:

```bash
# Revert the last commit
git revert HEAD

# Revert changes to specific files (unstaged)
git checkout -- UEFN-TOOLBELT-latest/path/to/file.py

# Undo staged changes
git reset HEAD file.py

# View history
git log --oneline -10
git diff HEAD~1
```

## Development Patterns Across Projects

### Python Projects (UEFN-Toolbelt, unreal-codex-agent, agentscope)

- **Virtual environment**: Always activate before running or installing
  ```bash
  python -m venv .venv
  .venv\Scripts\activate.bat    # Windows
  source .venv/bin/activate      # macOS/Linux
  ```
- **Testing**: Each project specifies its test suite in its own CLAUDE.md
- **Package manager**: Varies by project (see individual docs)

### JavaScript/TypeScript Projects (electron-app frontend, claude-code-plugin)

- **Node.js version**: 20+ required
- **Package manager**: npm (specified in package.json)
- **Test commands**: See individual project CLAUDE.md

### UEFN Projects (UEFN-TOOLBELT, unreal-codex-agent backend)

- **Python version**: 3.11+ (UEFN requirement)
- **Editor integration**: Tools run inside UEFN editor, not at runtime
- **Deployment**: Use `install.py` or `deploy.bat` to copy into UEFN projects
- **Testing requirement**: ⚠️ **Always test in live UEFN before committing** (not just syntax check)

## Key Architecture Decisions

### UEFN-TOOLBELT

- **237 registered tools** across 37 categories, all returning structured dicts
- **PySide6 dashboard** with dark theme, 18 tabs, running inside UEFN
- **MCP bridge** for Claude Code control (http://127.0.0.1:8765)
- **Schema-aware**: Reference schema (uefn_reference_schema.json) + live project schema sync
- **V2 Device Wall**: Fortnite V2 Creative devices use @editable Verse properties, not Python UPROPERTYs — workaround is to generate Verse code instead
- **Phase 6 autonomy pipeline**: Claude reads live level, designs, places devices, generates Verse, fixes build errors

### Unreal Codex Agent (Electron Desktop App)

- **Three-layer architecture**:
  - React frontend (Electron) + TypeScript
  - Python FastAPI backend
  - UEFN MCP bridge → UEFN Toolbelt
- **Integrated tools**: 161 UEFN tools available through the desktop UI
- **Asset AI**: Smart asset management with trust scores
- **Codex planning**: AI-powered island creation and orchestration

### Everything Claude Code

- **Agent framework**: Markdown + YAML frontmatter for specialized subagents
- **Skills**: Documented workflows with clear "When to Use" sections
- **Hooks**: JSON-based automation triggers
- **Commands**: Slash command definitions
- **CI/CD ready**: Conventional commits, test suite, GitHub integration

## Common Development Tasks

### Testing Across the Workspace

| Project | Test Command | Notes |
|---------|--------------|-------|
| **everything-claude-code** | `node tests/run-all.js` | Full test suite |
| **agentscope** | See agentscope/README.md | Multi-agent framework tests |
| **UEFN-Toolbelt** | Live UEFN editor test | ⚠️ Mandatory before commit |
| **unreal-codex-agent** | Backend: `pytest`; Frontend: `npm test` | See DEVELOPMENT.md |

### Building/Running

| Project | Build Command | Notes |
|---------|--------------|-------|
| **UEFN-Toolbelt** | `install.py` or `deploy.bat` | Installs into UEFN project |
| **unreal-codex-agent** | `setup.bat` (Windows) or `setup.sh` (macOS/Linux) | Then `npm start` |
| **everything-claude-code** | No build; uses package.json | Pre-installed on Claude Code |
| **agentscope** | `pip install agentscope` or dev install | See agentscope README |

### Linting / Style Checks

- **Python**: Follow PEP 8 (UEFN Toolbelt uses black, flake8 implicitly through `smoke_test`)
- **JavaScript**: No external linter enforced; follow project conventions
- **Commit messages**: Conventional format (see each project's CLAUDE.md)

## Important Constraints & Warnings

1. **UEFN-Toolbelt UI consistency** (mandatory)
   - All PySide6 windows must subclass `ToolbeltWindow` from `core/base_window.py`
   - Window titles: `"UEFN Toolbelt — Tool Name"` (exact format, never omit prefix)
   - Use only colors from `core/theme.py` palette
   - Every tool window needs a `?` help button
   - Read `docs/ui_style_guide.md` before writing any windowed UI

2. **UEFN Python main thread lock** (critical for async operations)
   - Don't use `time.sleep()` to wait for async file output — it deadlocks the editor
   - Trigger the async action, verify the request sent, exit — file appears ~1 second later

3. **UEFN path quirks** (common source of bugs)
   - Project mount point is NOT `/Game/` in UEFN — use `detect_project_mount()` from `core/__init__.py`
   - `AssetData.package_name` returns the project-mount form, not `/Game/` form
   - See `docs/UEFN_QUIRKS.md` for full list

4. **V2 Creative device properties** (hard limit in current UEFN)
   - Cannot set game-logic properties (duration, score, team index) via Python
   - Workaround: generate Verse code with `@editable` properties instead
   - Read-only Python access: base-class props, method calls (timer_start, etc.)

5. **Git submodules** (workspace structure)
   - Agentscope, everything-claude-code, editor-reference, UEFN-TOOLBELT are independent repos versioned here
   - All `.git` folders removed and content tracked directly in this repo
   - To update a project's upstream: navigate to its folder and pull/merge as needed, then commit changes to the parent

## References & Documentation

- **UEFN Python API**: https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/
- **UEFN Toolbelt Reference**: `UEFN-TOOLBELT-latest/docs/PIPELINE.md` (6-phase autonomy)
- **Electron App**: `unreal-codex-agent/UNIFIED_APP_README.md` (2000+ line user manual)
- **Claude Code Plugins**: `everything-claude-code/CONTRIBUTING.md` (format guide)
- **AgentScope Docs**: https://doc.agentscope.io/ (production-ready agent framework)

## Support & Questions

- Each project has its own CLAUDE.md — start there for project-specific guidance
- Sub-projects may have upstream repos (agentscope, everything-claude-code) — check their original repos for broader context
- Git history and commits are your reference for decisions and patterns

---

## AI Fort Agent System (Cursor + Claude Enhanced Stack)

This workspace uses an enhanced AI agent workflow built on top of Cursor, Claude, and everything-claude-code.

### Core Principle

Claude must not operate as a one-pass generator. All tasks must follow a structured loop:

Perceive → Plan → Edit → Validate → Fix → Confirm

Claude should never mark work complete without validation.

---

## Required Agent Behavior

Before making any changes:

1. Read all relevant files for the task
2. Build a mental model of the system
3. Identify root cause (not symptoms)
4. Propose a plan before editing

During edits:

- Only modify necessary files
- Preserve existing working systems
- Avoid large rewrites unless required
- Keep diffs minimal and reversible

After edits:

- Run a validation pass
- Check for unintended side effects
- Summarize all changes clearly

---

## Validation Rules (MANDATORY)

All generated or modified systems must pass:

- No overlapping geometry
- No floating structures
- Proper alignment to grid / base
- Roofs must match footprint and slope consistently
- No clipping between assets
- Consistent placement logic across systems

If any validation fails:
→ Claude must fix the issue before completing the task

---

## UEFN-Specific Intelligence Layer

When working with UEFN systems:

- Always account for editor constraints and quirks
- Respect project mount path behavior
- Do not assume `/Game/` paths
- Validate all placement logic against real UEFN behavior

For device logic:

- Recognize V2 device limitations
- Use Verse generation when properties cannot be set via Python
- Ensure Verse output is clean, modular, and valid

---

## Repo Awareness + Safety

Claude must treat this workspace as a monorepo:

- Identify which subproject is being modified
- Follow that project's CLAUDE.md before editing
- Never mix logic across unrelated projects

Before any commit suggestion:

- List changed files
- Explain purpose of each change
- Identify potential risks
- Generate a clean commit message

---

## Commit Format Enforcement

Use structured commit messages:

type(scope): description

Examples:
- fix(uefn-toolbelt): correct device schema validation
- feat(electron-app): add asset preview panel
- refactor(claude-plugin): reorganize agent hooks

---

## Cursor Agent Execution Rules

When running in Cursor Agent mode:

- Always scan project before answering
- Do not hallucinate missing code
- Ask for clarification if context is incomplete
- Prefer reading files over guessing
- Break complex tasks into steps

---

## Subagent Role Separation

For complex tasks, Claude should internally separate responsibilities:

- Architect → structure, layout, system design
- Validator → detects errors and inconsistencies
- Repo Guardian → ensures safe diffs and commit readiness
- Verse Engineer → handles Verse-specific logic

Claude should simulate this separation when reasoning through tasks.

---

## Failure Handling

If Claude detects:

- repeated mistakes
- inconsistent outputs
- unclear project structure

It must:

1. Stop
2. Re-analyze the system
3. Identify why the failure occurred
4. Adjust approach before continuing

---

## Final Rule

Claude must prioritize correctness over speed.

A correct, validated, minimal fix is always better than a fast but flawed implementation.

---
## Today (2026-03-26): Uncommitted Repo Changes

The following reflect the current working-tree state (from `git status --porcelain`) and are not committed yet.

Deleted (`D`):
- unreal-codex-agent/data/ai_assets/default/wooden_crate/exports/wooden_crate_v1.glb
- unreal-codex-agent/data/ai_assets/default/wooden_crate/metadata/record.json
- unreal-codex-agent/data/ai_assets/default/wooden_crate/previews/v1_placeholder.png
- unreal-codex-agent/data/ai_assets/default/wooden_crate/source/prompt.json
- unreal-codex-agent/data/ai_assets/default/wooden_crate/source/v1_code.py
- unreal-codex-agent/data/ai_assets/default/wooden_crate_005/exports/wooden_crate_005_v1.glb
- unreal-codex-agent/data/ai_assets/default/wooden_crate_005/metadata/record.json
- unreal-codex-agent/data/ai_assets/default/wooden_crate_005/previews/v1_placeholder.png
- unreal-codex-agent/data/ai_assets/default/wooden_crate_005/source/prompt.json
- unreal-codex-agent/data/ai_assets/default/wooden_crate_005/source/v1_code.py
- unreal-codex-agent/data/ai_assets/default/wooden_crate_005/validation/v1_result.json
- unreal-codex-agent/data/electron_runtime/cache/Cache/Cache_Data/f_000017
- unreal-codex-agent/data/electron_runtime/cache/Cache/Cache_Data/f_00001a

Modified (`M`):
- unreal-codex-agent/data/ai_assets/registry.json
- unreal-codex-agent/data/catalog/shortlist.json
- unreal-codex-agent/data/electron_runtime/cache/Cache/Cache_Data/data_0
- unreal-codex-agent/data/electron_runtime/cache/Cache/Cache_Data/data_1
- unreal-codex-agent/data/electron_runtime/cache/Cache/Cache_Data/data_2
- unreal-codex-agent/data/electron_runtime/cache/Cache/Cache_Data/data_3
- `unreal-codex-agent/data/electron_runtime/cache/Code Cache/js/53cfa7bcdb2af8af_0`
- `unreal-codex-agent/data/electron_runtime/cache/Code Cache/js/index-dir/the-real-index`
- unreal-codex-agent/data/electron_runtime/cache/GPUCache/data_1
- `unreal-codex-agent/data/electron_runtime/cache/Local Storage/leveldb/LOG`
- `unreal-codex-agent/data/electron_runtime/cache/Local Storage/leveldb/LOG.old`
- `unreal-codex-agent/data/electron_runtime/cache/Session Storage/LOG`
- `unreal-codex-agent/data/electron_runtime/cache/Session Storage/LOG.old`
- unreal-codex-agent/vendor/uefn-mcp-server

Untracked (`??`):
- unreal-codex-agent/data/ai_assets/default/luxury_mansion/
- unreal-codex-agent/data/electron_runtime/cache/Cache/Cache_Data/f_00001c
- unreal-codex-agent/data/electron_runtime/cache/Cache/Cache_Data/f_00001e
- unreal-codex-agent/data/electron_runtime/cache/Cache/Cache_Data/f_00002f
- `unreal-codex-agent/data/electron_runtime/cache/Code Cache/js/5719fe40bc1e43c1_0`