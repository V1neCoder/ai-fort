from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import typer

from apps.asset_ai.query_catalog import query_rows
from apps.asset_ai.shortlist import shortlist_assets
from apps.capture_service.capture_manager import CaptureManager
from apps.capture_service.scene_packet import build_scene_packet
from apps.codex_bridge.codex_session import CodexSession
from apps.integrations.prefabricator import prefabricator_settings, should_prefer_prefabs
from apps.integrations.uefn_backend import (
    choose_action_backend,
    choose_capture_backend,
    choose_scene_backend,
)
from apps.integrations.uefn_mcp import apply_action_via_mcp, resolve_existing_asset_path
from apps.placement.placement_solver import normalize_action_payload
from apps.mcp_extensions.scene_tools import load_scene_state_for_context
from apps.orchestrator.cycle_runner import (
    CycleContext,
    CycleRunner,
)
from apps.orchestrator.dirty_zone import DirtyZone
from apps.orchestrator.session_manager import SessionManager
from apps.orchestrator.state_store import SessionStateStore
from apps.uefn.verse_export import apply_action_via_verse_export
from apps.validation.run_validators import LocalValidator

app = typer.Typer(help="UEFN Codex Agent orchestrator CLI.")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _repo_paths(repo_root: Path) -> dict[str, Path]:
    config_dir = repo_root / "config"
    return {
        "repo_root": repo_root,
        "config_dir": config_dir,
        "project": config_dir / "project.json",
        "validator_rules": config_dir / "validator_rules.json",
    }


def _load_config(repo_root: Path) -> dict[str, Any]:
    paths = _repo_paths(repo_root)
    project = _load_json(paths["project"])
    validator_rules = _load_json(paths["validator_rules"])
    project.setdefault("orchestrator", {})
    project.setdefault("asset_ai", {})
    project.setdefault("paths", {})
    project["orchestrator"].setdefault("session_name", "default_session")
    validator_rules.setdefault("completion_gate", {})
    validator_rules.setdefault("validators", {})
    return {
        "project": project,
        "validator_rules": validator_rules,
        "paths": paths,
    }


class LocalSceneStateProvider:
    def get_scene_state(self, context: CycleContext) -> dict[str, Any]:
        return load_scene_state_for_context(context.repo_root)


class CaptureServiceAdapter:
    def __init__(self, repo_root: Path) -> None:
        self.manager = CaptureManager(repo_root=repo_root)

    def build_capture_packet(self, context: CycleContext, dirty_zone: DirtyZone) -> dict[str, Any]:
        packet = self.manager.build_capture_packet(context=context, dirty_zone=dirty_zone)
        packet.setdefault("notes", [])
        packet["notes"] = list(packet["notes"]) + [
            f"capture_backend_selected={packet.get('capture_backend', 'placeholder')}",
            f"capture_backend_preferred={choose_capture_backend(context.repo_root)}",
            f"action_backend_preferred={choose_action_backend(context.repo_root)}",
        ]
        return packet


