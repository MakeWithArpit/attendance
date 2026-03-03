"""
analytics/views.py
Analytics, Reports, Filtering, PDF/CSV, Parent Notifications
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404


from accounts.models import Student, Teacher
from academics.models import CourseRegistration, Subject, Branch
from attendance.models import Attendance, AttendanceSession
from attendance.utils import (
    get_student_attendance_summary,
    get_students_by_attendance_threshold,
    get_monthly_attendance_trend,
    calculate_attendance_percentage,
)
from accounts.permissions import IsTeacherOrAdmin, IsAdmin
from .utils import (
    generate_attendance_pdf,
    generate_attendance_csv,
    send_attendance_alert_email,
    get_whatsapp_message_link,
)


# ─────────────────────────────────────────────
# Attendance Analytics - Subject Wise (Teacher View)
# ─────────────────────────────────────────────
class SubjectWiseAnalyticsView(APIView):
    """
    GET /api/analytics/subject-wise/
    ?branch_id=1&semester=3&section=A&academic_year=2024-2025

    Returns: Each subject's average attendance %, total classes, students below threshold.
    """

    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        branch_id = request.query_params.get("branch_id")
        semester = request.query_params.get("semester")
        section = request.query_params.get("section")
        academic_year = request.query_params.get("academic_year")

        if not all([branch_id, semester, section, academic_year]):
            return Response(
                {"error": "branch_id, semester, section, academic_year are required"},
                status=400,
            )

        # Get all subjects for this branch/semester/section
        subject_ids = (
            CourseRegistration.objects.filter(
                branch_id=branch_id, semester=semester, section=section
            )
            .values_list("subject_id", flat=True)
            .distinct()
        )

        subjects = Subject.objects.filter(pk__in=subject_ids)

        analytics = []
        for subject in subjects:
            thresholds = get_students_by_attendance_threshold(
                subject.pk, int(semester), academic_year, section, branch_id
            )
            total_students = len(thresholds["above_75"]) + len(thresholds["below_75"])

            # Average attendance for this subject
            records = Attendance.objects.filter(
                subject=subject, semester=semester, academic_year=academic_year
            )
            total_present = records.filter(is_present=True).count()
            total_records = records.count()
            avg_pct = calculate_attendance_percentage(total_records, total_present)

            # Total classes held
            sessions = AttendanceSession.objects.filter(
                subject=subject,
                semester=semester,
                branch_id=branch_id,
                section=section,
                status="closed",
            ).count()

            analytics.append(
                {
                    "subject_code": subject.subject_code,
                    "subject_name": subject.subject_name,
                    "total_classes_held": sessions,
                    "total_students": total_students,
                    "average_pct": avg_pct,
                    "above_75_count": len(thresholds["above_75"]),
                    "below_75_count": len(thresholds["below_75"]),
                    "below_60_count": len(thresholds["below_60"]),
                    "below_50_count": len(thresholds["below_50"]),
                }
            )

        return Response({"analytics": analytics})


class MonthlyAttendanceTrendView(APIView):
    """
    GET /api/analytics/monthly-trend/?student_id=1&subject_id=2&academic_year=2024-2025
    """

    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        student_id = request.query_params.get("student_id")
        subject_id = request.query_params.get("subject_id")
        academic_year = request.query_params.get("academic_year")

        if not all([student_id, subject_id, academic_year]):
            return Response(
                {"error": "student_id, subject_id, academic_year required"}, status=400
            )

        trend = get_monthly_attendance_trend(
            str(student_id), str(subject_id), academic_year
        )
        return Response({"trend": trend})


class StudentAttendanceDetailView(APIView):
    """
    GET /api/analytics/student/<id>/?semester=3&academic_year=2024-2025
    Teacher sees a specific student's full attendance breakdown.
    """

    permission_classes = [IsTeacherOrAdmin]

    def get(self, request, pk):
        student = get_object_or_404(Student, pk=pk)
        semester = request.query_params.get("semester")
        academic_year = request.query_params.get("academic_year")

        if not semester or not academic_year:
            return Response(
                {"error": "semester and academic_year are required"}, status=400
            )

        summary = get_student_attendance_summary(
            student.pk, int(semester), academic_year
        )

        overall_total = sum(s["total_classes"] for s in summary)
        overall_attended = sum(s["attended"] for s in summary)
        overall_pct = calculate_attendance_percentage(overall_total, overall_attended)

        return Response(
            {
                "student": {
                    "id": student.pk,
                    "enrollment_number": student.enrollment_number,
                    "name": getattr(student, "profile", None) and student.profile.name,
                },
                "overall_percentage": overall_pct,
                "subject_wise": summary,
            }
        )


class ClassAttendanceThresholdView(APIView):
    """
    GET /api/analytics/thresholds/
    ?subject_id=1&branch_id=1&semester=3&section=A&academic_year=2024-2025

    Returns students categorised by attendance %.
    - above_75: safe
    - below_75: at risk
    - below_60: warning
    - below_50: critical
    """

    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        subject_id = request.query_params.get("subject_id")
        branch_id = request.query_params.get("branch_id")
        semester = request.query_params.get("semester")
        section = request.query_params.get("section")
        academic_year = request.query_params.get("academic_year")

        if not all([subject_id, branch_id, semester, section, academic_year]):
            return Response({"error": "All parameters are required"}, status=400)

        data = get_students_by_attendance_threshold(
            subject_id, int(semester), academic_year, section, branch_id
        )
        return Response(data)


# ─────────────────────────────────────────────
# Filtered Attendance Report (with PDF/CSV download)
# ─────────────────────────────────────────────
class AttendanceReportView(APIView):
    """
    GET /api/analytics/report/
    Params:
      - branch_id, semester, section, subject_id, academic_year (required)
      - min_percentage, max_percentage (optional filters)
      - format: json | pdf | csv (default: json)

    This powers the "filter + download" feature for teachers.
    """

    permission_classes = [IsTeacherOrAdmin]
    def get_format_suffix(self, **kwargs):
        return None

    def get(self, request):
        branch_id = request.query_params.get("branch_id")
        semester = request.query_params.get("semester")
        section = request.query_params.get("section")
        subject_id = request.query_params.get("subject_id")
        academic_year = request.query_params.get("academic_year")
        min_pct = float(request.query_params.get("min_percentage", 0))
        max_pct = float(request.query_params.get("max_percentage", 100))
        output_format = request.query_params.get("dl_format", "json")

        if not all([branch_id, semester, section, subject_id, academic_year]):
            return Response({"error": "All required parameters missing"}, status=400)

        # Fetch all students registered for this subject/branch/sem/section
        registrations = CourseRegistration.objects.filter(
            branch_id=branch_id,
            semester=semester,
            section=section,
            subject_id=subject_id,
        ).select_related("student__profile")

        subject = get_object_or_404(Subject, pk=subject_id)
        teacher = Teacher.objects.filter(user=request.user).first()

        student_data = []
        for reg in registrations:
            records = Attendance.objects.filter(
                student=reg.student,
                subject_id=subject_id,
                semester=semester,
                academic_year=academic_year,
            )
            total = records.count()
            attended = records.filter(is_present=True).count()
            pct = calculate_attendance_percentage(total, attended)

            # Apply percentage filter
            if not (min_pct <= pct <= max_pct):
                continue

            status = "safe" if pct >= 75 else ("warning" if pct >= 60 else "critical")
            profile = getattr(reg.student, "profile", None)

            student_data.append(
                {
                    "student_id": reg.student.pk,
                    "enrollment_number": reg.student.enrollment_number,
                    "roll_number": reg.student.roll_number,
                    "name": profile.name if profile else "",
                    "subject_code": subject.subject_code,
                    "subject_name": subject.subject_name,
                    "total_classes": total,
                    "attended": attended,
                    "percentage": pct,
                    "status": status,
                    "mobile": profile.mobile_number if profile else "",
                    "email": profile.email if profile else "",
                }
            )

        # Return in requested format
        if output_format == "csv":
            try:
                return generate_attendance_csv(
                    student_data, f"Attendance Report - {subject.subject_name}"
                )
            except Exception as e:
                import traceback; traceback.print_exc()
                return Response({"error": str(e)}, status=500)

        if output_format == "pdf":
            try:
                teacher_name = teacher.name if teacher else "Admin"
                return generate_attendance_pdf(
                    student_data,
                    report_title=f"Attendance Report - {subject.subject_name}",
                    teacher_name=teacher_name,
                    subject_name=subject.subject_name,
                    academic_year=academic_year,
                )
            except Exception as e:
                import traceback; traceback.print_exc()
                return Response({'error': str(e)}, status=500)

        # Default: JSON
        return Response(
            {
                "subject": subject.subject_name,
                "total": len(student_data),
                "filters": {"min_percentage": min_pct, "max_percentage": max_pct},
                "students": student_data,
            }
        )


# ─────────────────────────────────────────────
# Parent Notification
# ─────────────────────────────────────────────
class NotifyParentsView(APIView):
    """
    POST /api/analytics/notify-parents/
    Teacher sends email/WhatsApp to parents of low-attendance students.
    Body: {
        "student_ids": [1, 2, 3],
        "subject_id": 5,
        "academic_year": "2024-2025",
        "semester": 3,
        "method": "email" | "whatsapp"
    }
    """

    permission_classes = [IsTeacherOrAdmin]

    def post(self, request):
        student_ids = request.data.get("student_ids", [])
        subject_id = request.data.get("subject_id")
        academic_year = request.data.get("academic_year")
        semester = request.data.get("semester")
        method = request.data.get("method", "email")

        subject = get_object_or_404(Subject, pk=subject_id)
        results = {"success": [], "failed": [], "whatsapp_links": []}

        for sid in student_ids:
            try:
                student = Student.objects.select_related(
                    "profile", "parent_detail"
                ).get(pk=sid)
                profile = student.profile
                parent = getattr(student, "parent_detail", None)

                records = Attendance.objects.filter(
                    student=student,
                    subject=subject,
                    semester=semester,
                    academic_year=academic_year,
                )
                total = records.count()
                attended = records.filter(is_present=True).count()
                pct = calculate_attendance_percentage(total, attended)

                if method == "email" and parent and parent.father_email:
                    send_attendance_alert_email(
                        parent.father_email, profile.name, subject.subject_name, pct
                    )
                    results["success"].append(
                        {"student": profile.name, "email": parent.father_email}
                    )

                elif method == "whatsapp" and parent and parent.father_mobile:
                    link = get_whatsapp_message_link(
                        parent.father_mobile, profile.name, subject.subject_name, pct
                    )
                    results["whatsapp_links"].append(
                        {
                            "student": profile.name,
                            "mobile": parent.father_mobile,
                            "link": link,
                        }
                    )
                    results["success"].append({"student": profile.name})

            except Exception as e:
                results["failed"].append({"student_id": sid, "error": str(e)})

        return Response(results)


# ─────────────────────────────────────────────
# Admin: Edit Attendance Record
# ─────────────────────────────────────────────
class AdminAttendanceCorrectionView(APIView):
    """
    PATCH /api/analytics/admin/attendance/<attendance_id>/
    Admin can correct any attendance record.
    """

    permission_classes = [IsAdmin]

    def patch(self, request, pk):
        from attendance.models import Attendance

        record = get_object_or_404(Attendance, pk=pk)

        is_present = request.data.get("is_present")
        if is_present is not None:
            record.is_present = is_present
            record.save()

        from attendance.serializers import AttendanceSerializer

        return Response(AttendanceSerializer(record).data)
