"""
analytics/utils.py
PDF and CSV report generation using ReportLab and openpyxl
"""
import io
import csv
import datetime
from django.http import HttpResponse


# ─────────────────────────────────────────────
# CSV Report Generation
# ─────────────────────────────────────────────
def generate_attendance_csv(student_data: list, report_title: str = "Attendance Report") -> HttpResponse:
    """
    Generates a CSV file from student attendance data.
    student_data: list of dicts with keys like name, enrollment, subject, total, attended, percentage
    """
    response = HttpResponse(content_type='text/csv')
    filename = f"attendance_report_{datetime.date.today()}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Header
    writer.writerow([report_title])
    writer.writerow([f"Generated on: {datetime.datetime.now().strftime('%d %B %Y, %I:%M %p')}"])
    writer.writerow([])  # Empty row

    # Column headers
    writer.writerow([
        'S.No', 'Enrollment No.', 'Student Name', 'Roll No.',
        'Subject Code', 'Subject Name', 'Total Classes',
        'Classes Attended', 'Attendance %', 'Status'
    ])

    for i, row in enumerate(student_data, start=1):
        writer.writerow([
            i,
            row.get('enrollment_number', ''),
            row.get('name', ''),
            row.get('roll_number', ''),
            row.get('subject_code', ''),
            row.get('subject_name', ''),
            row.get('total_classes', 0),
            row.get('attended', 0),
            f"{row.get('percentage', 0):.2f}%",
            row.get('status', '').upper(),
        ])

    return response


# ─────────────────────────────────────────────
# PDF Report Generation using ReportLab
# ─────────────────────────────────────────────
def generate_attendance_pdf(student_data: list, report_title: str = "Attendance Report",
                             teacher_name: str = "", subject_name: str = "",
                             academic_year: str = "") -> HttpResponse:
    """
    Generates a professional PDF attendance report.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.enums import TA_CENTER

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1*cm, leftMargin=1*cm,
        topMargin=1.5*cm, bottomMargin=1*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, alignment=TA_CENTER)
    sub_style   = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER)

    elements = []

    # Title
    elements.append(Paragraph(report_title, title_style))
    elements.append(Spacer(1, 0.2*inch))

    # Meta info
    meta = f"Subject: {subject_name} | Teacher: {teacher_name} | Academic Year: {academic_year}"
    elements.append(Paragraph(meta, sub_style))
    gen = f"Generated on: {datetime.datetime.now().strftime('%d %B %Y, %I:%M %p')}"
    elements.append(Paragraph(gen, sub_style))
    elements.append(Spacer(1, 0.3*inch))

    # Table data
    headers = ['S.No', 'Enrollment No.', 'Name', 'Roll No.',
                'Total Classes', 'Attended', 'Attendance %', 'Status']
    table_data = [headers]

    for i, row in enumerate(student_data, start=1):
        pct    = row.get('percentage', 0)
        status = row.get('status', '')
        table_data.append([
            str(i),
            row.get('enrollment_number', ''),
            row.get('name', ''),
            row.get('roll_number', ''),
            str(row.get('total_classes', 0)),
            str(row.get('attended', 0)),
            f"{pct:.2f}%",
            status.upper(),
        ])

    # Build table
    col_widths = [1*cm, 3.5*cm, 5*cm, 2.5*cm, 3*cm, 2.5*cm, 3*cm, 2.5*cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Style
    table_style = TableStyle([
        # Header
        ('BACKGROUND',  (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
        ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0), 9),
        ('ALIGN',       (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ECF0F1')]),
        ('FONTSIZE',    (0, 1), (-1, -1), 8),
        ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])

    # Color-code status column
    for i, row in enumerate(student_data, start=1):
        status = row.get('status', '')
        if status == 'critical':
            table_style.add('BACKGROUND', (7, i), (7, i), colors.HexColor('#E74C3C'))
            table_style.add('TEXTCOLOR',  (7, i), (7, i), colors.white)
        elif status == 'warning':
            table_style.add('BACKGROUND', (7, i), (7, i), colors.HexColor('#F39C12'))
            table_style.add('TEXTCOLOR',  (7, i), (7, i), colors.white)
        elif status == 'safe':
            table_style.add('BACKGROUND', (7, i), (7, i), colors.HexColor('#27AE60'))
            table_style.add('TEXTCOLOR',  (7, i), (7, i), colors.white)

    table.setStyle(table_style)
    elements.append(table)

    # Summary
    elements.append(Spacer(1, 0.3*inch))
    total = len(student_data)
    safe     = sum(1 for r in student_data if r.get('status') == 'safe')
    warning  = sum(1 for r in student_data if r.get('status') == 'warning')
    critical = sum(1 for r in student_data if r.get('status') == 'critical')

    summary_text = (
        f"Summary: Total Students: {total} | "
        f"Above 75% (Safe): {safe} | "
        f"60-75% (Warning): {warning} | "
        f"Below 60% (Critical): {critical}"
    )
    elements.append(Paragraph(summary_text, sub_style))

    doc.build(elements)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"attendance_report_{datetime.date.today()}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─────────────────────────────────────────────
# Email + WhatsApp helpers
# ─────────────────────────────────────────────
def send_attendance_alert_email(parent_email: str, student_name: str,
                                subject_name: str, percentage: float):
    """
    Sends attendance alert email to parent.
    """
    from django.core.mail import send_mail
    from django.conf import settings

    subject = f"Attendance Alert - {student_name}"
    message = (
        f"Dear Parent,\n\n"
        f"This is to inform you that your ward {student_name}'s attendance "
        f"in {subject_name} has dropped to {percentage:.2f}%.\n\n"
        f"Please ensure regular attendance to avoid academic penalties.\n\n"
        f"Regards,\nCollege Administration"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[parent_email],
        fail_silently=False,
    )


def get_whatsapp_message_link(phone_number: str, student_name: str,
                               subject_name: str, percentage: float) -> str:
    """
    Returns a WhatsApp click-to-chat link for parent notification.
    Frontend can open this link to open WhatsApp with pre-filled message.
    """
    import urllib.parse
    message = (
        f"Dear Parent, your ward {student_name}'s attendance in "
        f"{subject_name} is {percentage:.2f}%. "
        f"Please ensure regular attendance. - College Administration"
    )
    encoded = urllib.parse.quote(message)
    # Remove leading 0 from phone number if present, add country code
    phone = phone_number.lstrip('0')
    return f"https://wa.me/91{phone}?text={encoded}"