class CodexBridgeAdapter:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.session = CodexSession(repo_root=repo_root)

    @staticmethod
    def _write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
                handle.write(json.dumps(payload, indent=2))
                temp_path = Path(handle.name)
            temp_path.replace(path)
        finally:
            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def _shortlist_for_zone(self, context: CycleContext, dirty_zone: DirtyZone, scene_state: dict[str, Any]) -> list[dict[str, Any]]:
        project = context.project_config
        paths_cfg = project.get("paths", {})
        catalog_db = self.repo_root / paths_cfg.get("catalog_db", "data/catalog/asset_catalog.sqlite")
        expected_mount_type = scene_state.get("expected_mount_type")
        prefab_settings = prefabricator_settings(project)
        prefer_structural_prefabs = should_prefer_prefabs(project, expected_mount_type)

        try:
            records = query_rows(
                catalog_db=catalog_db,
                room_type=dirty_zone.room_type if dirty_zone.room_type != "unknown" else None,
                mount_type=expected_mount_type if expected_mount_type not in {None, "unknown"} else None,
                min_trust_score=int(project.get("asset_ai", {}).get("min_trust_for_shortlist", 70)),
                status="approved",
                limit=50,
            )
        except Exception:
            records = []
        try:
            shortlist = shortlist_assets(
                catalog=records,
                room_type=dirty_zone.room_type if dirty_zone.room_type != "unknown" else None,
                function_name=None,
                mount_type=expected_mount_type if expected_mount_type not in {None, "unknown"} else None,
                style=None,
                min_trust="high" if int(project.get("asset_ai", {}).get("min_trust_for_shortlist", 70)) >= 85 else "medium",
                room_dimensions=None,
                limit=10,
                prefer_structural_prefabs=prefer_structural_prefabs,
            )
        except Exception:
            shortlist = []

        shortlist = self._filter_live_assets(shortlist, context=context)
        if not shortlist and choose_action_backend(context.repo_root) == "uefn_mcp_apply":
            shortlist = self._fallback_live_shortlist(scene_state=scene_state, dirty_zone=dirty_zone)

        cache_dir = context.repo_root / "data" / "cache" / "latest_shortlists"
        cache_dir.mkdir(parents=True, exist_ok=True)
        shortlist_payload = {
            "zone_key": dirty_zone.zone_id,
            "room_type": dirty_zone.room_type,
            "function_name": None,
            "style": None,
            "expected_mount_type": expected_mount_type,
            "prefer_structural_prefabs": prefer_structural_prefabs,
            "preferred_prefab_mount_types": prefab_settings.get("prefer_prefabs_for_mount_types", []),
            "min_trust": "high" if int(project.get("asset_ai", {}).get("min_trust_for_shortlist", 70)) >= 85 else "medium",
            "generated_at_utc": SessionStateStore.utcnow_static(),
            "results": [
                {
                    "asset_id": row.get("asset_id"),
                    "asset_path": row.get("asset_path"),
                    "trust_score": row.get("trust_score"),
                    "placement_rank": row.get("placement_rank"),
                    "is_prefab": bool((row.get("tags", {}) or {}).get("is_prefab", False)),
                    "prefab_family": (row.get("tags", {}) or {}).get("prefab_family"),
                }
                for row in shortlist
            ],
        }
        self._write_atomic_json(cache_dir / f"{dirty_zone.zone_id}.json", shortlist_payload)
        if dirty_zone.room_type and dirty_zone.room_type != "unknown":
            self._write_atomic_json(cache_dir / f"{dirty_zone.room_type}.json", shortlist_payload)
        return shortlist

    def _filter_live_assets(self, shortlist: list[dict[str, Any]], *, context: CycleContext) -> list[dict[str, Any]]:
        if choose_action_backend(context.repo_root) != "uefn_mcp_apply":
            return shortlist
        filtered: list[dict[str, Any]] = []
        for row in shortlist:
            resolution = resolve_existing_asset_path(self.repo_root, str(row.get("asset_path") or ""))
            resolved_path = str(resolution.get("asset_path") or "").strip()
            if not resolved_path:
                continue
            updated = dict(row)
            updated["asset_path"] = resolved_path
            updated["uefn_live_asset"] = True
            filtered.append(updated)
        return filtered

    @staticmethod
    def _live_scene_asset_score(actor: dict[str, Any]) -> int:
        text = " ".join(
            str(actor.get(key) or "")
            for key in ("label", "actor_name", "class_name", "asset_path")
        ).lower()
        score = 0
        if any(token in text for token in ("gridplane", "landscape", "terrain", "world", "levelbounds", "islandsettings")):
            score -= 100
        if any(token in text for token in ("spawn pad", "spawner", "player spawn", "beacon", "creative", "prop")):
            score += 18
        if str(actor.get("asset_path") or "").strip():
            score += 10
        if bool(actor.get("selected", False)):
            score -= 8
        return score

    def _fallback_live_shortlist(self, *, scene_state: dict[str, Any], dirty_zone: DirtyZone) -> list[dict[str, Any]]:
        actors = [actor for actor in list(scene_state.get("actors") or []) if isinstance(actor, dict)]
        ranked = sorted(actors, key=self._live_scene_asset_score, reverse=True)
        expected_mount_type = str(scene_state.get("expected_mount_type") or "floor")
        fallback: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for actor in ranked:
            asset_path = str(actor.get("asset_path") or "").strip()
            if not asset_path or asset_path in seen_paths:
                continue
            if self._live_scene_asset_score(actor) <= 0:
                continue
            resolved = resolve_existing_asset_path(self.repo_root, asset_path)
            resolved_path = str(resolved.get("asset_path") or "").strip()
            if not resolved_path:
                continue
            seen_paths.add(asset_path)
            asset_name = resolved_path.rsplit("/", 1)[-1].split(".")[-1] or str(actor.get("label") or "LiveAsset")
            fallback.append(
                {
                    "asset_id": asset_name,
                    "asset_name": asset_name,
                    "asset_path": resolved_path,
                    "status": "approved",
                    "trust_score": 60,
                    "trust_level": "medium",
                    "placement_rank": round(max(0.4, 0.65 - (len(fallback) * 0.05)), 3),
                    "tags": {
                        "category": "live_scene_asset",
                        "function": ["utility"],
                        "room_types": [dirty_zone.room_type],
                        "styles": [],
                        "mount_type": expected_mount_type,
                        "scale_policy": "tight",
                        "placement_behavior": ["derived_from_live_scene"],
                    },
                    "scale_limits": {"min": 1.0, "max": 1.0, "preferred": 1.0},
                    "uefn_live_asset": True,
                }
            )
            if len(fallback) >= 5:
                break
        return fallback

    def _cache_scene_packet(
        self,
        *,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        capture_packet: dict[str, Any],
        shortlist: list[dict[str, Any]],
    ) -> None:
        cache_dir = context.repo_root / "data" / "cache" / "latest_scene_packets"
        cache_dir.mkdir(parents=True, exist_ok=True)
        scene_packet = build_scene_packet(
            build_goal=context.build_goal,
            scene_state=scene_state,
            dirty_zone=dirty_zone.to_dict(),
            capture_packet=capture_packet,
            shortlist=shortlist,
        )
        payload = dict(scene_packet)
        payload["generated_at_utc"] = SessionStateStore.utcnow_static()
        payload["expected_mount_type"] = scene_state.get("expected_mount_type")
        payload["placement_context"] = scene_state.get("placement_context")
        payload["prefabricator"] = {
            "enabled": bool(prefabricator_settings(context.project_config).get("enabled", False)),
            "prefer_structural_prefabs": should_prefer_prefabs(context.project_config, scene_state.get("expected_mount_type")),
            "preferred_prefab_mount_types": prefabricator_settings(context.project_config).get("prefer_prefabs_for_mount_types", []),
        }
        try:
            payload["scene_backend"] = choose_scene_backend(context.repo_root)
        except Exception:
            payload["scene_backend"] = "fallback"
        try:
            payload["capture_backend"] = choose_capture_backend(context.repo_root)
        except Exception:
            payload["capture_backend"] = "placeholder"
        try:
            payload["action_backend"] = choose_action_backend(context.repo_root)
        except Exception:
            payload["action_backend"] = "plan_only"
        self._write_atomic_json(cache_dir / f"{dirty_zone.zone_id}.json", payload)

    def choose_action(
        self,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        capture_packet: dict[str, Any],
    ) -> dict[str, Any]:
        shortlist = self._shortlist_for_zone(context, dirty_zone, scene_state)
        self._cache_scene_packet(
            context=context,
            scene_state=scene_state,
            dirty_zone=dirty_zone,
            capture_packet=capture_packet,
            shortlist=shortlist,
        )
        raw_action = self.session.choose_action(
            build_goal=context.build_goal,
            scene_state=scene_state,
            dirty_zone=dirty_zone,
            capture_packet=capture_packet,
            shortlist=shortlist,
        )
        asset_record = None
        selected_asset_path = raw_action.get("asset_path")
        if selected_asset_path:
            asset_record = next((row for row in shortlist if row.get("asset_path") == selected_asset_path), None)
        normalized = normalize_action_payload(
            action_payload=raw_action,
            scene_state=scene_state,
            dirty_zone=dirty_zone.to_dict(),
            asset_record=asset_record,
        )
        if asset_record is not None:
            normalized["asset_record"] = asset_record
        return normalized

    def review_edit(
        self,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        capture_packet: dict[str, Any],
        action: Any,
        validation_report: dict[str, Any],
    ) -> dict[str, Any]:
        return self.session.review_edit(
            build_goal=context.build_goal,
            scene_state=scene_state,
            dirty_zone=dirty_zone,
            capture_packet=capture_packet,
            action=action,
            validation_report=validation_report,
        )


