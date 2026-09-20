"""Contextual explanations shared by tooltips and the compact help window."""
from html import escape

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QTextBrowser, QPushButton, QMessageBox
from neomapper.presentation.i18n import Translator
from neomapper.shared.version import APP_VERSION


HELP_TOPICS = {
    "Right Ascension": "Help right ascension",
    "Declination": "Help declination",
    "Elongation": "Help elongation",
    "Phase angle": "Help phase angle",
    "Tail PA": "Help tail PA",
    "Magnitude": "Help magnitude",
    "Time display": "Help time display",
    "Orbital summary": "Help summary reference",
    "Perihelion": "Help perihelion",
    "Nearest approach": "Help nearest approach",
    "Minimum altitude deg": "Help altitude limit",
    "Sun altitude limit deg": "Help sun limit",
    "Distance unit": "Help distance unit",
}


def help_text(topic: str, language: str) -> str:
    key = HELP_TOPICS.get(topic)
    return Translator(language).tr(key) if key else ""


def show_help(parent: QWidget, language: str) -> None:
    tr = Translator(language).tr
    dialog = QDialog(parent)
    dialog.setWindowTitle(tr("Help"))
    dialog.resize(650, 550)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser()
    browser.setHtml("".join(f"<h3>{escape(tr(title))}</h3><p>{escape(tr(key))}</p>"
                            for title, key in HELP_TOPICS.items()))
    layout.addWidget(browser)
    close = QPushButton(tr("Close"))
    close.clicked.connect(dialog.accept)
    layout.addWidget(close)
    dialog.exec()


def manual_path(language: str) -> Path:
    """Locate the bundled manual that matches the selected UI language."""
    filename = {
        "PT": f"Manual_do_Usuario_NEOMapper_{APP_VERSION}.docx",
        "ES": f"Manual_del_Usuario_NEOMapper_{APP_VERSION}.docx",
    }.get(language.upper(), f"NEOMapper_User_Manual_{APP_VERSION}.docx")
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "manuals" / filename
    return Path(__file__).resolve().parents[3] / "docs" / filename


def open_manual(parent: QWidget, language: str) -> None:
    path = manual_path(language)
    if not path.exists() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
        QMessageBox.warning(parent, Translator(language).tr("Help"),
                            Translator(language).tr("Could not open the user manual."))
