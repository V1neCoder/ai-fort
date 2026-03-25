import json
from pathlib import Path

from apps.integrations.uefn_backend import backend_settings, backend_summary
from apps.integrations.uefn_toolbelt import (
    build_shared_init_script,
    deploy_toolbelt_files,
    toolbelt_list_source_tools,
    toolbelt_source_inventory,
    toolbelt_status_summary,
)


def _write_repo_config(repo_root: Path) -> None:
    config_dir = repo_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "project.json").write_text(
        json.dumps(
            {
                "integrations": {
                    "uefn_mcp": {
                        "enabled": True,
                    },
                    "uefn_toolbelt": {
                        "enabled": True,
                    },
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_fake_toolbelt_vendor(repo_root: Path) -> None:
    package_root = repo_root / "vendor" / "uefn-toolbelt" / "Content" / "Python" / "UEFN_Toolbelt"
    package_root.mkdir(parents=True, exist_ok=True)
    (package_root / "__init__.py").write_text("registry = []\n", encoding="utf-8")
    (package_root / "tools").mkdir(parents=True, exist_ok=True)
    (package_root / "tools" / "sample_tool.py").write_text(
        "\n".join(
            [
                "from UEFN_Toolbelt.registry import register_tool",
                "",
                '@register_tool(name="sample_tool", category="Utilities", description="Sample tool")',
                "def sample_tool(**kwargs):",
                "    return kwargs",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "vendor" / "uefn-toolbelt" / "init_unreal.py").write_text(
        "import unreal\nunreal.log('toolbelt init')\n",
        encoding="utf-8",
    )
    workflows_root = repo_root / "vendor" / "uefn-toolbelt" / ".agents" / "workflows"
    workflows_root.mkdir(parents=True, exist_ok=True)
    (workflows_root / "run_tests.md").write_text("description: test workflow\n", encoding="utf-8")
    tests_root = repo_root / "vendor" / "uefn-toolbelt" / "tests"
    tests_root.mkdir(parents=True, exist_ok=True)
    (tests_root / "smoke_test.py").write_text("def run_smoke_test():\n    return True\n", encoding="utf-8")
    (repo_root / "vendor" / "uefn-toolbelt" / "TOOL_STATUS.md").write_text("[A] sample_tool\n", encoding="utf-8")


def test_backend_settings_expose_toolbelt_paths(tmp_path: Path):
    _write_repo_config(tmp_path)

    settings = backend_settings(tmp_path)

    assert settings["uefn_toolbelt_enabled"] is True
    assert settings["uefn_toolbelt_repo_path"].endswith("vendor\\uefn-toolbelt")
    assert settings["uefn_toolbelt_package_path"].endswith("vendor\\uefn-toolbelt\\Content\\Python\\UEFN_Toolbelt")


def test_deploy_toolbelt_files_copies_package_and_writes_shared_init(tmp_path: Path):
    _write_repo_config(tmp_path)
    _write_fake_toolbelt_vendor(tmp_path)
    destination_root = tmp_path / "Island" / "Content" / "Python"

    result = deploy_toolbelt_files(tmp_path, destination_root=destination_root)

    assert (destination_root / "UEFN_Toolbelt" / "__init__.py").exists()
    assert (destination_root / "uefn_toolbelt_init.py").exists()
    assert (destination_root / "init_unreal.py").exists()
    assert (tmp_path / "Island" / "tests" / "smoke_test.py").exists()
    assert result["shared_init_exists"] is True


def test_backend_summary_reports_toolbelt_status(tmp_path: Path):
    _write_repo_config(tmp_path)
    _write_fake_toolbelt_vendor(tmp_path)

    summary = backend_summary(tmp_path)

    assert summary["uefn_toolbelt"]["enabled"] is True
    assert summary["uefn_toolbelt"]["vendor_ready"] is True
    assert summary["paths"]["uefn_toolbelt_repo_path"].endswith("vendor\\uefn-toolbelt")


def test_toolbelt_source_inventory_reports_tools_and_workflows(tmp_path: Path):
    _write_repo_config(tmp_path)
    _write_fake_toolbelt_vendor(tmp_path)

    inventory = toolbelt_source_inventory(tmp_path)

    assert inventory["tool_count"] == 1
    assert inventory["category_count"] == 1
    assert inventory["workflow_count"] == 1
    assert inventory["files"]["smoke_test_exists"] is True


def test_toolbelt_status_summary_and_source_filters(tmp_path: Path):
    _write_repo_config(tmp_path)
    _write_fake_toolbelt_vendor(tmp_path)

    summary = toolbelt_status_summary(tmp_path)
    filtered = toolbelt_list_source_tools(tmp_path, category="Utilities", query="sample")

    assert summary["source_inventory"]["tool_count"] == 1
    assert summary["live_status"]["available"] is False
    assert filtered["tool_count"] == 1
    assert filtered["tools"][0]["name"] == "sample_tool"


def test_shared_init_script_bootstraps_mcp_and_toolbelt():
    payload = build_shared_init_script()

    assert "uefn_listener.py" in payload
    assert "uefn_toolbelt_init" in payload
    assert "_start_mcp_listener()" in payload
    assert "_bootstrap_toolbelt()" in payload
