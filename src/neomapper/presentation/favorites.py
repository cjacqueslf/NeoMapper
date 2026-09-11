"""Edit and select favorites without issuing network requests."""

from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QLineEdit, QPlainTextEdit, QFormLayout, QPushButton, QMessageBox)

from neomapper.application.favorites import Favorite, FavoritesRepository
from neomapper.presentation.i18n import Translator
from neomapper.infrastructure.diagnostics import record_exception


class FavoritesDialog(QDialog):
    def __init__(self, repository: FavoritesRepository, designation: str, language: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.items = repository.load()
        self.selected_designation: str | None = None
        self.tr = Translator(language).tr
        self.setWindowTitle(self.tr("Favorites"))
        self.resize(600, 520)
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        layout.addWidget(self.list)
        self.new_button = QPushButton(self.tr("New favorite"))
        self.new_button.clicked.connect(self.new_favorite)
        layout.addWidget(self.new_button)
        form = QFormLayout()
        self.designation = QLineEdit(designation)
        self.name = QLineEdit(designation)
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(90)
        form.addRow(self.tr("Object / Designation"), self.designation)
        form.addRow(self.tr("Name"), self.name)
        form.addRow(self.tr("Notes"), self.notes)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.save_button = QPushButton(self.tr("Save favorite"))
        self.remove_button = QPushButton(self.tr("Remove favorite"))
        self.use_button = QPushButton(self.tr("Use favorite"))
        close = QPushButton(self.tr("Close"))
        for button in (self.save_button, self.remove_button, self.use_button, close):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.list.currentRowChanged.connect(self.select)
        self.save_button.clicked.connect(self.save)
        self.remove_button.clicked.connect(self.remove)
        self.use_button.clicked.connect(self.use)
        close.clicked.connect(self.reject)
        self.refresh()
        self.designation.setFocus()

    def refresh(self, selected: int = -1) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for item in self.items:
            self.list.addItem(f"{item.name} — {item.designation}")
        self.list.setCurrentRow(selected)
        self.list.blockSignals(False)
        self.remove_button.setEnabled(selected >= 0)
        self.use_button.setEnabled(selected >= 0)
        if selected >= 0:
            self.select(selected)

    def new_favorite(self) -> None:
        self.list.setCurrentRow(-1)
        self.list.clearSelection()
        self.selected_designation = None
        self.designation.clear()
        self.name.clear()
        self.notes.clear()
        self.remove_button.setEnabled(False)
        self.use_button.setEnabled(False)
        self.designation.setFocus()

    def select(self, index: int) -> None:
        valid = 0 <= index < len(self.items)
        self.remove_button.setEnabled(valid)
        self.use_button.setEnabled(valid)
        if valid:
            item = self.items[index]
            self.designation.setText(item.designation)
            self.name.setText(item.name)
            self.notes.setPlainText(item.notes)

    def persist(self, items: list[Favorite], selected: int = -1) -> None:
        try:
            self.repository.save(items)
        except Exception:
            record_exception("favorites_error.log")
            QMessageBox.warning(self, self.tr("Favorites"), self.tr("Could not save favorites"))
            return
        self.items = items
        self.refresh(selected)

    def save(self) -> None:
        designation = self.designation.text().strip()
        if not designation:
            QMessageBox.information(self, self.tr("Favorites"), self.tr("Enter an object first"))
            return
        value = Favorite(designation, self.name.text().strip() or designation, self.notes.toPlainText())
        items = list(self.items)
        index = next((i for i, item in enumerate(items) if item.designation.casefold() == designation.casefold()), -1)
        if index < 0:
            items.append(value)
            index = len(items) - 1
        else:
            items[index] = value
        self.persist(items, index)

    def remove(self) -> None:
        index = self.list.currentRow()
        if index >= 0:
            self.persist([item for i, item in enumerate(self.items) if i != index])

    def use(self) -> None:
        index = self.list.currentRow()
        if index >= 0:
            self.selected_designation = self.items[index].designation
            self.accept()
