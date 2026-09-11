import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from reportlab.pdfgen.canvas import Canvas

from neomapper.presentation import report_preview


class ReportPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_preview_exports_same_document_and_remains_open(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "preview.pdf"
            pdf = Canvas(str(source))
            for page in range(3):
                pdf.drawString(72, 720, f"Page {page + 1}")
                pdf.showPage()
            pdf.save()
            dialog = report_preview.ReportPreviewDialog(str(source), "PT")
            try:
                dialog.show()
                self.assertEqual(dialog.document.pageCount(), 3)
                self.assertEqual(dialog.view.pageMode(), report_preview.QPdfView.PageMode.MultiPage)
                target = Path(folder) / "saved"
                with patch.object(report_preview.QFileDialog, "getSaveFileName", return_value=(str(target), "PDF")):
                    dialog.save_pdf()
                self.assertEqual(target.with_suffix(".pdf").read_bytes(), source.read_bytes())
                with patch.object(report_preview, "print_pdf") as printing:
                    dialog.print_report()
                    printing.assert_called_once_with(str(source), dialog)
                self.assertTrue(dialog.isVisible())
                with patch.object(report_preview.QFileDialog, "getSaveFileName", return_value=("", "")), patch.object(report_preview.shutil, "copyfile") as copy:
                    dialog.save_pdf()
                    copy.assert_not_called()
            finally:
                dialog.document.close()
                dialog.close()

    def test_invalid_pdf_has_translated_error(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "Não foi possível abrir"):
                report_preview.ReportPreviewDialog(str(Path(folder) / "missing.pdf"), "PT")

    def test_generated_report_contains_sexagesimal_coordinates(self) -> None:
        from neomapper.presentation.ephemeris_report import create_ephemeris_pdf

        row = dict(utc="2026-09-09T00:00:00", RA=188.73625, DEC=-12.5824166667,
                   EL=30., AZ=120., Sky_motion=1., Sky_mot_PA=90., V=14., Tmag=None)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "coordinates.pdf")
            create_ephemeris_pdf("Fixture", [row], path, "PT")
            dialog = report_preview.ReportPreviewDialog(path, "PT")
            try:
                text = dialog.document.getAllText(0).text()
                self.assertIn("12h 34m 56,70s", text)
                self.assertIn('-12° 34\' 56,70"', text)
                self.assertNotIn("AR/Dec: graus", text)
                self.assertEqual(row["RA"], 188.73625)
            finally:
                dialog.document.close()
                dialog.close()
