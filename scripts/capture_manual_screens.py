"""Capture deterministic screens from the current NEOMapper 4.2 interface."""
from __future__ import annotations

import os
import sys
import argparse
from pathlib import Path
from astropy.time import Time
from PySide6.QtWidgets import QApplication

from neomapper.domain.object_summary import ObjectSummary, SummarySample, SummaryTarget
from neomapper.infrastructure.favorites import JsonFavoritesRepository
from neomapper.presentation.favorites import FavoritesDialog
from neomapper.presentation.gui import NEOMapperMainWindow
from neomapper.presentation.object_summary import ObjectSummaryWidget


def save_grab(widget, path: Path) -> None:
    widget.show()
    QApplication.processEvents()
    if not widget.grab().save(str(path)):
        raise RuntimeError(f"Could not save {path.name}")
    widget.hide()


def fixture_summary() -> ObjectSummary:
    selected_time = Time("2026-09-10T00:00:00", scale="utc")
    perihelion_time = Time("2029-11-14T12:00:00", scale="utc")
    approach_time = Time("2029-04-13T21:46:00", scale="utc")

    def row(instant: Time, radius: float, delta: float, magnitude: float) -> SummarySample:
        return SummarySample(instant, radius, delta, 206.1, -8.3, magnitude, "V", 74.2, 58.1, None)

    target = SummaryTarget("99942 Apophis", "2099942", False, perihelion_time, 323.6)
    return ObjectSummary(
        target,
        row(perihelion_time, .746, .855, 19.1),
        row(selected_time, 1.10, .82, 18.4),
        row(approach_time, 1.00, .000254, 3.1),
        selected_time - 365,
        selected_time + 365,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=("PT", "EN", "ES"), default="PT")
    args = parser.parse_args()
    language = args.language
    repository = Path(__file__).resolve().parents[1]
    destination = repository / "docs" / "manual_assets" / language.lower()
    destination.mkdir(parents=True, exist_ok=True)
    local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    object_dir = local_appdata / "NEOMapper" / "output" / "99942-20260910"
    visibility_map = object_dir / "99942_visibility_20260910_000000.png"
    sky_map = object_dir / "99942_sky_20260910_000000.png"
    altitude_map = object_dir / "99942_altitude_20260910_030000.png"
    solar_map = object_dir / "solar_system_sketch.png"

    app = QApplication.instance() or QApplication(sys.argv)
    window = NEOMapperMainWindow()
    window.resize(1500, 900)
    window.language_header_combo.setCurrentText(language)
    window.object_edit.setText("99942")
    window.summary_object.setText("99942 Apophis")
    window.object_sun_distance.setText("164.557.657 km")
    window.object_earth_distance.setText("122.670.253 km")
    window.object_magnitude.setText("18,4 V")
    window._object_validated = True
    window._update_object_actions()

    captures = [
        (1, "01_object.png", solar_map),
        (0, "02_obs_information.png", altitude_map),
        (3, "03_layers.png", sky_map),
        (4, "04_animation.png", sky_map),
        (5, "05_settings.png", visibility_map),
        (6, "06_about.png", visibility_map),
    ]
    for page, filename, preview in captures:
        window._activate_workflow_page(page)
        if preview.is_file():
            window.show_png(preview)
        if page == 0:
            window.orbital_summary.set_summary(fixture_summary(), "UTC", -19.9, -43.9)
            window.altitude_details.show()
        window.show()
        app.processEvents()
        if not window.grab().save(str(destination / filename)):
            raise RuntimeError(f"Could not save {filename}")

    favorites = FavoritesDialog(JsonFavoritesRepository(), "99942", language, window)
    favorites.resize(650, 560)
    save_grab(favorites, destination / "07_favorites.png")

    summary = ObjectSummaryWidget()
    summary.resize(1350, 340)
    summary.set_language(language)
    summary.set_distance_unit("UA")
    summary.set_summary(fixture_summary(), "UTC", -19.9, -43.9)
    save_grab(summary, destination / "08_orbital_summary.png")

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
