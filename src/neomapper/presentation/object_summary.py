"""Compact orbital summary with an expandable, read-only table."""
from __future__ import annotations

from PySide6.QtCore import Qt
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QDialog, QSizePolicy, QHeaderView,
    QHBoxLayout, QFileDialog, QMessageBox)
from neomapper.domain.object_summary import ObjectSummary
from neomapper.presentation.coordinates import format_right_ascension, format_declination
from neomapper.presentation.distances import AU_KM, format_distance
from neomapper.presentation.i18n import Translator, format_number
from neomapper.shared.utils import format_time_for_map
from neomapper.infrastructure.paths import object_output_dir
from neomapper.infrastructure.diagnostics import record_exception
from neomapper.presentation.summary_export import SummaryReport, export_summary
from neomapper.presentation.context_help import help_text, show_help
from PySide6.QtGui import QResizeEvent


class SummaryTable(QTableWidget):
    """Keep all event rows visible as columns and wrapped text change size."""

    def fit_rows(self) -> None:
        self.resizeRowsToContents()
        height = (max(self.horizontalHeader().height(), self.horizontalHeader().sizeHint().height())
                  + sum(self.rowHeight(row) for row in range(self.rowCount()))
                  + 2 * self.frameWidth() + self.horizontalScrollBar().sizeHint().height())
        if self.height() != height:
            self.setFixedHeight(height)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.fit_rows()


