from __future__ import annotations

import json
from typing import Any

from ue_runtime import load_unreal

unreal = load_unreal(("EditorLevelLibrary",))


DEFAULT_PREFIX = "UCA_ValidationActor"


def _ensure_unreal() -> None:
    if unreal is None:
        raise RuntimeError("Unreal Python API is not available in this environment.")


def cleanup_validation_actors(label_prefix: str = DEFAULT_PREFIX) -> dict[str, Any]:
    _ensure_unreal()
    removed: list[str] = []
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception as exc:
        return {"status": "error", "reason": str(exc), "removed": removed}
    for actor in actors:
        try:
            label = actor.get_actor_label()
        except Exception:
            label = ""
        if not str(label).startswith(label_prefix):
            continue
        try:
            removed.append(str(label))
            unreal.EditorLevelLibrary.destroy_actor(actor)
        except Exception:
            pass
    return {"status": "ok", "removed": removed, "count": len(removed)}


if __name__ == "__main__":
    try:
        result = cleanup_validation_actors()
    except Exception as exc:
        result = {"status": "error", "reason": str(exc), "removed": []}
    print(json.dumps(result, indent=2))
