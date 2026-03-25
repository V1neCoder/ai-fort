from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

class ImageCache:
    def __init__(self, max_entries: int = 256) -> None:
        self._cache: OrderedDict[str, str] = OrderedDict()
        self.max_entries = max(1, int(max_entries))

    def put(self, key: str, value: str) -> None:
        normalized_key = str(key)
        normalized_value = str(Path(value))
        if normalized_key in self._cache:
            self._cache.pop(normalized_key, None)
        self._cache[normalized_key] = normalized_value
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)

    def get(self, key: str) -> str | None:
        normalized_key = str(key)
        value = self._cache.get(normalized_key)
        if value is None:
            return None
        if not Path(value).exists():
            self._cache.pop(normalized_key, None)
            return None
        self._cache.move_to_end(normalized_key)
        return value

    def invalidate_prefix(self, prefix: str) -> int:
        normalized_prefix = str(prefix)
        removed = 0
        for key in list(self._cache.keys()):
            if key.startswith(normalized_prefix):
                self._cache.pop(key, None)
                removed += 1
        return removed

    def clear(self) -> None:
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)
