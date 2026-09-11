"""Atomic, user-local persistence for favorite objects."""
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from neomapper.application.favorites import Favorite
from neomapper.infrastructure.paths import data_dir


class JsonFavoritesRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else data_dir() / "favorites.json"

    def load(self) -> list[Favorite]:
        if not self.path.exists():
            return []
        values = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(values, list):
            raise ValueError("Invalid favorites file")
        result: list[Favorite] = []
        for value in values:
            if not isinstance(value, dict) or any(not isinstance(value.get(key), str) for key in ("designation", "name", "notes")) or not value["designation"].strip():
                raise ValueError("Invalid favorite entry")
            result.append(Favorite(value["designation"], value["name"], value["notes"]))
        return result

    def save(self, favorites: list[Favorite]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as stream:
                temporary = stream.name
                json.dump([asdict(item) for item in favorites], stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
