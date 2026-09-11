"""On-screen PDF reports with optional export and native printing."""
from __future__ import annotations

from pathlib import Path
import shutil
import traceback

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from neomapper.infrastructure.paths import logs_dir, output_dir
from neomapper.presentation.i18n import Translator
from neomapper.presentation.pdf_print import print_pdf


class ReportPreviewDialog(QDialog):
    def __init__(self, path: str, language: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = Path(path)
        self.translator = Translator(language)
        self.setWindowTitle(self.translator.tr("Report preview"))
        self.resize(1100, 750)
        layout = QVBoxLayout(self)
        self.document = QPdfDocument(self)
        # A memory-backed device avoids Qt retaining a Windows file lock after close().
        self.buffer = QBuffer(self.document)
        try:
            self.buffer.setData(self.path.read_bytes())
        except OSError as exc:
            raise RuntimeError(self.translator.tr("Could not open report")) from exc
        self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.document.load(self.buffer)
        if self.document.error() != QPdfDocument.Error.None_:
            self.document.close()
            raise RuntimeError(self.translator.tr("Could not open report"))
        self.view = QPdfView(self)
        self.view.setDocument(self.document)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        layout.addWidget(self.view)
        actions = QHBoxLayout()
        for key, callback in (("Save PDF", self.save_pdf), ("Print PDF", self.print_report), ("Close", self.accept)):
            button = QPushButton(self.translator.tr(key), self)
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)

    def show_error(self) -> None:
        log_path = logs_dir() / "ephemeris_preview_error.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        QMessageBox.critical(self, "NEOMapper", self.translator.tr("Could not export report"))

    def save_pdf(self) -> None:
        target, _ = QFileDialog.getSaveFileName(
            self, self.translator.tr("Save PDF"), str(output_dir() / "ephemeris_report.pdf"), "PDF (*.pdf)"
        )
        if not target:
            return
        if not target.lower().endswith(".pdf"):
            target += ".pdf"
        try:
            shutil.copyfile(self.path, target)
        except Exception:
            self.show_error()

    def print_report(self) -> None:
        try:
            print_pdf(str(self.path), self)
        except Exception:
            self.show_error()
