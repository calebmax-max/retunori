from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from openpyxl import Workbook


def report_xlsx(rows: list[dict]) -> BytesIO:
    workbook = Workbook(); sheet = workbook.active; sheet.title = "RETUNORI Report"
    headers = list(rows[0].keys()) if rows else ["status"]
    sheet.append(headers)
    for row in rows: sheet.append([row.get(key) for key in headers])
    output = BytesIO(); workbook.save(output); output.seek(0); return output


def report_pdf(title: str, rows: list[dict]) -> BytesIO:
    output = BytesIO(); document = canvas.Canvas(output, pagesize=A4); width, height = A4
    document.setFont("Helvetica-Bold", 18); document.drawString(45, height - 55, title)
    document.setFont("Helvetica", 9); y = height - 90
    for row in rows:
        line = " | ".join(f"{key}: {value}" for key, value in row.items())
        document.drawString(45, y, line[:140]); y -= 16
        if y < 45: document.showPage(); y = height - 45
    document.save(); output.seek(0); return output

