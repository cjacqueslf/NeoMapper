"""Regression checks for favorites, summary export and contextual help."""
import csv
import json
import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from astropy.time import Time
from PySide6.QtWidgets import QApplication
from PySide6.QtPdf import QPdfDocument

from neomapper.application.favorites import Favorite
from neomapper.domain.object_summary import ObjectSummary, SummarySample, SummaryTarget
from neomapper.infrastructure.favorites import JsonFavoritesRepository
from neomapper.presentation import gui
from neomapper.presentation.context_help import HELP_TOPICS, help_text
from neomapper.presentation.favorites import FavoritesDialog
from neomapper.presentation.i18n import load_catalog
from neomapper.presentation.object_summary import ObjectSummaryWidget
from neomapper.presentation.summary_export import export_summary


def test_favorites_round_trip_unicode_and_atomic_failure(tmp_path: Path) -> None:
    repo = JsonFavoritesRepository(tmp_path / "favorites.json")
    assert repo.load() == []
    original = [Favorite("220P", "Cometa favorito", "Órbita / 50% / España")]
    repo.save(original)
    assert repo.load() == original
    with patch("neomapper.infrastructure.favorites.os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            repo.save([])
    assert repo.load() == original
    assert list(tmp_path.iterdir()) == [repo.path]
    repo.path.write_text("broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        repo.load()
    assert repo.path.read_text(encoding="utf-8") == "broken"


def test_favorites_save_update_select_and_remove(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    repo = JsonFavoritesRepository(tmp_path / "favorites.json")
    dialog = FavoritesDialog(repo, "220P", "PT")
    try:
        dialog.name.setText("McNaught")
        dialog.notes.setPlainText("Observar antes do amanhecer")
        dialog.save_button.click()
        dialog.designation.setText("220p")
        dialog.notes.setPlainText("Nova nota")
        dialog.save_button.click()
        assert len(repo.load()) == 1
        assert repo.load()[0].notes == "Nova nota"
        dialog.use_button.click()
        assert dialog.selected_designation == "220p"
        dialog.remove_button.click()
        assert repo.load() == []
    finally:
        dialog.close()


def test_add_multiple_favorites_and_reopen_for_another_object(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    repo = JsonFavoritesRepository(tmp_path / "favorites.json")
    dialog = FavoritesDialog(repo, "220P", "PT")
    try:
        dialog.save_button.click()
        first = repo.load()[0]
        dialog.new_button.click()
        assert dialog.list.currentRow() == -1
        assert dialog.designation.text() == ""
        assert dialog.name.text() == ""
        assert dialog.notes.toPlainText() == ""
        assert not dialog.remove_button.isEnabled()
        dialog.designation.setText("99942")
        dialog.name.setText("Apophis")
        dialog.save_button.click()
        assert repo.load() == [first, Favorite("99942", "Apophis")]
    finally:
        dialog.close()
    reopened = FavoritesDialog(repo, "433", "PT")
    try:
        reopened.show()
        app.processEvents()
        assert reopened.designation.text() == "433"
        reopened.save_button.click()
        assert [item.designation for item in repo.load()] == ["220P", "99942", "433"]
        reopened.list.setCurrentRow(1)
        assert reopened.designation.text() == "99942"
        reopened.notes.setPlainText("Atualizado")
        reopened.save_button.click()
        assert len(repo.load()) == 3
        assert repo.load()[1].notes == "Atualizado"
    finally:
        reopened.close()


@pytest.mark.parametrize("language", ["PT", "EN", "ES"])
@pytest.mark.parametrize("unit", ["UA", "km"])
def test_summary_exports_current_units_and_full_instant(tmp_path: Path, language: str, unit: str) -> None:
    app = QApplication.instance() or QApplication([])
    instant = Time("2026-09-10T01:00:00", scale="utc")
    sample = SummarySample(instant, 1., 1.5, 51.5, -8.25, 11.3, "T", 115., 31.1, 260.)
    data = ObjectSummary(SummaryTarget("220P/McNaught <test>", "1", True, instant), sample, sample, sample, instant, instant)
    widget = ObjectSummaryWidget()
    try:
        assert not widget.pdf_button.isEnabled()
        widget.set_language(language)
        widget.set_distance_unit(unit)
        widget.set_summary(data, "LOCAL", -19.9, -43.9)
        report = widget.report()
        assert len(report.headers) == 10
        assert report.rows[1][1].startswith("2026-09-09")
        assert "LOCAL" in report.rows[1][1]
        assert report.rows[1][3] == widget.table.item(1, 3).text()
        csv_path = tmp_path / "summary.csv"
        export_summary(report, csv_path, "csv")
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            records = list(csv.reader(stream, delimiter=";"))
        assert len(records) == 4
        assert records[2][1:11] == report.rows[1]
        assert records[2][0] == data.target.name
        assert records[2][-1] == report.conventions
        pdf_path = tmp_path / "summary.pdf"
        export_summary(report, pdf_path, "pdf")
        document = QPdfDocument()
        document.load(str(pdf_path))
        assert document.pageCount() == 1
        text = document.getAllText(0).text()
        assert "McNaught <test>" in text
        assert "JPL Horizons" in text and "LOCAL" in text
        document.close()
        previous = pdf_path.read_bytes()
        with patch("neomapper.presentation.object_summary.QFileDialog.getSaveFileName", return_value=("", "")):
            widget.pdf_button.click()
        assert pdf_path.read_bytes() == previous
        widget.reset()
        assert not widget.csv_button.isEnabled()
    finally:
        widget.close()


def test_help_and_about_in_all_languages(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    with patch.dict(os.environ, {"NEOMAPPER_DATA_DIR": str(tmp_path)}):
        window = gui.NEOMapperMainWindow()
        try:
            for language in ("ES", "PT", "EN"):
                window.language_header_combo.setCurrentText(language)
                for topic, key in HELP_TOPICS.items():
                    assert key in load_catalog(language)
                    assert help_text(topic, language) != key
                assert window.time_mode_combo.toolTip() == help_text("Time display", language)
                assert "Observatório SONEAR" in window.sponsor_label.text()
                assert "AstroNEOS" in window.sponsor_label.text()
                assert 'href="https://www.youtube.com/@AstroNEOS"' in window.channel_label.text()
                assert window.channel_label.openExternalLinks()
        finally:
            window.close()
