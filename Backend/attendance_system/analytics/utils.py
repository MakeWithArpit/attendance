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
# Email Base Builder
# ─────────────────────────────────────────────

def _build_email_html(subject: str, content_html: str) -> str:
    """
    Master HTML email template — Prahari / Invertis University branding.
    Fully responsive: auto-adjusts for mobile and desktop.
    Tested with Gmail, Outlook, Apple Mail, Android Mail.
    """
    import datetime
    year = datetime.date.today().year
    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8"/>
  <meta http-equiv="X-UA-Compatible" content="IE=edge"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <meta name="format-detection" content="telephone=no,date=no,address=no,email=no"/>
  <title>{subject}</title>

  <!--
    ┌─────────────────────────────────────────────────────────────┐
    │  RESPONSIVE STYLES                                          │
    │  Media queries: supported by Gmail App, Apple Mail,         │
    │  Outlook iOS/Android, Samsung Mail, Spark, Hey              │
    │  Outlook desktop (Windows) ignores media queries —          │
    │  fluid % widths + min-width handle it via MSO conditionals  │
    └─────────────────────────────────────────────────────────────┘
  -->
  <style type="text/css">
    /* ── Reset ── */
    body, table, td, a {{ -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
    table, td {{ mso-table-lspace:0pt; mso-table-rspace:0pt; border-collapse:collapse; }}
    img {{ -ms-interpolation-mode:bicubic; border:0; outline:none; text-decoration:none; }}

    /* ── Outer wrapper ── */
    .email-wrapper {{
      width:100% !important;
      background:#EEF2F7;
      padding:32px 12px;
      box-sizing:border-box;
    }}

    /* ── Card: 600px on desktop, fluid on mobile ── */
    .email-card {{
      width:600px;
      max-width:100%;
      background:#ffffff;
      border-radius:16px;
      overflow:hidden;
      box-shadow:0 8px 40px rgba(0,0,0,0.10);
      margin:0 auto;
    }}

    /* ── Header padding ── */
    .email-header {{ padding:36px 48px 28px; }}

    /* ── Body padding ── */
    .email-body {{ padding:40px 48px 32px; }}

    /* ── Footer padding ── */
    .email-footer {{ padding:24px 48px; }}

    /* ── Info table inside body ── */
    .info-table {{ width:100%; border:1px solid #E2E8F0; border-radius:10px; overflow:hidden; background:#FAFAFA; }}
    .info-table td {{ padding:10px 16px; font-size:14px; }}
    .info-label {{ color:#6B7280; font-weight:600; white-space:nowrap; width:40%; }}
    .info-value {{ color:#1E293B; border-left:1px solid #E2E8F0; width:60%; }}

    /* ── OTP digit boxes ── */
    .otp-digit {{
      display:inline-block;
      width:44px; height:54px; line-height:54px;
      background:#F0F7FF;
      border:2px solid #BFDBFE;
      border-radius:10px;
      font-size:28px; font-weight:800;
      color:#1A56DB;
      text-align:center;
      margin:0 4px;
      font-family:'Courier New',Courier,monospace;
    }}

    /* ══════════════════════════════════════════
       MOBILE  (max-width: 620px)
       Gmail App on Android/iOS supports this
    ══════════════════════════════════════════ */
    @media only screen and (max-width:620px) {{

      .email-wrapper {{ padding:16px 8px !important; }}

      .email-card {{
        width:100% !important;
        border-radius:12px !important;
      }}

      /* Tighter padding on small screens */
      .email-header {{ padding:28px 20px 22px !important; }}
      .email-body   {{ padding:24px 20px 20px !important; }}
      .email-footer {{ padding:18px 20px !important; }}

      /* Brand name slightly smaller */
      .brand-name {{ font-size:20px !important; letter-spacing:1px !important; }}
      .brand-sub  {{ font-size:10px !important; letter-spacing:2px !important; }}

      /* Headings */
      .email-heading {{ font-size:17px !important; }}
      .email-subhead {{ font-size:12px !important; }}

      /* Body text */
      .email-body p, .email-body div {{
        font-size:13px !important;
        line-height:1.7 !important;
      }}

      /* OTP box — smaller digits on phones */
      .otp-digit {{
        width:34px !important; height:44px !important; line-height:44px !important;
        font-size:22px !important;
        margin:0 2px !important;
        border-radius:8px !important;
      }}
      .otp-label {{ font-size:10px !important; }}
      .otp-timer {{ font-size:11px !important; margin-top:10px !important; }}

      /* Info table: stack label above value on very small screens */
      .info-label, .info-value {{
        display:block !important;
        width:100% !important;
        border-left:none !important;
        padding:6px 12px !important;
      }}
      .info-label {{ background:#F1F5F9; border-bottom:1px solid #E2E8F0; }}

      /* Alert badge */
      .alert-badge {{ font-size:13px !important; padding:8px 18px !important; }}

      /* Notice boxes */
      .notice-box {{ padding:12px 14px !important; }}
      .notice-box p {{ font-size:12px !important; }}

      /* Footer text */
      .footer-text {{ font-size:11px !important; }}
      .footer-copy {{ font-size:10px !important; }}
    }}

    /* ══════════════════════════════════════════
       DARK MODE  (Apple Mail, Outlook iOS)
    ══════════════════════════════════════════ */
    @media (prefers-color-scheme: dark) {{
      .email-wrapper {{ background:#1E2433 !important; }}
      .email-card    {{ background:#252D3D !important; box-shadow:0 8px 40px rgba(0,0,0,0.40) !important; }}
      .email-body    {{ background:#252D3D !important; }}
      .email-body p, .email-body div {{ color:#CBD5E1 !important; }}
      .email-heading {{ color:#93C5FD !important; }}
      .info-table    {{ background:#1E2433 !important; border-color:#334155 !important; }}
      .info-label    {{ color:#94A3B8 !important; background:#1A2232 !important; }}
      .info-value    {{ color:#E2E8F0 !important; border-color:#334155 !important; }}
      .email-footer  {{ background:#1A2232 !important; border-color:#334155 !important; }}
      .footer-text, .footer-copy {{ color:#64748B !important; }}
      .otp-digit     {{ background:#1E3A5F !important; border-color:#3B82F6 !important; color:#93C5FD !important; }}
    }}
  </style>

  <!--[if mso]>
  <style type="text/css">
    /* Outlook desktop: force 600px, ignore border-radius */
    .email-card {{ width:600px !important; }}
    .email-header, .email-body, .email-footer {{ padding-left:40px !important; padding-right:40px !important; }}
  </style>
  <![endif]-->
</head>

<body style="margin:0;padding:0;background:#EEF2F7;
             font-family:'Segoe UI',Helvetica,Arial,sans-serif;
             -webkit-font-smoothing:antialiased;">

<!-- Preheader (hidden preview text in inbox) -->
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;
            font-size:1px;color:#EEF2F7;line-height:1px;">
  Prahari — Invertis University Official Notification
  &nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
</div>

<table class="email-wrapper" width="100%" cellpadding="0" cellspacing="0"
       style="background:#EEF2F7;padding:32px 12px;">
<tr><td align="center">

  <!--[if mso]>
  <table width="600" cellpadding="0" cellspacing="0"><tr><td>
  <![endif]-->

  <div class="email-card"
       style="width:600px;max-width:100%;background:#ffffff;
              border-radius:16px;overflow:hidden;
              box-shadow:0 8px 40px rgba(0,0,0,0.10);margin:0 auto;">

    <!-- ═══════════ HEADER ═══════════ -->
    <div class="email-header"
         style="background:linear-gradient(135deg,#0F2557 0%,#1A56DB 100%);
                padding:36px 48px 28px;text-align:center;">

      <!-- Brand pill -->
      <div style="display:inline-block;background:rgba(255,255,255,0.12);
                  border-radius:12px;padding:10px 24px;margin-bottom:14px;">
        <span class="brand-name"
              style="font-size:24px;font-weight:800;color:#FFFFFF;
                     letter-spacing:2px;font-family:Georgia,'Times New Roman',serif;">
          Prahari
        </span>
      </div>

      <div class="brand-sub"
           style="font-size:11px;color:rgba(255,255,255,0.55);
                  letter-spacing:3px;text-transform:uppercase;">
        Invertis University &mdash; Attendance Management System
      </div>

      <!-- Gold accent line -->
      <div style="width:48px;height:3px;background:#F0A500;
                  border-radius:2px;margin:16px auto 0;"></div>
    </div>
    <!-- /header -->

    <!-- ═══════════ BODY ═══════════ -->
    <div class="email-body"
         style="padding:40px 48px 32px;background:#ffffff;">
      {content_html}
    </div>
    <!-- /body -->

    <!-- ═══════════ FOOTER ═══════════ -->
    <div class="email-footer"
         style="background:#F8FAFC;border-top:1px solid #E2E8F0;
                padding:24px 48px;text-align:center;">
      <p class="footer-text"
         style="margin:0 0 6px;font-size:12px;color:#94A3B8;line-height:1.7;">
        This is an automated message from
        <strong style="color:#64748B;">Prahari</strong>, the official Attendance
        Management System of<br/>
        <strong style="color:#64748B;">
          Invertis University, NH-530 Lucknow Road, Bareilly (U.P.)
        </strong>
      </p>
      <p class="footer-copy"
         style="margin:0;font-size:11px;color:#CBD5E1;">
        Please do not reply to this email &nbsp;&middot;&nbsp;
        &copy; {year} Invertis University
      </p>
    </div>
    <!-- /footer -->

  </div><!-- /email-card -->

  <!--[if mso]>
  </td></tr></table>
  <![endif]-->

</td></tr>
</table>

</body>
</html>"""


def _otp_box(otp_code: str) -> str:
    """Renders a styled OTP display box — responsive via CSS classes."""
    digits = ''.join(
        f'<span class="otp-digit" style="display:inline-block;width:44px;height:54px;'
        f'line-height:54px;background:#F0F7FF;border:2px solid #BFDBFE;'
        f'border-radius:10px;font-size:28px;font-weight:800;color:#1A56DB;'
        f'text-align:center;margin:0 4px;'
        f'font-family:\'Courier New\',Courier,monospace;">{d}</span>'
        for d in str(otp_code)
    )
    return f"""
    <div style="text-align:center;margin:28px 0;">
      <div style="display:inline-block;background:#EFF6FF;border:1px solid #BFDBFE;
                  border-radius:14px;padding:20px 28px;">
        <div style="font-size:11px;color:#6B7280;letter-spacing:2px;
                    text-transform:uppercase;margin-bottom:14px;">Your One-Time Password</div>
        <div>{digits}</div>
        <div style="font-size:12px;color:#EF4444;margin-top:14px;font-weight:600;"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Valid for 10 minutes only</div>
      </div>
    </div>"""


def _info_row(label: str, value: str) -> str:
    return f"""
    <tr>
      <td class="info-label" style="padding:10px 16px;font-size:13px;color:#6B7280;
                 font-weight:600;white-space:nowrap;width:40%;">{label}</td>
      <td class="info-value" style="padding:10px 16px;font-size:13px;color:#1E293B;
                 border-left:1px solid #E2E8F0;width:60%;">{value}</td>
    </tr>"""


def _info_table(rows: list) -> str:
    """rows = list of (label, value) tuples"""
    inner = ''.join(_info_row(l, v) for l, v in rows)
    return f"""
    <table class="info-table" cellpadding="0" cellspacing="0" width="100%"
           style="border:1px solid #E2E8F0;border-radius:10px;
                  overflow:hidden;margin:20px 0;background:#FAFAFA;">
      {inner}
    </table>"""


def _alert_badge(percentage: float) -> str:
    if percentage < 60:
        bg, color, label = '#FEE2E2', '#DC2626', '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> Critical'
    elif percentage < 75:
        bg, color, label = '#FEF3C7', '#D97706', '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#D97706" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> Warning'
    else:
        bg, color, label = '#DCFCE7', '#16A34A', '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#16A34A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> Safe'
    return f"""
    <div style="text-align:center;margin:24px 0;">
      <span style="display:inline-block;background:{bg};color:{color};
                   border-radius:999px;padding:10px 28px;
                   font-size:16px;font-weight:700;letter-spacing:0.5px;">
        {label} &nbsp;·&nbsp; {percentage:.1f}%
      </span>
    </div>"""


def send_professional_email(to: str, subject: str, heading: str, body: str,
                             footer: str = 'Prahari'):
    """
    Generic professional email — for custom messages.
    body = plain text, will be converted to paragraphs.
    """
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    paragraphs = ''.join(
        f'<p style="margin:0 0 14px;font-size:14px;color:#374151;line-height:1.8;">{p.strip()}</p>'
        for p in body.split('\n\n') if p.strip()
    )
    content = f"""
      <h2 style="margin:0 0 24px;font-size:20px;font-weight:700;
                 color:#0F2557;border-bottom:2px solid #EEF2F7;padding-bottom:14px;">
        {heading}
      </h2>
      {paragraphs}
    """
    html = _build_email_html(subject, content)
    text_body = f"{heading}\n\n{body}\n\n— Prahari, Invertis University"

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=f"Prahari — Invertis University <{settings.EMAIL_HOST_USER}>",
        to=[to],
    )
    email.attach_alternative(html, 'text/html')
    email.send(fail_silently=False)


# ─────────────────────────────────────────────
# Specific Email Templates
# ─────────────────────────────────────────────

def send_password_reset_otp_email(user_email: str, user_name: str, otp_code: str):
    """Beautifully formatted OTP email for password reset."""
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    content = f"""
      <h2 style="margin:0 0 6px;font-size:20px;font-weight:700;color:#0F2557;">
        Password Reset Request
      </h2>
      <p style="margin:0 0 24px;font-size:13px;color:#94A3B8;">
        Security notification for your Prahari account
      </p>

      <p style="margin:0 0 16px;font-size:14px;color:#374151;line-height:1.8;">
        Dear <strong>{user_name}</strong>,
      </p>
      <p style="margin:0 0 4px;font-size:14px;color:#374151;line-height:1.8;">
        We received a request to reset your Prahari account password.
        Use the OTP below to proceed. <strong>Do not share this code with anyone.</strong>
      </p>

      {_otp_box(otp_code)}

      <div style="background:#FFF7ED;border-left:4px solid #F0A500;
                  border-radius:0 8px 8px 0;padding:14px 18px;margin:20px 0;">
        <p style="margin:0;font-size:13px;color:#92400E;line-height:1.7;">
          <strong><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#92400E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> Didn't request this?</strong><br/>
          If you did not initiate this request, your account is still safe.
          Simply ignore this email — no changes will be made.
        </p>
      </div>
    """
    html = _build_email_html('Password Reset OTP — Prahari', content)
    text_body = (
        f"Dear {user_name},\n\n"
        f"Your password reset OTP is: {otp_code}\n\n"
        f"Valid for 10 minutes only. Do not share this with anyone.\n\n"
        f"— Prahari, Invertis University"
    )
    email = EmailMultiAlternatives(
        subject='Password Reset OTP — Prahari | Invertis University',
        body=text_body,
        from_email=f"Prahari — Invertis University <{settings.EMAIL_HOST_USER}>",
        to=[user_email],
    )
    email.attach_alternative(html, 'text/html')
    email.send(fail_silently=False)


def send_device_otp_email(user_email: str, user_name: str, otp_code: str):
    """OTP email for new device login verification."""
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    content = f"""
      <h2 style="margin:0 0 6px;font-size:20px;font-weight:700;color:#0F2557;">
        New Device Login Detected
      </h2>
      <p style="margin:0 0 24px;font-size:13px;color:#94A3B8;">
        Security alert for your Prahari account
      </p>

      <p style="margin:0 0 16px;font-size:14px;color:#374151;line-height:1.8;">
        Dear <strong>{user_name}</strong>,
      </p>
      <p style="margin:0 0 4px;font-size:14px;color:#374151;line-height:1.8;">
        A login attempt was made from a <strong>new or unrecognized device</strong>.
        To confirm it's you, please enter the OTP below on the login screen.
      </p>

      {_otp_box(otp_code)}

      <div style="background:#FEF2F2;border-left:4px solid #EF4444;
                  border-radius:0 8px 8px 0;padding:14px 18px;margin:20px 0;">
        <p style="margin:0;font-size:13px;color:#991B1B;line-height:1.7;">
          <strong><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#991B1B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> Not you?</strong><br/>
          If you did not attempt to log in, please change your password immediately
          and contact your institution's administration.
        </p>
      </div>
    """
    html = _build_email_html('New Device Login OTP — Prahari', content)
    text_body = (
        f"Dear {user_name},\n\n"
        f"New device login OTP: {otp_code}\n\n"
        f"Valid for 10 minutes. If this wasn't you, change your password immediately.\n\n"
        f"— Prahari, Invertis University"
    )
    email = EmailMultiAlternatives(
        subject='New Device Login OTP — Prahari | Invertis University',
        body=text_body,
        from_email=f"Prahari — Invertis University <{settings.EMAIL_HOST_USER}>",
        to=[user_email],
    )
    email.attach_alternative(html, 'text/html')
    email.send(fail_silently=False)


def send_attendance_alert_email(parent_email: str, student_name: str,
                                subject_name: str, percentage: float,
                                custom_message: str = ''):
    """Professional attendance alert email to parent/guardian."""
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    if percentage < 60:
        urgency = 'Immediate action is required.'
        status_note = 'critically low'
    elif percentage < 75:
        urgency = 'Please take prompt note of this.'
        status_note = 'below the required threshold'
    else:
        urgency = 'Please ensure attendance improves further.'
        status_note = 'below expected levels'

    content = f"""
      <h2 style="margin:0 0 6px;font-size:20px;font-weight:700;color:#0F2557;">
        Attendance Alert Notice
      </h2>
      <p style="margin:0 0 24px;font-size:13px;color:#94A3B8;">
        Official notification from Invertis University
      </p>

      <p style="margin:0 0 16px;font-size:14px;color:#374151;line-height:1.8;">
        Dear Parent / Guardian,
      </p>
      <p style="margin:0 0 20px;font-size:14px;color:#374151;line-height:1.8;">
        This is an official attendance notification regarding your ward's academic record.
        The attendance is currently <strong>{status_note}</strong>. {urgency}
      </p>

      {_alert_badge(percentage)}

      {_info_table([
          ('Student Name', student_name),
          ('Subject', subject_name),
          ('Attendance', f'{percentage:.1f}%'),
          ('Required Minimum', '75%'),
      ])}

      <div style="background:#EFF6FF;border-left:4px solid #1A56DB;
                  border-radius:0 8px 8px 0;padding:14px 18px;margin:20px 0;">
        <p style="margin:0;font-size:13px;color:#1E40AF;line-height:1.7;">
          <strong><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#1E40AF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> Institutional Policy</strong><br/>
          A minimum of <strong>75% attendance</strong> is mandatory for all students
          to be eligible to appear in semester examinations, as per university regulations.
        </p>
      </div>

      <p style="margin:16px 0 0;font-size:13px;color:#6B7280;line-height:1.8;">
        We request you to kindly encourage your ward to attend classes regularly.
        For any queries or if there are extenuating circumstances, please contact
        the respective faculty or the administration office at the earliest.
      </p>
      {f'<div style="background:#FFF7ED;border-left:4px solid #F0A500;border-radius:0 8px 8px 0;padding:14px 18px;margin:16px 0;"><p style="margin:0;font-size:13px;color:#92400E;line-height:1.7;"><strong>Message from Faculty:</strong><br/>' + custom_message + '</p></div>' if custom_message else ''}
    """
    html = _build_email_html(f'Attendance Alert — {student_name}', content)
    text_body = (
        f"Dear Parent/Guardian,\n\n"
        f"Attendance Alert for {student_name}\n"
        f"Subject: {subject_name}\n"
        f"Current Attendance: {percentage:.1f}% (Required: 75%)\n\n"
        f"Please ensure your ward attends classes regularly.\n\n"
        f"— Prahari, Invertis University"
    )
    email = EmailMultiAlternatives(
        subject=f'Attendance Alert — {student_name} | {subject_name} | Invertis University',
        body=text_body,
        from_email=f"Prahari — Invertis University <{settings.EMAIL_HOST_USER}>",
        to=[parent_email],
    )
    email.attach_alternative(html, 'text/html')
    email.send(fail_silently=False)


def send_attendance_request_email(teacher_email: str, student_name: str,
                                  subject_name: str, date: str,
                                  reason: str, action: str = 'submitted',
                                  remark: str = ''):
    """
    Email to teacher for attendance request events.
    action: 'submitted' | 'approved' | 'rejected'
    """
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    if action == 'approved':
        heading     = 'Attendance Request Approved ✓'
        badge_color = '#16A34A'
        badge_bg    = '#DCFCE7'
        badge_text  = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#16A34A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> Approved'
        note = 'The student\'s attendance has been marked as <strong>Present</strong> in the system.'
        subject_line = f'Request Approved — {student_name} | Prahari'
    elif action == 'rejected':
        heading     = 'Attendance Request Rejected ✗'
        badge_color = '#DC2626'
        badge_bg    = '#FEE2E2'
        badge_text  = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> Rejected'
        note = 'The request was not approved. Please contact the administrator for further details.'
        subject_line = f'Request Rejected — {student_name} | Prahari'
    else:
        heading     = 'Attendance Request Submitted'
        badge_color = '#1A56DB'
        badge_bg    = '#EFF6FF'
        badge_text  = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#1A56DB" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Pending Review'
        note = 'Your request has been forwarded to the administrator and will be reviewed shortly.'
        subject_line = f'Request Submitted — {student_name} | Prahari'

    remark_row = [('Admin Remark', remark or 'No remarks provided.')] if action != 'submitted' else []

    content = f"""
      <h2 style="margin:0 0 6px;font-size:20px;font-weight:700;color:#0F2557;">
        {heading}
      </h2>
      <p style="margin:0 0 24px;font-size:13px;color:#94A3B8;">
        Attendance request update — Prahari System
      </p>

      <div style="text-align:center;margin:0 0 24px;">
        <span style="display:inline-block;background:{badge_bg};color:{badge_color};
                     border-radius:999px;padding:8px 24px;
                     font-size:14px;font-weight:700;">
          {badge_text}
        </span>
      </div>

      {_info_table([
          ('Student', student_name),
          ('Subject', subject_name),
          ('Date', str(date)),
          ('Reason', reason),
      ] + remark_row)}

      <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;
                  padding:14px 18px;margin:20px 0;">
        <p style="margin:0;font-size:13px;color:#374151;line-height:1.7;">
          {note}
        </p>
      </div>
    """
    html = _build_email_html(subject_line, content)
    text_body = (
        f"{heading}\n\nStudent: {student_name}\nSubject: {subject_name}\n"
        f"Date: {date}\nReason: {reason}"
        + (f"\nAdmin Remark: {remark}" if remark else '')
        + f"\n\n— Prahari, Invertis University"
    )
    email = EmailMultiAlternatives(
        subject=subject_line,
        body=text_body,
        from_email=f"Prahari — Invertis University <{settings.EMAIL_HOST_USER}>",
        to=[teacher_email],
    )
    email.attach_alternative(html, 'text/html')
    email.send(fail_silently=False)


def send_device_reset_email(user_email: str, user_name: str):
    """Email sent when admin resets a student's device registration."""
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    content = f"""
      <h2 style="margin:0 0 6px;font-size:20px;font-weight:700;color:#0F2557;">
        Device Registration Reset
      </h2>
      <p style="margin:0 0 24px;font-size:13px;color:#94A3B8;">
        Security update for your Prahari account
      </p>

      <p style="margin:0 0 16px;font-size:14px;color:#374151;line-height:1.8;">
        Dear <strong>{user_name}</strong>,
      </p>
      <p style="margin:0 0 16px;font-size:14px;color:#374151;line-height:1.8;">
        Your registered device has been <strong>reset by the administrator</strong>.
        This is typically done when you have changed, lost, or replaced your device.
      </p>

      <div style="background:#EFF6FF;border-left:4px solid #1A56DB;
                  border-radius:0 8px 8px 0;padding:14px 18px;margin:20px 0;">
        <p style="margin:0;font-size:13px;color:#1E40AF;line-height:1.7;">
          <strong><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#1E40AF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg> What happens next?</strong><br/>
          The next time you log in to Prahari from a new device,
          that device will be automatically registered as your primary device.
        </p>
      </div>

      <div style="background:#FEF2F2;border-left:4px solid #EF4444;
                  border-radius:0 8px 8px 0;padding:14px 18px;margin:20px 0;">
        <p style="margin:0;font-size:13px;color:#991B1B;line-height:1.7;">
          <strong><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#991B1B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;display:inline-block;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> Not expecting this?</strong><br/>
          If you did not request a device reset, please contact your institution's
          administration immediately.
        </p>
      </div>
    """
    html = _build_email_html('Device Registration Reset — Prahari', content)
    text_body = (
        f"Dear {user_name},\n\n"
        f"Your device registration has been reset by the administrator.\n"
        f"Next login from a new device will register it automatically.\n\n"
        f"If you didn't request this, contact your institution immediately.\n\n"
        f"— Prahari, Invertis University"
    )
    email = EmailMultiAlternatives(
        subject='Device Registration Reset — Prahari | Invertis University',
        body=text_body,
        from_email=f"Prahari — Invertis University <{settings.EMAIL_HOST_USER}>",
        to=[user_email],
    )
    email.attach_alternative(html, 'text/html')
    email.send(fail_silently=False)


# ─────────────────────────────────────────────
# WhatsApp Helper
# ─────────────────────────────────────────────

def get_whatsapp_message_link(phone_number: str, student_name: str,
                               subject_name: str, percentage: float) -> str:
    """Returns a wa.me link with a professional WhatsApp attendance alert message."""
    import urllib.parse

    if percentage < 60:
        status_line = f"[ CRITICAL — {percentage:.1f}%*\nImmediate action is required."
    elif percentage < 75:
        status_line = f"[ LOW — {percentage:.1f}%*\nPlease take prompt steps to improve attendance."
    else:
        status_line = f"[ BELOW EXPECTED — {percentage:.1f}%*\nKindly ensure regular attendance."

    message = (
        f"[ Prahari — Attendance Alert ]\n"
        f"_Invertis University, Bareilly_\n"
        f"{'─' * 30}\n\n"
        f"Dear Parent / Guardian,\n\n"
        f"This is an official attendance notice regarding your ward:\n\n"
        f"Student: {student_name}\n"
        f"Subject: {subject_name}\n"
        f"Attendance Status:\n{status_line}\n\n"
        f"Note: As per university policy, a minimum of *75% attendance* is mandatory "
        f"for examination eligibility.\n\n"
        f"Kindly ensure your ward attends classes regularly. For queries, "
        f"please contact the institution directly.\n\n"
        f"{'─' * 30}\n"
        f"Prahari AMS · Invertis University_"
    )
    phone = phone_number.lstrip('0')
    return f"https://wa.me/91{phone}?text={urllib.parse.quote(message)}"