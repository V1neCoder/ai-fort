from __future__ import annotations

import json
import re
import shutil
import textwrap
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from apps.integrations.uefn_backend import backend_settings, uefn_content_root


def _resolve_repo_path(repo_root: Path, value: Any, default: str) -> Path:
    raw = str(value or default).strip() or default
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _write_atomic_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _copy_text_file(source: Path, destination: Path) -> None:
    _write_atomic_text(destination, source.read_text(encoding="utf-8"))


def _copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _register_tool_blocks(path: Path) -> list[dict[str, str]]:
    try:
        payload = path.read_text(encoding="utf-8-sig")
    except OSError:
        return []

    matches = re.finditer(
        r"@register_tool\s*\((?P<body>.*?)\)\s*def\s+(?P<fn>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
        payload,
        flags=re.DOTALL,
    )
    entries: list[dict[str, str]] = []
    for match in matches:
        body = match.group("body")

        def _extract(key: str) -> str:
            value_match = re.search(rf"{key}\s*=\s*['\"]([^'\"]+)['\"]", body, flags=re.DOTALL)
            return value_match.group(1).strip() if value_match else ""

        name = _extract("name")
        if not name:
            continue
        entries.append(
            {
                "name": name,
                "category": _extract("category") or "Utilities",
                "description": _extract("description"),
                "function_name": match.group("fn"),
            }
        )
    return entries


def toolbelt_settings(repo_root: Path) -> dict[str, Any]:
    settings = backend_settings(repo_root)
    return {
        "enabled": bool(settings.get("uefn_toolbelt_enabled", False)),
        "repo_root": _resolve_repo_path(repo_root, settings.get("uefn_toolbelt_repo_path"), "vendor/uefn-toolbelt"),
        "python_root": _resolve_repo_path(
            repo_root,
            settings.get("uefn_toolbelt_python_root"),
            "vendor/uefn-toolbelt/Content/Python",
        ),
        "package_root": _resolve_repo_path(
            repo_root,
            settings.get("uefn_toolbelt_package_path"),
            "vendor/uefn-toolbelt/Content/Python/UEFN_Toolbelt",
        ),
        "init_source_path": _resolve_repo_path(
            repo_root,
            settings.get("uefn_toolbelt_init_path"),
            "vendor/uefn-toolbelt/init_unreal.py",
        ),
        "mcp_server_path": _resolve_repo_path(
            repo_root,
            settings.get("uefn_toolbelt_mcp_server_path"),
            "vendor/uefn-toolbelt/mcp_server.py",
        ),
        "client_path": _resolve_repo_path(
            repo_root,
            settings.get("uefn_toolbelt_client_path"),
            "vendor/uefn-toolbelt/client.py",
        ),
        "launcher_path": _resolve_repo_path(
            repo_root,
            settings.get("uefn_toolbelt_launcher_path"),
            "vendor/uefn-toolbelt/launcher.py",
        ),
        "docs_root": _resolve_repo_path(
            repo_root,
            settings.get("uefn_toolbelt_docs_root"),
            "vendor/uefn-toolbelt/docs",
        ),
        "workflows_root": _resolve_repo_path(
            repo_root,
            settings.get("uefn_toolbelt_workflows_root"),
            "vendor/uefn-toolbelt/.agents/workflows",
        ),
        "tool_status_path": _resolve_repo_path(
            repo_root,
            settings.get("uefn_toolbelt_tool_status_path"),
            "vendor/uefn-toolbelt/TOOL_STATUS.md",
        ),
        "smoke_test_path": _resolve_repo_path(
            repo_root,
            settings.get("uefn_toolbelt_smoke_test_path"),
            "vendor/uefn-toolbelt/tests/smoke_test.py",
        ),
        "tools_dump_path": _resolve_repo_path(
            repo_root,
            settings.get("uefn_toolbelt_tools_dump_path"),
            "vendor/uefn-toolbelt/tools_dump.json",
        ),
    }


def toolbelt_content_python_root(repo_root: Path) -> Path | None:
    content_root = uefn_content_root(repo_root)
    if content_root is None:
        return None
    return (content_root / "Python").resolve()