class ActionExecutorAdapter:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    @staticmethod
    def _next_cycle_number(context: CycleContext) -> int:
        session_payload = _load_json(context.session_path / "session.json")
        return int(session_payload.get("last_cycle_number") or 0) + 1

    def execute_action(
        self,
        context: CycleContext,
        scene_state: dict[str, Any],
        dirty_zone: DirtyZone,
        action: Any,
    ) -> dict[str, Any]:
        del scene_state, dirty_zone
        backend = choose_action_backend(context.repo_root)
        if backend == "uefn_mcp_apply":
            auto_save = bool((context.project_config.get("verse") or {}).get("auto_save_after_apply", False))
            try:
                result = apply_action_via_mcp(
                    context.repo_root,
                    action.to_dict() if hasattr(action, "to_dict") else dict(action or {}),
                    session_path=context.session_path,
                    cycle_number=self._next_cycle_number(context),
                    auto_save=auto_save,
                )
            except Exception as exc:  # noqa: BLE001
                result = {
                    "status": "error",
                    "backend": "uefn_mcp_apply",
                    "applied_mode": "uefn_mcp_apply",
                    "degraded_to_fallback": False,
                    "applied": False,
                    "reason": str(exc),
                }
            result["backend_selected"] = backend
            return result
        if backend == "uefn_verse_apply":
            result = apply_action_via_verse_export(
                repo_root=context.repo_root,
                session_path=context.session_path,
                cycle_number=self._next_cycle_number(context),
                scene_state=scene_state,
                dirty_zone=dirty_zone.to_dict(),
                action_payload=action.to_dict() if hasattr(action, "to_dict") else dict(action or {}),
            )
            result["backend_selected"] = backend
            return result
        return {
            "status": "skipped",
            "backend": backend,
            "backend_selected": backend,
            "applied": False,
            "reason": "No live action backend is enabled.",
        }


