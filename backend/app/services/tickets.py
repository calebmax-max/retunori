from io import BytesIO
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def ticket_pdf(ticket) -> BytesIO:
    qr = qrcode.make(ticket.qr_token)
    qr_stream = BytesIO(); qr.save(qr_stream, format="PNG"); qr_stream.seek(0)
    output = BytesIO(); document = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    document.setFillColorRGB(0.03, 0.04, 0.08); document.rect(0, 0, width, height, fill=1, stroke=0)
    document.setFillColorRGB(0.55, 0.66, 1); document.setFont("Helvetica-Bold", 26); document.drawString(54, height - 76, "RETUNORI")
    document.setFillColorRGB(0.95, 0.96, 1); document.setFont("Helvetica-Bold", 22); document.drawString(54, height - 145, ticket.retreat_title_snapshot)
    document.setFont("Helvetica", 12); document.setFillColorRGB(0.65, 0.68, 0.76)
    lines = [("Attendee", ticket.attendee_name_snapshot), ("Course", ticket.course_snapshot), ("Date", ticket.retreat_date_snapshot.strftime("%d %B %Y, %H:%M")), ("Ticket", ticket.ticket_number), ("Price", f"KES {ticket.price_snapshot:,}"), ("Status", "PAYMENT VERIFIED"), ("M-Pesa receipt", ticket.mpesa_receipt_snapshot or "Verified payment")]
    y = height - 205
    for label, value in lines:
        document.drawString(54, y, label.upper()); document.setFillColorRGB(0.95, 0.96, 1); document.setFont("Helvetica-Bold", 13); document.drawString(54, y - 18, value); document.setFont("Helvetica", 12); document.setFillColorRGB(0.65, 0.68, 0.76); y -= 58
    document.drawImage(ImageReader(qr_stream), width - 190, 105, 120, 120, preserveAspectRatio=True, mask="auto")
    document.setFont("Helvetica", 9); document.drawString(width - 205, 88, "Present this QR code at check-in")
    document.save(); output.seek(0); return output

