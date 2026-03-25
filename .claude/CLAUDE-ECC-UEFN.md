# Everything Claude Code + UEFN Workflow

This file tailors ECC skills for the AI Fort UEFN development workflow (TypeScript + Python + UEFN).

## Workflow Integration

### TDD Workflow (/tdd)
**Applies to:** UEFN Toolbelt tools, Electron app backend + frontend, utilities

**Test Setup by Project:**
- **UEFN-TOOLBELT-latest**: Python + pytest
  ```bash
  cd UEFN-TOOLBELT-latest
  python -m pytest tests/ -v --cov=Content/Python/UEFN_Toolbelt --cov-report=term-missing
  ```

- **unreal-codex-agent (backend)**: Python + pytest
  ```bash
  cd unreal-codex-agent
  pytest app/backend/tests/ -v --cov=app/backend
  ```

- **unreal-codex-agent (frontend)**: TypeScript + Vitest/Jest
  ```bash
  cd unreal-codex-agent/app/frontend
  npm test -- --coverage
  ```

- **everything-claude-code**: JavaScript + Node
  ```bash
  cd everything-claude-code
  node tests/run-all.js
  ```

**Minimum Coverage**: 80% (unit + integration + E2E)

**Key TDD Principles for This Repo**:
1. Write tests BEFORE implementation
2. Test UEFN Python changes in live editor before committing (UEFN-Toolbelt rule)
3. Frontend E2E tests with Playwright for Electron app critical paths
4. Mock external APIs (UEFN MCP bridge) in unit tests

---

### Verification Loop (/verification-loop)
Run after completing features or before PRs.

**Phase 1: Build Verification**
```bash
# TypeScript projects (Electron app frontend)
npm run build

# Python projects
python -m py_compile Content/Python/UEFN_Toolbelt/**/*.py
```

**Phase 2: Type Check**
```bash
# TypeScript
npx tsc --noEmit

# Python
pyright UEFN-TOOLBELT-latest/Content/Python/
```

**Phase 3: Lint Check**
```bash
# JavaScript/TypeScript
npm run lint

# Python (UEFN Toolbelt)
ruff check UEFN-TOOLBELT-latest/Content/Python/
```

**Phase 4: Test Execution**
```bash
# Run all test suites for affected projects
node everything-claude-code/tests/run-all.js
pytest UEFN-TOOLBELT-latest/tests/ -v
pytest unreal-codex-agent/app/backend/tests/ -v
npm test --prefix unreal-codex-agent/app/frontend
```

**Phase 5: Security Review** (/security-review)
- UEFN-Toolbelt: Check for unsafe unreal.* API calls, module injection
- Electron app: Authenticate MCP bridge calls, validate user input, prevent XSS
- No API keys hardcoded anywhere

---

### E2E Testing (/e2e-testing)
**Critical paths to test:**

1. **Electron App**:
   - Launch app → Tool dashboard visible
   - Select tool → Tool executes with parameters
   - Results display correctly in UI
   - Error handling (tool failure, timeout)

2. **UEFN Toolbelt MCP Bridge**:
   - Connect Claude Code → tb.run() callable
   - Execute tool from MCP → Result returned to Claude
   - Async operations (screenshots, exports) complete

3. **Backend API (FastAPI)**:
   - POST tool execution → returns structured result
   - GET tool list → returns 161 tools with metadata
   - Error responses (invalid tool, missing params)

**Test Framework**: Playwright for Electron, pytest for backend

---

### Security Review (/security-review)
**UEFN-specific security checklist:**

- [ ] No unreal.* calls on non-main thread (Main Thread Lock rule)
- [ ] No subprocess.call for Verse compilation (unreliable in sandbox)
- [ ] File paths use forward slashes and correct project mount
- [ ] V2 device properties only set via Verse code, not Python
- [ ] MCP bridge validates all incoming commands (no code injection)
- [ ] Secrets (API keys) in env vars, not hardcoded
- [ ] PySide6 windows use ToolbeltWindow base class with theme consistency

**See Also**: UEFN-TOOLBELT-latest/CLAUDE.md § "UEFN Python — Critical Rules"

---

### Code Review (/python-review, /typescript-review, etc.)
Standards by project:

**Python (UEFN Toolbelt + Backend)**:
- PEP 8 compliance
- Type hints (Python 3.11+)
- Docstrings for public APIs
- Error handling with structured returns

**TypeScript/React (Electron Frontend)**:
- Strict mode enabled
- No `any` types (use proper typing)
- Component composition patterns
- Props with explicit types

**JavaScript (Claude Code Skills)**:
- ES2020+ syntax
- Consistent formatting (prettier/eslint)
- Proper error handling
- Clear function signatures

---

### Continuous Learning (/continuous-learning)
After each session, extract reusable patterns:

- UEFN-specific patterns → `UEFN-TOOLBELT-latest/docs/PATTERNS.md`
- Electron app patterns → `unreal-codex-agent/DEVELOPMENT.md`
- Claude Code skill patterns → `everything-claude-code/docs/PATTERNS.md`

---

## Project-Specific Skill Mappings

| Task | Skill | Context |
|------|-------|---------|
| Add UEFN tool | `/tdd` + `security-review` | Test in live UEFN before commit (non-negotiable) |
| Electron UI feature | `/tdd` + `/e2e-testing` | Frontend E2E, backend mocking, integration tests |
| FastAPI endpoint | `/tdd` + `verification-loop` | Unit + integration tests, type checking |
| Fix bug | `/tdd` + `verification-loop` | Regression test first, then fix |
| Refactor | `/tdd` + `verification-loop` | Maintain 80%+ coverage throughout |
| MCP bridge change | `security-review` + `/tdd` | Validate command injection, test response handling |
| Before PR | `verification-loop` + `security-review` | Full build, tests, lint, security checks |

---

## Monorepo Git Workflow

**Commit Format** (ECC conventional commits):
```
type(scope): description

[optional body]

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

**Types**:
- `feat`: New feature or tool
- `fix`: Bug fix
- `refactor`: Code restructuring (no behavior change)
- `test`: Test additions/updates
- `docs`: Documentation
- `perf`: Performance optimization

**Scopes**:
- `uefn-toolbelt`: UEFN Toolbelt changes
- `electron-app`: Electron desktop app (frontend + backend)
- `claude-code`: ECC skills or hooks
- `agentscope`: AgentScope framework
- `(root)`: Project-level files (CLAUDE.md, .gitignore, etc.)

**Examples**:
```
feat(uefn-toolbelt): add zone_fill_scatter tool

This tool randomly scatters props within a zone volume
using Poisson-disk sampling for natural distribution.

Auto-commit by session exit hook.
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

```
fix(electron-app): handle MCP bridge timeout gracefully

Wrapped tool execution calls with 30s timeout and user
feedback modal when MCP server is unreachable.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

---

## Automated Hooks (Configured in .claude/settings.local.json)

- **Stop hook**: Auto-commit + push changes to GitHub on session exit
- **Pre-commit hooks**: Git hooks in project (if configured separately)

See `.claude/settings.local.json` for hook definitions.

---

## Next Steps

1. **Load these rules**: Restart Claude Code to load `.claude/rules/*.md`
2. **Test ECC skills**: Try `/tdd` or `/verification-loop` on a feature branch
3. **Extract project instincts**: Use `/learn-eval` or `continuous-learning` after productive sessions
4. **Customize for your workflow**: Adjust coverage targets, add UEFN-specific lint rules, etc.