def build_shared_init_script() -> str:
    return '''"""
Shared init_unreal.py generated by unreal-codex-agent.

This startup shim keeps both the vendored UEFN MCP listener and the vendored
UEFN Toolbelt active without forcing either integration to own init_unreal.py.
"""

from __future__ import annotations

import os
import sys

import unreal

_CONTENT_PYTHON = os.path.join(unreal.Paths.project_content_dir(), "Python")

if _CONTENT_PYTHON not in sys.path:
    sys.path.insert(0, _CONTENT_PYTHON)


def _start_mcp_listener() -> None:
    listener_path = os.path.join(_CONTENT_PYTHON, "uefn_listener.py")
    if not os.path.exists(listener_path):
        return
    try:
        import uefn_listener

        if getattr(uefn_listener, "_server", None) is None:
            port = uefn_listener.start_listener()
            unreal.log(f"[MCP] Auto-started on port {port}")
        else:
            unreal.log(f"[MCP] Already running on port {getattr(uefn_listener, '_bound_port', 'unknown')}")
    except Exception as exc:  # noqa: BLE001
        unreal.log_error(f"[MCP] Auto-start failed: {exc}")


def _bootstrap_toolbelt() -> None:
    package_path = os.path.join(_CONTENT_PYTHON, "UEFN_Toolbelt")
    init_path = os.path.join(_CONTENT_PYTHON, "uefn_toolbelt_init.py")
    if not os.path.isdir(package_path) and not os.path.exists(init_path):
        return
    try:
        import uefn_toolbelt_init  # noqa: F401

        unreal.log("[TOOLBELT] Shared init bootstrapped Toolbelt.")
    except Exception as exc:  # noqa: BLE001
        unreal.log_error(f"[TOOLBELT] Shared init failed: {exc}")


_start_mcp_listener()
_bootstrap_toolbelt()
'''


def write_shared_init_script(destination_root: Path) -> Path:
    destination_root.mkdir(parents=True, exist_ok=True)
    target_path = destination_root / "init_unreal.py"
    _write_atomic_text(target_path, build_shared_init_script())
    return target_path


def _toolbelt_project_root_from_content_python(target_root: Path) -> Path:
    return target_root.parent.parent


def _source_tool_entries(settings: dict[str, Any]) -> list[dict[str, str]]:
    package_root = Path(settings["package_root"])
    tools: list[dict[str, str]] = []
    if package_root.exists():
        for path in sorted(package_root.rglob("*.py")):
            relative_path = path.relative_to(package_root).as_posix()
            for entry in _register_tool_blocks(path):
                tools.append(
                    {
                        "name": entry["name"],
                        "category": entry["category"],
                        "description": entry["description"],
                        "function_name": entry["function_name"],
                        "source_file": relative_path,
                    }
                )
    if tools:
        return sorted(tools, key=lambda item: (item["category"], item["name"]))

    payload = _read_json_file(Path(settings["tools_dump_path"]))
    if isinstance(payload, list):
        fallback_tools: list[dict[str, str]] = []
        for raw_entry in payload:
            if not isinstance(raw_entry, dict):
                continue
            name = str(raw_entry.get("name") or "").strip()
            if not name:
                continue
            fallback_tools.append(
                {
                    "name": name,
                    "category": str(raw_entry.get("category") or "Utilities").strip() or "Utilities",
                    "description": str(raw_entry.get("description") or "").strip(),
                    "function_name": "",
                    "source_file": str(raw_entry.get("source_file") or "").strip(),
                }
            )
        return sorted(fallback_tools, key=lambda item: (item["category"], item["name"]))
    return []


def _workflow_entries(settings: dict[str, Any]) -> list[dict[str, str]]:
    workflows_root = Path(settings["workflows_root"])
    if not workflows_root.exists():
        return []
    entries: list[dict[str, str]] = []
    for path in sorted(workflows_root.glob("*.md")):
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            lines = []
        description = ""
        for line in lines[:10]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key.strip().lower() == "description":
                description = value.strip()
                break
        entries.append(
            {
                "name": path.name,
                "description": description,
                "path": str(path),
            }
        )
    return entries


def toolbelt_source_inventory(repo_root: Path) -> dict[str, Any]:
    settings = toolbelt_settings(repo_root)
    tools = _source_tool_entries(settings)
    workflows = _workflow_entries(settings)
    categories = sorted({entry["category"] for entry in tools if entry.get("category")})
    return {
        "tool_count": len(tools),
        "category_count": len(categories),
        "categories": categories,
        "workflow_count": len(workflows),
        "workflows": workflows,
        "sample_tools": tools[:25],
        "paths": {
            "repo_root": str(settings["repo_root"]),
            "package_root": str(settings["package_root"]),
            "tools_dump_path": str(settings["tools_dump_path"]),
            "workflows_root": str(settings["workflows_root"]),
            "tool_status_path": str(settings["tool_status_path"]),
            "smoke_test_path": str(settings["smoke_test_path"]),
        },
        "files": {
            "repo_root_exists": Path(settings["repo_root"]).exists(),
            "package_root_exists": Path(settings["package_root"]).exists(),
            "init_source_exists": Path(settings["init_source_path"]).exists(),
            "tools_dump_exists": Path(settings["tools_dump_path"]).exists(),
            "workflows_root_exists": Path(settings["workflows_root"]).exists(),
            "tool_status_exists": Path(settings["tool_status_path"]).exists(),
            "smoke_test_exists": Path(settings["smoke_test_path"]).exists(),
        },
    }


