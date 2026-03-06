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
# Professional Email Helper
# ─────────────────────────────────────────────
def send_professional_email(to: str, subject: str, heading: str, body: str,
                             footer: str = 'AttendX'):
    """
    Sends a professionally formatted HTML + plain-text email.
    Used for: OTP, attendance alerts, request notifications, password reset.
    """
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    html_body = body.replace('\n', '<br>').replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f6f9;font-family:'Segoe UI',Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 0">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08)">
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e3a5f,#3b82f6);padding:32px 40px;text-align:center">
            <div style="font-size:28px;font-weight:900;color:#ffffff;letter-spacing:2px">AttendX</div>
            <div style="font-size:12px;color:rgba(255,255,255,0.75);letter-spacing:3px;margin-top:4px;text-transform:uppercase">
              Attendance Management System
            </div>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:40px">
            <h2 style="margin:0 0 20px;font-size:20px;color:#1e3a5f;font-weight:700">{heading}</h2>
            <div style="font-size:14px;color:#4b5563;line-height:1.8">{html_body}</div>
          </td>
        </tr>
        <!-- Divider -->
        <tr><td style="padding:0 40px"><hr style="border:none;border-top:1px solid #e5e7eb"></td></tr>
        <!-- Footer -->
        <tr>
          <td style="padding:24px 40px;text-align:center">
            <p style="margin:0;font-size:12px;color:#9ca3af">
              This is an automated message from <strong>{footer}</strong>.<br>
              Please do not reply to this email.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    text_body = f"{heading}\n\n{body}\n\n— {footer}"

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=f"AttendX <{settings.EMAIL_HOST_USER}>",
        to=[to],
    )
    email.attach_alternative(html, 'text/html')
    email.send(fail_silently=False)


# ─────────────────────────────────────────────
# Email + WhatsApp helpers
# ─────────────────────────────────────────────
def send_attendance_alert_email(parent_email: str, student_name: str,
                                subject_name: str, percentage: float):
    """Professional attendance alert email to parent."""
    status_str = (
        'critically low' if percentage < 60 else
        'low' if percentage < 75 else
        'below expected'
    )
    send_professional_email(
        to=parent_email,
        subject=f'Attendance Alert — {student_name} | {subject_name}',
        heading='Important: Attendance Alert',
        body=(
            f"Dear Parent / Guardian,\n\n"
            f"We hope this message finds you well. This is an official notification from the "
            f"institution regarding the attendance record of your ward.\n\n"
            f"Student Name:       {student_name}\n"
            f"Subject:            {subject_name}\n"
            f"Current Attendance: {percentage:.1f}%\n"
            f"Status:             {status_str.title()}\n\n"
            f"As per our institutional policy, a minimum of 75% attendance is mandatory for all "
            f"students to be eligible for examinations. We kindly request you to take immediate "
            f"note of this matter and encourage your ward to attend classes regularly.\n\n"
            f"If there are any extenuating circumstances leading to frequent absences, we encourage "
            f"you or your ward to speak with the respective faculty member or the administration "
            f"at the earliest.\n\n"
            f"We appreciate your cooperation and support in ensuring the academic success of your child."
        ),
        footer='AttendX — Attendance Management System',
    )


def get_whatsapp_message_link(phone_number: str, student_name: str,
                               subject_name: str, percentage: float) -> str:
    """Professional WhatsApp alert message link for parent."""
    import urllib.parse
    threshold_note = (
        'below the required 75% threshold' if percentage < 75 else 'below expected levels'
    )
    message = (
        f"Dear Parent, this is an official attendance notice from AttendX. "
        f"Your ward {student_name}'s attendance in {subject_name} is currently {percentage:.1f}%, "
        f"which is {threshold_note}. "
        f"Kindly ensure regular class attendance to avoid academic consequences. "
        f"For queries, please contact the institution. — AttendX Attendance System"
    )
    phone = phone_number.lstrip('0')
    return f"https://wa.me/91{phone}?text={urllib.parse.quote(message)}"


def send_password_reset_otp_email(user_email: str, user_name: str, otp_code: str):
    """Professional OTP email for password reset."""
    send_professional_email(
        to=user_email,
        subject='Password Reset OTP — AttendX',
        heading='Password Reset Request',
        body=(
            f"Dear {user_name},\n\n"
            f"We received a request to reset the password for your AttendX account. "
            f"Use the following One-Time Password (OTP) to proceed:\n\n"
            f"                {otp_code}\n\n"
            f"This OTP is valid for 10 minutes only. Do not share it with anyone.\n\n"
            f"If you did not request a password reset, please disregard this email. "
            f"Your account remains secure."
        ),
        footer='AttendX Attendance Management System',
    )