"""File storage manager for the AI asset pipeline."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


class AssetStorage:
    """Manages the data/ai_assets/ directory structure."""

    def __init__(self, root: Path | str | None = None):
        if root is None:
            root = Path(__file__).resolve().parents[2] / "data" / "ai_assets"
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ── Directory structure ──────────────────────────────────────────

    def asset_dir(self, project: str, name: str) -> Path:
        d = self.root / project / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def source_dir(self, project: str, name: str) -> Path:
        d = self.asset_dir(project, name) / "source"
        d.mkdir(exist_ok=True)
        return d

    def export_dir(self, project: str, name: str) -> Path:
        d = self.asset_dir(project, name) / "exports"
        d.mkdir(exist_ok=True)
        return d

    def preview_dir(self, project: str, name: str) -> Path:
        d = self.asset_dir(project, name) / "previews"
        d.mkdir(exist_ok=True)
        return d

    def metadata_dir(self, project: str, name: str) -> Path:
        d = self.asset_dir(project, name) / "metadata"
        d.mkdir(exist_ok=True)
        return d

    def validation_dir(self, project: str, name: str) -> Path:
        d = self.asset_dir(project, name) / "validation"
        d.mkdir(exist_ok=True)
        return d

    # ── File operations ──────────────────────────────────────────────

    def save_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_json(self, path: Path) -> Any:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def load_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    # ── Convenience ──────────────────────────────────────────────────

    def save_spec(self, project: str, name: str, spec_dict: dict) -> Path:
        p = self.source_dir(project, name) / "prompt.json"
        self.save_json(p, spec_dict)
        return p

    def save_code(self, project: str, name: str, code: str, version: int) -> Path:
        p = self.source_dir(project, name) / f"v{version}_code.py"
        self.save_text(p, code)
        return p

    def save_record(self, project: str, name: str, record_dict: dict) -> Path:
        p = self.metadata_dir(project, name) / "record.json"
        self.save_json(p, record_dict)
        return p

    def load_record(self, project: str, name: str) -> dict | None:
        p = self.metadata_dir(project, name) / "record.json"
        return self.load_json(p)

    def save_validation(self, project: str, name: str, result_dict: dict, version: int) -> Path:
        p = self.validation_dir(project, name) / f"v{version}_result.json"
        self.save_json(p, result_dict)
        return p

    def glb_path(self, project: str, name: str, version: int) -> Path:
        return self.export_dir(project, name) / f"{name}_v{version}.glb"

    def list_projects(self) -> list[str]:
        if not self.root.exists():
            return []
        return [d.name for d in self.root.iterdir() if d.is_dir() and d.name != ".gitkeep"]

    def list_assets(self, project: str) -> list[str]:
        proj_dir = self.root / project
        if not proj_dir.exists():
            return []
        return [d.name for d in proj_dir.iterdir() if d.is_dir()]

    def delete_asset(self, project: str, name: str) -> bool:
        d = self.root / project / name
        if d.exists():
            shutil.rmtree(d)
            return True
        return False
