"""Writable runtime paths.

Keeping generated files outside the package makes editable installs, packaged
applications and test runs behave consistently.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("NEOMAPPER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "NEOMapper"

    return Path.home() / ".neomapper"


def ensure_data_dir() -> Path:
    path = data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    return data_dir() / "NEOMapper_config.ini"


def output_dir() -> Path:
    path = ensure_data_dir() / "output"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = ensure_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def object_output_dir(designation: str, generated_on: date | None = None) -> Path:
    """Group products by sanitized designation and local generation date, YYYYMMDD."""
    from neomapper.shared.utils import safe_filename

    name = safe_filename(designation).strip(". ") or "object"
    # The date suffix also prevents bare Windows reserved device names.
    path = output_dir() / f"{name}-{(generated_on or date.today()):%Y%m%d}"
    path.mkdir(parents=True, exist_ok=True)
    return path