def toolbelt_list_source_tools(
    repo_root: Path,
    *,
    category: str = "",
    query: str = "",
) -> dict[str, Any]:
    settings = toolbelt_settings(repo_root)
    tools = _source_tool_entries(settings)
    normalized_category = category.strip()
    normalized_query = query.strip().lower()
    if normalized_category:
        tools = [tool for tool in tools if tool.get("category") == normalized_category]
    if normalized_query:
        tools = [
            tool
            for tool in tools
            if normalized_query
            in " ".join(
                [
                    str(tool.get("name") or ""),
                    str(tool.get("category") or ""),
                    str(tool.get("description") or ""),
                    str(tool.get("source_file") or ""),
                ]
            ).lower()
        ]
    return {
        "status": "ok",
        "tool_count": len(tools),
        "category": normalized_category,
        "query": query,
        "tools": tools,
    }


def _build_toolbelt_editor_script(
    *,
    body: str,
    payload: dict[str, Any] | None = None,
    reload_modules: bool = False,
) -> str:
    payload_json = json.dumps(payload or {}, ensure_ascii=True)
    indented_body = textwrap.indent(body.strip(), "    ")
    reload_code = ""
    if reload_modules:
        reload_code = """
for key in list(sys.modules):
    if "UEFN_Toolbelt" in key or key == "uefn_toolbelt_init":
        sys.modules.pop(key, None)
"""
    return f"""
import json
import sys

payload = json.loads({payload_json!r})
result = {{}}

def _tb_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {{str(key): _tb_safe(item) for key, item in value.items()}}
    if isinstance(value, (list, tuple, set)):
        return [_tb_safe(item) for item in value]
    try:
        return str(value)
    except Exception:
        return "<unserializable>"

{reload_code}

try:
    import UEFN_Toolbelt as tb

    existing_tools = []
    try:
        existing_tools = list(tb.registry.list_tools())
    except Exception:
        existing_tools = []
    if payload.get("force_register") or not existing_tools:
        tb.register_all_tools()

{indented_body}
except Exception as exc:
    result = {{"status": "error", "error": str(exc)}}
"""


def _run_live_toolbelt_script(
    repo_root: Path,
    *,
    body: str,
    payload: dict[str, Any] | None = None,
    reload_modules: bool = False,
    timeout: float = 20.0,
) -> dict[str, Any]:
    from apps.integrations.uefn_mcp import execute_python

    execution = execute_python(
        repo_root,
        _build_toolbelt_editor_script(body=body, payload=payload, reload_modules=reload_modules),
        timeout=timeout,
    )
    result = execution.get("result")
    normalized = dict(result) if isinstance(result, dict) else {"value": result}
    normalized["stdout"] = str(execution.get("stdout") or "")
    normalized["stderr"] = str(execution.get("stderr") or "")
    return normalized


def toolbelt_live_status(repo_root: Path, *, reload_modules: bool = False) -> dict[str, Any]:
    return _run_live_toolbelt_script(
        repo_root,
        reload_modules=reload_modules,
        timeout=25.0,
        body="""
tools = [dict(item) for item in tb.registry.list_tools()]
categories = list(tb.registry.categories())
result = {
    "status": "ok",
    "tool_count": len(tools),
    "category_count": len(categories),
    "categories": categories,
    "sample_tools": [str(item.get("name") or "") for item in tools[:25]],
    "dashboard_available": hasattr(tb, "launch_qt"),
    "toolbelt_module": str(getattr(tb, "__file__", "")),
    "smoke_test_registered": "toolbelt_smoke_test" in tb.registry,
    "integration_test_registered": "toolbelt_integration_test" in tb.registry,
}
""",
    )


