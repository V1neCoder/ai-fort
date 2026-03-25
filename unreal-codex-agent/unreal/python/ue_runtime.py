from __future__ import annotations

from typing import Any


def load_unreal(required_attrs: tuple[str, ...] = ()) -> Any | None:
    try:
        import unreal as unreal_module  # type: ignore
    except Exception:
        return None

    if not all(hasattr(unreal_module, attr) for attr in required_attrs):
        return None
    return unreal_module