class ObjectSummaryWidget(QWidget):
    def __init__(self, parent: QWidget | None = None, *, show_expand_button: bool = True) -> None:
        super().__init__(parent)
        self.show_expand_button = show_expand_button
        self.data: ObjectSummary | None = None
        self.calculating = False
        self.language = "EN"
        self.distance_unit = "km"
        self.mode = "UTC"
        self.latitude = 0.0
        self.longitude = 0.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFixedHeight(34)
        self.title.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #191966; color: #edf3ff; padding: 6px;")
        layout.addWidget(self.title)
        self.loading = QLabel()
        self.loading.setAlignment(Qt.AlignCenter)
        self.loading.setWordWrap(True)
        self.loading.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffcc33; padding: 12px;")
        layout.addWidget(self.loading)
        self.table = SummaryTable(3, 10)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { font-size: 12px; background-color: #101922; "
            "alternate-background-color: #1e2a3b; color: #edf3ff; selection-background-color: #24558a; } "
            "QHeaderView::section { font-size: 12px; background-color: #1e2a3b; "
            "color: #edf3ff; border: 1px solid #26394a; padding: 4px; }"
        )
        layout.addWidget(self.table)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("font-size: 10px; color: #a8b8ca;")
        layout.addWidget(self.note)
        self.expand = QPushButton()
        self.expand.clicked.connect(self.open_expanded)
        actions = QHBoxLayout()
        actions.addWidget(self.expand)
        self.pdf_button = QPushButton()
        self.csv_button = QPushButton()
        self.pdf_button.clicked.connect(lambda: self.save_report("pdf"))
        self.csv_button.clicked.connect(lambda: self.save_report("csv"))
        actions.addWidget(self.pdf_button)
        actions.addWidget(self.csv_button)
        self.help_button = QPushButton()
        self.help_button.clicked.connect(lambda: show_help(self, self.language))
        actions.addWidget(self.help_button)
        layout.addLayout(actions)
        layout.addStretch()
        self.refresh()

    def reset(self) -> None:
        self.data = None
        self.refresh()

    def set_language(self, language: str) -> None:
        self.language = language
        self.refresh()

    def set_distance_unit(self, unit: str) -> None:
        self.distance_unit = unit
        self.refresh()

    def set_summary(self, data: ObjectSummary, mode: str, latitude: float, longitude: float) -> None:
        self.data, self.mode, self.latitude, self.longitude = data, mode, latitude, longitude
        self.refresh()

    def set_calculating(self, calculating: bool) -> None:
        self.calculating = calculating
        self.loading.setText(Translator(self.language).tr("Calculating orbital summary…"))
        self.loading.setVisible(calculating)

    def refresh(self) -> None:
        tr = Translator(self.language).tr
        self.expand.setText(tr("Expand summary"))
        self.pdf_button.setText(tr("Save PDF"))
        self.csv_button.setText(tr("Save CSV"))
        self.help_button.setText(tr("Help"))
        self.pdf_button.setEnabled(self.data is not None)
        self.csv_button.setEnabled(self.data is not None)
        self.table.setVisible(self.data is not None)
        self.expand.setVisible(self.data is not None and self.show_expand_button)
        self.title.setText(self.data.target.name if self.data else tr("Orbital summary"))
        if self.data is None:
            self.note.setText(tr("Calculate summary with its button"))
            return
        keys = ["Ephemerides", "Date", "Magnitude", "Solar distance", "Earth distance",
                "Right Ascension", "Declination", "Elongation", "Phase angle", "Tail PA"]
        self.table.setHorizontalHeaderLabels([tr(key) for key in keys])
        for index, key in enumerate(keys):
            self.table.horizontalHeaderItem(index).setToolTip(help_text(key, self.language))
        self.table.setColumnHidden(9, not self.data.target.is_comet)
        perihelion_key = "Next perihelion" if self.data.perihelion_refined else ("Estimated perihelion" if self.data.extended_search else "Perihelion")
        events = [(perihelion_key, self.data.perihelion), ("Selected date", self.data.selected),
                  ("Nearest approach", self.data.closest)]

        def number(value: float | None, precision: int, suffix: str = "") -> str:
            return "—" if value is None else format_number(value, precision, self.language, False) + suffix

        for index, (key, row) in enumerate(events):
            date, mode = format_time_for_map(row.instant, self.mode, self.latitude, self.longitude)
            values = [tr(key), date[:10], number(row.magnitude, 1, " " + row.magnitude_band),
                      format_distance(None if row.radius_au is None else row.radius_au * AU_KM, self.distance_unit, self.language),
                      format_distance(None if row.delta_au is None else row.delta_au * AU_KM, self.distance_unit, self.language),
                      format_right_ascension(row.ra_deg, self.language), format_declination(row.dec_deg, self.language),
                      number(row.elongation_deg, 1, "°"), number(row.phase_deg, 1, "°"), number(row.tail_pa_deg, 1, "°")]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter if column == 0 else Qt.AlignCenter)
                help_key = "Perihelion" if column == 0 and index == 0 else (key if column == 0 else keys[column])
                explanation = help_text(help_key, self.language)
                item.setToolTip(f"{date} {mode}" if column == 1 else value + ("\n" + explanation if explanation else ""))
                self.table.setItem(index, column, item)
        self.table.resizeColumnsToContents()
        self.table.fit_rows()
        start = format_time_for_map(self.data.search_start, self.mode, self.latitude, self.longitude)[0][:10]
        stop = format_time_for_map(self.data.search_stop, self.mode, self.latitude, self.longitude)[0][:10]
        if self.data.extended_search:
            period = format_number(self.data.target.period_days / 365.25, 1, self.language, False)
            self.note.setText(tr("Summary extended short", mode=self.mode, start=start, stop=stop, period=period))
            details = tr("Summary extended conventions", mode=self.mode, start=start, stop=stop, period=period)
            if self.data.search_limited:
                warning = tr("Summary perihelion unconfirmed")
                details += " " + warning
                self.note.setText(self.note.text() + " " + warning)
        else:
            self.note.setText(tr("Summary short conventions", mode=self.mode, start=start, stop=stop))
            details = tr("Summary conventions", mode=self.mode, start=start, stop=stop)
        if self.data.target.is_comet:
            details += " " + tr("Summary tail conventions")
        self.note.setToolTip(details)
        self.table.horizontalHeaderItem(9).setToolTip(tr("Summary tail conventions"))

    def report(self) -> SummaryReport:
        if self.data is None:
            raise ValueError("No orbital summary")
        columns = [column for column in range(self.table.columnCount()) if not self.table.isColumnHidden(column)]
        rows = [[self.table.item(row, column).toolTip() if column == 1 else self.table.item(row, column).text()
                 for column in columns] for row in range(self.table.rowCount())]
        return SummaryReport(self.data.target.name,
            [self.table.horizontalHeaderItem(column).text() for column in columns], rows,
            self.note.toolTip(), self.language)

    def save_report(self, kind: str) -> None:
        if self.data is None:
            return
        tr = Translator(self.language).tr
        self.loading.setText(tr("Calculating orbital summary…"))
        self.loading.setVisible(self.calculating)
        try:
            default = object_output_dir(self.data.target.name) / ("orbital_summary." + kind)
            path, _ = QFileDialog.getSaveFileName(self, tr("Save PDF" if kind == "pdf" else "Save CSV"),
                                                 str(default), f"{kind.upper()} (*.{kind})")
            if not path:
                return
            destination = Path(path)
            if not destination.suffix:
                destination = destination.with_suffix("." + kind)
            export_summary(self.report(), destination, kind)
        except Exception:
            record_exception("summary_export_error.log")
            QMessageBox.warning(self, tr("Orbital summary"), tr("Could not export report"))

    def open_expanded(self) -> None:
        if self.data is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(Translator(self.language).tr("Orbital summary"))
        dialog.resize(1320, 300)
        layout = QVBoxLayout(dialog)
        summary = ObjectSummaryWidget(dialog)
        summary.set_language(self.language)
        summary.set_distance_unit(self.distance_unit)
        summary.set_summary(self.data, self.mode, self.latitude, self.longitude)
        summary.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        summary.expand.hide()
        layout.addWidget(summary)
        dialog.exec()