def _build_runner(repo_root: Path, state_store: SessionStateStore) -> CycleRunner:
    return CycleRunner(
        state_store=state_store,
        scene_state_provider=LocalSceneStateProvider(),
        capture_service=CaptureServiceAdapter(repo_root=repo_root),
        codex_bridge=CodexBridgeAdapter(repo_root=repo_root),
        validator=LocalValidator(repo_root=repo_root),
        action_executor=ActionExecutorAdapter(repo_root=repo_root),
    )


@app.command()
def create_session(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    goal: str = typer.Option("default build goal", help="Initial build goal."),
    session_name: str | None = typer.Option(None, help="Optional explicit session name."),
) -> None:
    config = _load_config(repo_root)
    project = config["project"]

    state_store = SessionStateStore(repo_root=repo_root)
    manager = SessionManager(
        session_root=repo_root / "data" / "sessions",
        state_store=state_store,
    )

    session = manager.create_session(
        goal=goal,
        requested_name=session_name or project["orchestrator"]["session_name"],
    )

    typer.echo(f"Created session: {session.session_id}")
    typer.echo(f"Session path: {session.session_path}")


@app.command()
def start(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    goal: str = typer.Option("Build a polished room that fits the task.", help="Build goal."),
    cycles: int = typer.Option(1, help="How many cycles to run."),
    session_name: str | None = typer.Option(None, help="Optional explicit session name."),
) -> None:
    config = _load_config(repo_root)
    project = config["project"]
    validator_rules = config["validator_rules"]

    state_store = SessionStateStore(repo_root=repo_root)
    manager = SessionManager(
        session_root=repo_root / "data" / "sessions",
        state_store=state_store,
    )

    session = manager.create_session(
        goal=goal,
        requested_name=session_name or project["orchestrator"]["session_name"],
    )

    context = CycleContext(
        repo_root=repo_root,
        session_id=session.session_id,
        session_path=session.session_path,
        build_goal=goal,
        project_config=project,
        validator_rules=validator_rules,
    )

    runner = _build_runner(repo_root=repo_root, state_store=state_store)

    typer.echo(f"Starting session: {session.session_id}")
    typer.echo(f"Goal: {goal}")

    for cycle_index in range(1, cycles + 1):
        result = runner.run_once(context=context, cycle_number=cycle_index)
        typer.echo(
            f"[cycle {cycle_index}] "
            f"decision={result['review_decision']} "
            f"score={result['score']['overall_score']} "
            f"completion={result['completion']['decision']}"
        )

    typer.echo("Done.")


@app.command()
def run_once(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    session_id: str = typer.Option(..., help="Existing session id."),
    goal: str | None = typer.Option(None, help="Optional goal override."),
) -> None:
    config = _load_config(repo_root)
    project = config["project"]
    validator_rules = config["validator_rules"]

    state_store = SessionStateStore(repo_root=repo_root)
    manager = SessionManager(
        session_root=repo_root / "data" / "sessions",
        state_store=state_store,
    )

    session = manager.get_session(session_id)
    if session is None:
        raise typer.BadParameter(f"Unknown session_id: {session_id}")

    context = CycleContext(
        repo_root=repo_root,
        session_id=session.session_id,
        session_path=session.session_path,
        build_goal=goal or session.goal,
        project_config=project,
        validator_rules=validator_rules,
    )

    runner = _build_runner(repo_root=repo_root, state_store=state_store)

    result = runner.run_once(context=context, cycle_number=session.last_cycle_number + 1)

    typer.echo(
        f"Ran cycle {result['cycle_number']} for session {session.session_id}: "
        f"decision={result['review_decision']} "
        f"completion={result['completion']['decision']}"
    )


@app.command()
def status(
    repo_root: Path = typer.Option(Path("."), help="Repo root path."),
    session_id: str = typer.Option(..., help="Session id."),
) -> None:
    state_store = SessionStateStore(repo_root=repo_root)
    manager = SessionManager(
        session_root=repo_root / "data" / "sessions",
        state_store=state_store,
    )
    session = manager.get_session(session_id)
    if session is None:
        raise typer.BadParameter(f"Unknown session_id: {session_id}")

    completion_state = state_store.load_completion_state(session.session_path)
    typer.echo(f"session_id: {session.session_id}")
    typer.echo(f"goal: {session.goal}")
    typer.echo(f"last_cycle_number: {session.last_cycle_number}")
    typer.echo(f"session_path: {session.session_path}")
    typer.echo(f"completion_state: {json.dumps(completion_state, indent=2)}")


if __name__ == "__main__":
    app()
