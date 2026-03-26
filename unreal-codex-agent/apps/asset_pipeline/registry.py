"""Asset registry — lifecycle tracking and shortlist sync."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import AssetRecord, AssetSpec, ValidationResult
from .storage import AssetStorage


class AssetRegistry:
    """Manages the master registry and syncs to the app's shortlist."""

    def __init__(self, storage: AssetStorage | None = None):
        self.storage = storage or AssetStorage()
        self._registry_path = self.storage.root / "registry.json"
        self._records: dict[str, dict[str, Any]] = {}
        self._load()

    # ── Persistence ──────────────────────────────────────────────────

    def _load(self) -> None:
        if self._registry_path.exists():
            with open(self._registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._records = {r["asset_id"]: r for r in data.get("assets", [])}
        else:
            self._records = {}

    def _save(self) -> None:
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._registry_path, "w", encoding="utf-8") as f:
            json.dump({"assets": list(self._records.values())}, f, indent=2, ensure_ascii=False)

    # ── CRUD ─────────────────────────────────────────────────────────

    def create(self, spec: AssetSpec, project: str = "default") -> AssetRecord:
        """Create a new asset record from a spec."""
        name = self._sanitize_name(spec.asset_name or spec.prompt)
        # Ensure uniqueness
        base_name = name
        counter = 1
        while any(r.get("name") == name and r.get("project") == project for r in self._records.values()):
            counter += 1
            name = f"{base_name}_{counter:03d}"

        record = AssetRecord(
            name=name,
            category=spec.category,
            project=project,
            prompt=spec.prompt,
            spec=spec,
            status="pending",
            generation_provider="",
        )

        # Save to storage
        self.storage.save_spec(project, name, spec.to_dict())
        self.storage.save_record(project, name, record.to_dict())

        # Add to registry
        self._records[record.asset_id] = record.to_dict()
        self._save()

        return record

    def get(self, asset_id: str) -> AssetRecord | None:
        data = self._records.get(asset_id)
        if data is None:
            return None
        return AssetRecord.from_dict(dict(data))

    def update(self, record: AssetRecord) -> None:
        """Save an updated record."""
        record.touch()
        record_dict = record.to_dict()
        self._records[record.asset_id] = record_dict
        self.storage.save_record(record.project, record.name, record_dict)
        self._save()

    def delete(self, asset_id: str) -> bool:
        data = self._records.pop(asset_id, None)
        if data is None:
            return False
        self.storage.delete_asset(data["project"], data["name"])
        self._save()
        return True

    def list_all(self, project: str | None = None) -> list[AssetRecord]:
        records = []
        for data in self._records.values():
            if project and data.get("project") != project:
                continue
            records.append(AssetRecord.from_dict(dict(data)))
        records.sort(key=lambda r: r.updated_at, reverse=True)
        return records

    # ── Lifecycle updates ────────────────────────────────────────────

    def update_status(self, record: AssetRecord, status: str) -> AssetRecord:
        record.status = status
        self.update(record)
        return record

    def update_generation(self, record: AssetRecord, glb_path: str, code: str,
                          provider: str, vertex_count: int = 0, face_count: int = 0,
                          bounds: dict | None = None) -> AssetRecord:
        record.glb_path = glb_path
        record.generated_code = code
        record.generation_provider = provider
        record.vertex_count = vertex_count
        record.face_count = face_count
        record.bounds_cm = bounds or {}
        record.status = "preview_ready"
        self.storage.save_code(record.project, record.name, code, record.version)
        self.update(record)
        return record

    def update_previews(self, record: AssetRecord, screenshot_names: list[str]) -> AssetRecord:
        record.preview_screenshots = screenshot_names
        self.update(record)
        return record

    def update_validation(self, record: AssetRecord, result: ValidationResult) -> AssetRecord:
        result_dict = result.to_dict()
        record.validation_results.append(result_dict)
        record.latest_validation = result_dict
        record.status = "approved" if result.passed else "needs_correction"
        self.update(record)
        self.storage.save_validation(record.project, record.name, result_dict, record.version)
        return record

    def add_fix(self, record: AssetRecord, fix_entry: dict) -> AssetRecord:
        record.fix_history.append(fix_entry)
        record.version += 1
        self.update(record)
        return record

    def mark_imported(self, record: AssetRecord, uefn_path: str) -> AssetRecord:
        from .models import _now_iso
        record.uefn_import_path = uefn_path
        record.imported_at = _now_iso()
        record.status = "imported"
        self.update(record)
        return record

    # ── Shortlist sync ───────────────────────────────────────────────

    def sync_to_shortlist(self, record: AssetRecord | None = None, base_url: str = "") -> None:
        """Sync approved/imported assets to data/catalog/shortlist.json for the AssetBrowser."""
        shortlist_path = self.storage.root.parent / "catalog" / "shortlist.json"
        shortlist_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing shortlist
        existing: list[dict[str, Any]] = []
        if shortlist_path.exists():
            with open(shortlist_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        # Remove old pipeline entries
        existing = [a for a in existing if not a.get("pipeline_asset")]

        # Add all approved/imported pipeline assets
        for data in self._records.values():
            if data.get("status") in ("approved", "imported"):
                rec = AssetRecord.from_dict(dict(data))
                existing.append(rec.to_shortlist_entry(base_url))

        with open(shortlist_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_name(text: str) -> str:
        """Convert prompt text to a valid asset name."""
        # Take first meaningful words
        text = text.lower().strip()
        # Remove common prefixes
        for prefix in ("create ", "make ", "generate ", "build ", "a ", "an ", "the "):
            if text.startswith(prefix):
                text = text[len(prefix):]
        # Clean
        name = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
        # Limit length
        parts = name.split("_")[:5]
        return "_".join(parts) or "asset"