def toolbelt_list_live_tools(
    repo_root: Path,
    *,
    category: str = "",
    query: str = "",
    reload_modules: bool = False,
) -> dict[str, Any]:
    return _run_live_toolbelt_script(
        repo_root,
        reload_modules=reload_modules,
        timeout=25.0,
        payload={
            "category": category,
            "query": query,
        },
        body="""
tools = [dict(item) for item in tb.registry.list_tools()]
category = str(payload.get("category") or "").strip()
query = str(payload.get("query") or "").strip().lower()
if category:
    tools = [item for item in tools if str(item.get("category") or "") == category]
if query:
    def _haystack(item):
        tags = item.get("tags") or []
        return " ".join(
            [
                str(item.get("name") or ""),
                str(item.get("category") or ""),
                str(item.get("description") or ""),
                " ".join(str(tag) for tag in tags),
            ]
        ).lower()
    tools = [item for item in tools if query in _haystack(item)]
tools.sort(key=lambda item: (str(item.get("category") or ""), str(item.get("name") or "")))
result = {
    "status": "ok",
    "tool_count": len(tools),
    "category": category,
    "query": payload.get("query") or "",
    "tools": _tb_safe(tools),
}
""",
    )


def toolbelt_nuclear_reload(repo_root: Path) -> dict[str, Any]:
    return _run_live_toolbelt_script(
        repo_root,
        reload_modules=True,
        timeout=30.0,
        payload={"force_register": True},
        body="""
tools = [dict(item) for item in tb.registry.list_tools()]
categories = list(tb.registry.categories())
result = {
    "status": "ok",
    "action": "nuclear_reload",
    "tool_count": len(tools),
    "category_count": len(categories),
    "categories": categories,
    "sample_tools": [str(item.get("name") or "") for item in tools[:25]],
}
""",
    )


def toolbelt_launch(
    repo_root: Path,
    *,
    mode: str = "qt",
    reload_modules: bool = False,
) -> dict[str, Any]:
    return _run_live_toolbelt_script(
        repo_root,
        reload_modules=reload_modules,
        timeout=25.0,
        payload={
            "mode": mode,
        },
        body="""
mode = str(payload.get("mode") or "qt").strip().lower()
if mode == "qt":
    tb.launch_qt()
elif mode in {"fallback", "default", "launch"}:
    tb.launch()
else:
    raise ValueError(f"Unsupported Toolbelt launch mode: {mode}")
result = {
    "status": "ok",
    "launched": True,
    "mode": mode,
}
""",
    )


def toolbelt_run_tool(
    repo_root: Path,
    *,
    tool_name: str,
    kwargs: dict[str, Any] | None = None,
    reload_modules: bool = False,
    timeout: float = 30.0,
) -> dict[str, Any]:
    return _run_live_toolbelt_script(
        repo_root,
        reload_modules=reload_modules,
        timeout=timeout,
        payload={
            "tool_name": tool_name,
            "kwargs": kwargs or {},
        },
        body="""
tool_name = str(payload.get("tool_name") or "").strip()
if not tool_name:
    raise ValueError("tool_name is required.")
if tool_name not in tb.registry:
    raise ValueError(f"Unknown Toolbelt tool: {tool_name}")
tool_kwargs = payload.get("kwargs") or {}
run_result = tb.run(tool_name, **tool_kwargs)
result = {
    "status": "ok",
    "tool_name": tool_name,
    "kwargs": _tb_safe(tool_kwargs),
    "run_result": _tb_safe(run_result),
}
""",
    )


def toolbelt_deployment_status(repo_root: Path) -> dict[str, Any]:
    target_root = toolbelt_content_python_root(repo_root)
    settings = toolbelt_settings(repo_root)
    if target_root is None:
        return {
            "content_python_root": "",
            "package_path": "",
            "toolbelt_init_path": "",
            "shared_init_path": "",
            "runtime_smoke_test_path": "",
            "package_exists": False,
            "toolbelt_init_exists": False,
            "shared_init_exists": False,
            "runtime_smoke_test_exists": False,
            "ready": False,
            "vendor_ready": settings["package_root"].exists() and settings["init_source_path"].exists(),
        }
    package_path = target_root / "UEFN_Toolbelt"
    toolbelt_init_path = target_root / "uefn_toolbelt_init.py"
    shared_init_path = target_root / "init_unreal.py"
    runtime_smoke_test_path = _toolbelt_project_root_from_content_python(target_root) / "tests" / "smoke_test.py"
    return {
        "content_python_root": str(target_root),
        "package_path": str(package_path),
        "toolbelt_init_path": str(toolbelt_init_path),
        "shared_init_path": str(shared_init_path),
        "runtime_smoke_test_path": str(runtime_smoke_test_path),
        "package_exists": package_path.exists(),
        "toolbelt_init_exists": toolbelt_init_path.exists(),
        "shared_init_exists": shared_init_path.exists(),
        "runtime_smoke_test_exists": runtime_smoke_test_path.exists(),
        "ready": package_path.exists() and toolbelt_init_path.exists() and shared_init_path.exists(),
        "vendor_ready": settings["package_root"].exists() and settings["init_source_path"].exists(),
    }


