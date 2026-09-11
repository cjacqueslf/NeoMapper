from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from neomapper.presentation.i18n import Translator
from neomapper.presentation.coordinates import format_declination, format_right_ascension


def create_ephemeris_pdf(object_name: str, rows: list[dict], output_pdf: str, language: str = "EN") -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    tr = Translator(language).tr
    if not rows:
        raise ValueError(tr("No ephemerides returned"))
    path = Path(output_pdf)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), rightMargin=12*mm,
                            leftMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    styles["Normal"].fontSize = 8
    title = escape(str(rows[0].get("target") or object_name))
    story = [Paragraph(f'{tr("Ephemerides")} - {title}', styles["Title"]),
             Paragraph(tr("Report conventions"), styles["Normal"]), Spacer(1, 6*mm)]
    keys = ["Date", "Hour", "Minute", "Right Ascension", "Declination", "Altitude",
            "Azimuth", "Sky Motion", "Sky Motion PA", "Magnitude"]
    data = [[Paragraph(escape(tr(key)), styles["Normal"]) for key in keys]]

    def number(value: float | None, precision: int = 3) -> str:
        if value is None:
            return "-"
        text = f"{value:.{precision}f}"
        return text.replace(".", ",") if language.upper() in ("PT", "ES") else text

    for row in rows:
        date, clock = row["utc"].split("T")
        magnitude = row["V"] if row["V"] is not None else row["Tmag"]
        mag_label = " V" if row["V"] is not None else " T"
        data.append([date, clock[:2], clock[3:5], format_right_ascension(row["RA"], language), format_declination(row["DEC"], language),
                     number(row["EL"]), number(row["AZ"]), number(row["Sky_motion"]),
                     number(row["Sky_mot_PA"]), number(magnitude, 2) + (mag_label if magnitude is not None else "")])
    table = Table(data, repeatRows=1, colWidths=[26*mm, 13*mm, 15*mm, 32*mm, 30*mm, 26*mm, 26*mm, 31*mm, 31*mm, 23*mm])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#dce8f1")),
        ("GRID", (0,0), (-1,-1), .25, colors.grey), ("FONTSIZE", (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f5f8")])]))
    story.append(table)
    doc.build(story)
    return str(path)
