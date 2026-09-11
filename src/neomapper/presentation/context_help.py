"""Contextual explanations shared by tooltips and the compact help window."""
from html import escape

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QTextBrowser, QPushButton
from neomapper.presentation.i18n import Translator


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