def toolbelt_status_summary(repo_root: Path) -> dict[str, Any]:
    settings = toolbelt_settings(repo_root)
    deployed = toolbelt_deployment_status(repo_root)
    live_status: dict[str, Any] = {
        "available": False,
        "reason": "UEFN MCP listener is not available.",
    }
    try:
        from apps.integrations.uefn_mcp import mcp_listener_running

        if settings["enabled"] and deployed["ready"] and mcp_listener_running(repo_root):
            live_status = {
                "available": True,
                **toolbelt_live_status(repo_root),
            }
        elif not deployed["ready"]:
            live_status = {
                "available": False,
                "reason": "Toolbelt is not deployed into the UEFN Content/Python directory.",
            }
    except Exception as exc:  # noqa: BLE001
        live_status = {
            "available": False,
            "error": str(exc),
        }
    return {
        "enabled": settings["enabled"],
        "vendored": settings["repo_root"].exists(),
        "vendor_ready": deployed["vendor_ready"],
        "deployed": deployed["ready"],
        "source_inventory": toolbelt_source_inventory(repo_root),
        "live_status": live_status,
        "paths": {
            "repo_root": str(settings["repo_root"]),
            "python_root": str(settings["python_root"]),
            "package_root": str(settings["package_root"]),
            "init_source_path": str(settings["init_source_path"]),
            "mcp_server_path": str(settings["mcp_server_path"]),
            "client_path": str(settings["client_path"]),
            "launcher_path": str(settings["launcher_path"]),
            "docs_root": str(settings["docs_root"]),
            "workflows_root": str(settings["workflows_root"]),
            "tool_status_path": str(settings["tool_status_path"]),
            "smoke_test_path": str(settings["smoke_test_path"]),
            "tools_dump_path": str(settings["tools_dump_path"]),
            "content_python_root": deployed["content_python_root"],
            "package_path": deployed["package_path"],
            "toolbelt_init_path": deployed["toolbelt_init_path"],
            "shared_init_path": deployed["shared_init_path"],
            "runtime_smoke_test_path": deployed["runtime_smoke_test_path"],
        },
    }


def deploy_toolbelt_files(repo_root: Path, destination_root: Path | None = None) -> dict[str, Any]:
    settings = toolbelt_settings(repo_root)
    target_root = destination_root or toolbelt_content_python_root(repo_root)
    if target_root is None:
        raise ValueError("Could not determine the UEFN Content/Python directory.")
    if not settings["package_root"].exists():
        raise FileNotFoundError(f"UEFN Toolbelt package was not found: {settings['package_root']}")
    if not settings["init_source_path"].exists():
        raise FileNotFoundError(f"UEFN Toolbelt init file was not found: {settings['init_source_path']}")

    target_root.mkdir(parents=True, exist_ok=True)
    deployed_package_path = target_root / "UEFN_Toolbelt"
    deployed_toolbelt_init_path = target_root / "uefn_toolbelt_init.py"
    deployed_runtime_smoke_test_path = _toolbelt_project_root_from_content_python(target_root) / "tests" / "smoke_test.py"
    _copy_tree(settings["package_root"], deployed_package_path)
    _copy_text_file(settings["init_source_path"], deployed_toolbelt_init_path)
    if settings["smoke_test_path"].exists():
        _copy_text_file(settings["smoke_test_path"], deployed_runtime_smoke_test_path)
    shared_init_path = write_shared_init_script(target_root)

    return {
        "content_python_root": str(target_root),
        "package_path": str(deployed_package_path),
        "toolbelt_init_path": str(deployed_toolbelt_init_path),
        "shared_init_path": str(shared_init_path),
        "runtime_smoke_test_path": str(deployed_runtime_smoke_test_path),
        "package_exists": deployed_package_path.exists(),
        "toolbelt_init_exists": deployed_toolbelt_init_path.exists(),
        "shared_init_exists": shared_init_path.exists(),
        "runtime_smoke_test_exists": deployed_runtime_smoke_test_path.exists(),
    }
