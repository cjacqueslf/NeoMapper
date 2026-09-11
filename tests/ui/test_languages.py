"""Language coverage for registered UI text and live figure relabeling."""
import ast
import os
from pathlib import Path
from string import Formatter
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from matplotlib import pyplot as plt
from PySide6.QtWidgets import QApplication

from neomapper.presentation import gui, mapplot
from neomapper.presentation.i18n import LOCALES_DIR, Translator, load_catalog


def test_catalogs_cover_source_keys_and_preserve_format_fields() -> None:
    catalogs = [load_catalog(code) for code in ("EN", "PT", "ES")]
    keys = set(catalogs[0])
    for catalog in catalogs:
        assert set(catalog) == keys
        for key, value in catalog.items():
            assert value.strip(), key
            def fields(text: str) -> set[str]:
                return {field for _, field, _, _ in Formatter().parse(text) if field is not None}
            assert fields(catalogs[0][key]) == fields(value), key
            assert "\ufffd" not in value
    for path in LOCALES_DIR.parent.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
                if any(isinstance(target, ast.Name) and target.id == "keys" for target in node.targets):
                    for item in node.value.elts:
                        if isinstance(item, ast.Constant) and isinstance(item.value, str):
                            assert item.value in keys, (path.name, item.value)
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                if name not in {"tr", "create_section_label", "create_metric_card", "create_line_field", "create_combo_field", "create_check", "create_datetime_field"}:
                    continue
                index = 0 if name in {"tr", "create_section_label"} else 1
                if len(node.args) > index and isinstance(node.args[index], ast.Constant):
                    key = node.args[index].value
                    if isinstance(key, str):
                        assert key in keys, (path.name, key)


def test_all_registered_labels_and_controls_switch_languages(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": str(tmp_path)}):
        window = gui.NEOMapperMainWindow()
        try:
            for lang, sun, earth, version in (
                ("ES", "Distancia al Sol", "Distancia a la Tierra", "Versión"),
                ("EN", "Distance to Sun", "Distance to Earth", "Version"),
                ("PT", "Distância ao Sol", "Distância à Terra", "Versão"),
            ):
                window.language_header_combo.setCurrentText(lang)
                tr = Translator(lang).tr
                assert window.tr_widgets["Distance to Sun"].text() == sun
                assert window.tr_widgets["Distance to Earth"].text() == earth
                assert window.tr_widgets["Version"].text() == version
                for key, widget in window.tr_widgets.items():
                    assert key in load_catalog(lang), key
                    if key == "Date / Time UTC":
                        key = "Date / Time " + window.time_mode_combo.currentText()
                    assert widget.text() == tr(key), key
                assert window.player_play_btn.text() == tr("Play")
                assert window.anim_progress_label.text() == tr("Ready")
                assert window.anim_playback_combo.itemText(4) == tr("Very Fast (25 fps)")
                assert window.anim_format_combo.itemText(3) == tr("Frames PNG")
                window.site_preset_combo.setCurrentIndex(window.site_preset_combo.count() - 1)
                assert window.site_preset_combo.currentData() == "Custom"
                assert window.site_preset_combo.currentText() == tr("Custom")
                window.right_stack.setCurrentIndex(4)
                window._update_preview_hint()
                assert window.preview_label.text() == tr("Click Generate Animation to preview the animation.")
        finally:
            window.close()


def test_solar_system_switches_labels_without_recalculating_orbits(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    orbit = (np.array([1., 0., 0.]), np.array([[1., 0., 0.], [0., 1., 0.]]))
    with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": str(tmp_path)}), patch.object(mapplot, "planet_orbit", return_value=orbit) as calculate:
        window = gui.NEOMapperMainWindow()
        path = tmp_path / "solar.png"
        fig = mapplot.build_solar_system_sketch("Fixture", 31., str(path), obstime="2026-09-10", language="PT")
        before = [line.get_xydata().copy() for line in fig.axes[0].lines]
        count = calculate.call_count
        try:
            window._distance_preview = (fig, path)
            window.show_png(path)
            for lang, earth, mercury in (("ES", "Tierra", "Mercurio"), ("EN", "Earth", "Mercury"), ("PT", "Terra", "Mercúrio")):
                window.language_header_combo.setCurrentText(lang)
                labels = {artist.get_text() for artist in fig.axes[0].texts}
                assert {earth, mercury, Translator(lang).tr("Neptune")} <= labels
                assert Translator(lang).tr("Solar System") in fig.axes[0].get_title()
                assert calculate.call_count == count
                for line, original in zip(fig.axes[0].lines, before):
                    np.testing.assert_array_equal(line.get_xydata(), original)
        finally:
            plt.close(fig)
            window.close()
