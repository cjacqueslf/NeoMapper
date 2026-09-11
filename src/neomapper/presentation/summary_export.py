"""Export an already formatted summary without recalculating scientific values."""
from dataclasses import dataclass
import csv
import os
from pathlib import Path
import tempfile
from xml.sax.saxutils import escape

from neomapper.presentation.i18n import Translator
from neomapper.shared.version import APP_TITLE, APP_VERSION


@dataclass(frozen=True)
class SummaryReport:
    object_name: str
    headers: list[str]
    rows: list[list[str]]
    conventions: str
    language: str


def export_summary(report: SummaryReport, path: Path, kind: str) -> None:
    """Replace the destination only after a complete PDF or UTF-8 CSV is written."""
    if kind not in ("pdf", "csv"):
        raise ValueError("Unsupported summary export format")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix="." + kind)
    os.close(handle)
    try:
        if kind == "pdf":
            _write_pdf(report, Path(temporary))
        else:
            _write_csv(report, Path(temporary))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _csv_text(value: str) -> str:
    # Treat external object names/notes as text in spreadsheet applications.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def _write_csv(report: SummaryReport, path: Path) -> None:
    tr = Translator(report.language).tr
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow([tr("Object"), *report.headers, tr("Software"), tr("Version"), tr("Conventions")])
        for row in report.rows:
            writer.writerow([_csv_text(report.object_name), *row, APP_TITLE, APP_VERSION, report.conventions])


def _write_pdf(report: SummaryReport, path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    tr = Translator(report.language).tr
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("SummaryBody", parent=styles["Normal"], fontSize=8, leading=11)
    heading = ParagraphStyle("SummaryHead", parent=normal, textColor=colors.white, fontName="Helvetica-Bold")
    def paragraph(value: str, header: bool = False) -> Paragraph:
        return Paragraph(escape(value.replace("—", "-").replace("−", "-")).replace("\n", "<br/>"), heading if header else normal)

    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=14*mm, bottomMargin=14*mm, title=report.object_name, author=APP_TITLE)
    widths = [30, 35, 19, 27, 27, 32, 32, 23, 23, 25][:len(report.headers)]
    widths = [value / sum(widths) * doc.width for value in widths]
    table = Table([[paragraph(value, True) for value in report.headers],
                   *[[paragraph(value) for value in row] for row in report.rows]], colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#191966")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#edf2f7")]),
        ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#b3bfcb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story = [Paragraph(escape(tr("Orbital summary")), styles["Title"]),
             Paragraph(escape(report.object_name), styles["Heading2"]),
             paragraph(f"{APP_TITLE} {APP_VERSION}"), Spacer(1, 6*mm), table,
             Spacer(1, 6*mm), paragraph(report.conventions)]
    doc.build(story)
