"""Native printer selection for generated PDF reports."""
from pathlib import Path

from PySide6.QtCore import QSize, QRect, QBuffer, QIODevice
from PySide6.QtGui import QPainter, QPageLayout
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import QDialog, QWidget


def print_pdf(path: str, parent: QWidget) -> None:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageOrientation(QPageLayout.Orientation.Landscape)
    selector = QPrintDialog(printer, parent)
    if selector.exec() != QDialog.DialogCode.Accepted:
        return
    document = QPdfDocument(parent)
    buffer = QBuffer(document)
    buffer.setData(Path(path).read_bytes())
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    document.load(buffer)
    if document.error() != QPdfDocument.Error.None_:
        document.deleteLater()
        raise RuntimeError("PDF")
    painter = QPainter()
    try:
        if not painter.begin(printer):
            raise RuntimeError("Printer")
        first = max(1, printer.fromPage())
        last = min(document.pageCount(), printer.toPage() or document.pageCount())
        for page in range(first - 1, last):
            if page > first - 1 and not printer.newPage():
                raise RuntimeError("Printer")
            viewport = painter.viewport()
            size = document.pagePointSize(page)
            ratio = min(viewport.width() / size.width(), viewport.height() / size.height())
            target = QSize(int(size.width() * ratio), int(size.height() * ratio))
            bitmap = document.render(page, QSize(int(size.width() * 3), int(size.height() * 3)))
            painter.drawImage(QRect(viewport.topLeft(), target), bitmap)
    finally:
        if painter.isActive():
            painter.end()
        document.close()
        document.deleteLater()
