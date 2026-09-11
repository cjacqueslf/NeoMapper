"""User annotations for objects; independent of ephemeris queries."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Favorite:
    designation: str
    name: str
    notes: str = ""


class FavoritesRepository(Protocol):
    def load(self) -> list[Favorite]: ...

    def save(self, favorites: list[Favorite]) -> None: ...
