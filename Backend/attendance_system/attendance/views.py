"""
attendance/views.py
All 4 attendance methods + Leave management
"""
import datetime
from django.utils import timezone
from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
import tempfile, os

from accounts.models import Student, Teacher
from academics.models import CourseRegistration, Subject
from .models import Attendance, AttendanceSession, LeaveRequest, AttendanceRequest
from .serializers import (
    AttendanceSerializer, AttendanceSessionSerializer,
    BulkAttendanceSerializer, LeaveRequestSerializer,
)
from .utils import (
    get_student_attendance_summary, verify_face,
    apply_approved_leave_to_attendance,
    verify_student_location,
)
from accounts.permissions import IsTeacherOrAdmin, IsStudent, IsAdmin


# ─────────────────────────────────────────────
# Step 1: Teacher starts an Attendance Session
# ─────────────────────────────────────────────
class StartAttendanceSessionView(APIView):
    """
    POST /api/attendance/sessions/start/
    Teacher picks: branch, semester, section, subject, date
    System creates a session → used for all 4 attendance methods

    Restrictions:
    - Teacher can only start a session for a subject assigned to them.
    - Only students enrolled in that subject are returned.

    GET /api/attendance/sessions/start/
    Returns only the subjects assigned to the requesting teacher
    (used by frontend to populate the subject dropdown).
    """
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        """Return only this teacher's assigned subjects."""
        teacher = get_object_or_404(Teacher, user=request.user)
        subjects = Subject.objects.filter(assigned_teacher=teacher)
        from academics.serializers import SubjectSerializer
        return Response({'subjects': SubjectSerializer(subjects, many=True).data})

    def post(self, request):
        teacher = get_object_or_404(Teacher, user=request.user)
        data    = request.data
        subject = get_object_or_404(Subject, pk=data.get('subject_id'))

        # ── Restriction: subject must be assigned to this teacher ──
        # Admin can bypass this check (they can start any session)
        if request.user.role == 'teacher':
            if subject.assigned_teacher_id != teacher.employee_id:
                return Response({
                    'error': (
                        f'You are not assigned to teach "{subject.subject_name}". '
                        'You can only start sessions for your own subjects.'
                    )
                }, status=403)

        session, created = AttendanceSession.objects.get_or_create(
            teacher=teacher,
            subject=subject,
            branch_id=data.get('branch_id'),
            semester=data.get('semester'),
            section=data.get('section'),
            date=data.get('date', datetime.date.today()),
            academic_year=data.get('academic_year'),
            defaults={
                'status':                'active',
                'facial_enabled':        data.get('facial_enabled', False),
                'geo_fencing_enabled':   data.get('geo_fencing_enabled', False),
                'campus_latitude':       data.get('campus_latitude'),
                'campus_longitude':      data.get('campus_longitude'),
                'allowed_radius_meters': data.get('allowed_radius_meters', 200),
            }
        )

        # ── Auto-expiry: set expires_at if duration_minutes provided ──
        duration_minutes = data.get('duration_minutes')
        if created and duration_minutes:
            try:
                mins = int(duration_minutes)
                if mins > 0:
                    session.duration_minutes = mins
                    session.expires_at = timezone.now() + datetime.timedelta(minutes=mins)
                    session.save(update_fields=['duration_minutes', 'expires_at'])
            except (ValueError, TypeError):
                pass

        # ── Load ONLY students enrolled in this specific subject ──
        # This naturally restricts to the right students regardless of branch/section params
        students = CourseRegistration.objects.filter(
            subject=subject,
            semester=data.get('semester'),
            section=data.get('section'),
            branch_id=data.get('branch_id'),
        ).select_related('student__profile')

        student_list = [{
            'student_id':        s.student.pk,
            'enrollment_number': s.student.enrollment_number,
            'roll_number':       s.student.roll_number,
            'name':              getattr(s.student, 'profile', None) and s.student.profile.name,
        } for s in students]

        return Response({
            'session':        AttendanceSessionSerializer(session).data,
            'students':       student_list,
            'total_students': len(student_list),
        }, status=201 if created else 200)


# ─────────────────────────────────────────────
# METHOD 1: Manual Attendance (Bulk)
# ─────────────────────────────────────────────
class BulkManualAttendanceView(APIView):
    """
    POST /api/attendance/mark/manual/
    Teacher submits attendance for all students at once.
    Body: {
        "session_id": 1,
        "academic_year": "2024-2025",
        "attendance": [
            {"student_id": 1, "is_present": true},
            {"student_id": 2, "is_present": false},
            ...
        ]
    }
    """
    permission_classes = [IsTeacherOrAdmin]

    def post(self, request):
        serializer = BulkAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = get_object_or_404(AttendanceSession, id=serializer.validated_data['session_id'])
        teacher = get_object_or_404(Teacher, user=request.user)
        academic_year = serializer.validated_data['academic_year']

        created_count = 0
        updated_count = 0

        for entry in serializer.validated_data['attendance']:
            obj, created = Attendance.objects.update_or_create(
                student_id=entry['student_id'],
                subject=session.subject,
                date=session.date,
                defaults={
                    'is_present':    entry['is_present'],
                    'day':           session.date.strftime('%A'),
                    'semester':      session.semester,
                    'academic_year': academic_year,
                    'marked_by':     teacher,
                    'method':        'manual',
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        session.status = 'closed'
        session.save()

        return Response({
            'message':  f'Attendance saved. {created_count} new, {updated_count} updated.',
            'session_id': session.id,
        })

# ─────────────────────────────────────────────
# METHOD 2: Facial Recognition Attendance
# ─────────────────────────────────────────────
class RegisterFaceView(APIView):
    """
    POST /api/attendance/face/register/
    Admin/Teacher uploads student's face photo for encoding.
    Body: multipart form with 'photo' file and 'student_id'
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        student_id = request.data.get('student_id')
        photo      = request.FILES.get('photo')

        if not photo:
            return Response({'error': 'Photo is required'}, status=400)

        student = get_object_or_404(Student, id=student_id)

        # Save temp file and encode
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            for chunk in photo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            from .utils import register_face_photo
            face_valid = register_face_photo(student, tmp_path)
            if not face_valid:
                return Response({'error': 'Image mein koi face detect nahi hua. Clear front-facing photo upload karo.'}, status=400)

            # Photo save karo — file upload karo registered_photo field mein
            import os as _os
            from django.core.files import File
            with open(tmp_path, 'rb') as f:
                filename = f"face_{student.enrollment_number}.jpg"
                student.registered_photo.save(filename, File(f), save=True)

            return Response({
                'message': f'Face successfully registered for {student.enrollment_number}.',
                'has_face_registered': True,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class ActiveSessionsForStudentView(APIView):
    """
    GET /api/attendance/sessions/active/
    Student apne enrolled subjects ki active sessions dekhta hai.
    Yahan se woh choose karta hai ki kis session mein face se attendance lagani hai.

    Response mein dikhta hai:
    - Session details
    - facial_enabled: True/False  ← sirf tab option dikhao jab True ho
    - geo_fencing_enabled: True/False
    """
    permission_classes = [IsStudent]

    def get(self, request):
        student = get_object_or_404(Student, user=request.user)

        # Student ke enrolled subjects nikalo
        from academics.models import CourseRegistration
        enrolled_subject_ids = CourseRegistration.objects.filter(
            student=student
        ).values_list('subject_id', flat=True)

        # Un subjects ki aaj ki active sessions nikalo
        import datetime
        active_sessions = AttendanceSession.objects.filter(
            subject_id__in=enrolled_subject_ids,
            status='active',
            date=datetime.date.today(),
        ).select_related('subject', 'teacher')

        sessions_data = []
        for s in active_sessions:
            # Kya student ne already attendance mark ki hai?
            already_marked = Attendance.objects.filter(
                student=student,
                subject=s.subject,
                date=s.date,
                is_present=True,
            ).exists()

            sessions_data.append({
                'session_id':          s.id,
                'subject_code':        s.subject.subject_code,
                'subject_name':        s.subject.subject_name,
                'teacher_name':        s.teacher.name,
                'date':                str(s.date),
                'facial_enabled':      s.facial_enabled,       # ← frontend isi se button dikhayega
                'geo_fencing_enabled': s.geo_fencing_enabled,
                'already_marked':      already_marked,
            })

        return Response({
            'active_sessions': sessions_data,
            'count':           len(sessions_data),
        })


class FacialAttendanceView(APIView):
    """
    POST /api/attendance/face/mark/
    Student apni selfie upload karta hai → face match hota hai → attendance mark hoti hai.

    Body (multipart form):
        photo      → selfie image file
        session_id → teacher ne jo session start kiya hai uska ID
        latitude   → student ki current latitude  (geo-fencing ke liye)
        longitude  → student ki current longitude (geo-fencing ke liye)

    Checks kiye jaate hain (sequence mein):
        1. Session active hai?
        2. Is session mein facial_enabled = True hai?
        3. Student is subject mein enrolled hai?
        4. Geo-fencing enable hai toh location campus ke andar hai?
        5. Student ka face registered hai?
        6. Uploaded selfie se face match hota hai?
    """
    permission_classes = [IsStudent]

    def post(self, request):
        session_id = request.data.get('session_id')
        photo      = request.FILES.get('photo')
        latitude   = request.data.get('latitude')
        longitude  = request.data.get('longitude')

        if not photo:
            return Response({'error': 'Photo zaruri hai.'}, status=400)
        if not session_id:
            return Response({'error': 'session_id zaruri hai.'}, status=400)

        student = get_object_or_404(Student, user=request.user)
        session = get_object_or_404(AttendanceSession, id=session_id, status='active')

        # ── Check 0a: Session expired? ──
        if session.is_expired:
            return Response(
                {'error': 'Session expired. Contact your teacher.'},
                status=400
            )

        # ── Check 0b: Device validation ──
        device_id = request.data.get('device_id', '').strip()
        if device_id:
            from accounts.models import DeviceToken
            tokens = DeviceToken.objects.filter(student=student)
            if tokens.exists() and not tokens.filter(device_id=device_id).exists():
                return Response({
                    'error': 'Unrecognized device. Contact admin to reset your device.',
                    'code':  'DEVICE_MISMATCH',
                }, status=403)

        # ── Check 1: Facial recognition is session mein allowed hai? ──
        if not session.facial_enabled:
            return Response({
                'error': 'Is session mein facial recognition se attendance allowed nahi hai. '
                         'Teacher se contact karo.'
            }, status=403)

        # ── Check 2: Student is subject mein enrolled hai? ──
        from academics.models import CourseRegistration
        enrolled = CourseRegistration.objects.filter(
            student=student,
            subject=session.subject,
            semester=session.semester,
        ).exists()
        if not enrolled:
            return Response({'error': 'Aap is subject mein enrolled nahi hain.'}, status=403)

        # ── Check 3: Geo-fencing (agar enable hai) ──
        location_verified = False
        if session.geo_fencing_enabled:
            if not latitude or not longitude:
                return Response({
                    'error': 'Is session mein location verification required hai. '
                             'Location permission allow karo aur dobara try karo.'
                }, status=400)

            geo_result = verify_student_location(session, float(latitude), float(longitude))
            if not geo_result['allowed']:
                return Response({
                    'error':            geo_result['message'],
                    'distance_meters':  geo_result['distance_meters'],
                    'allowed_radius':   geo_result['allowed_radius'],
                }, status=403)

            location_verified = True

        # ── Check 4: Face registered hai? ──
        if not student.registered_photo:
            return Response({
                'error': 'Aapka face registered nahi hai. Admin se contact karo.'
            }, status=400)

        # ── Check 5: Face match ──
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            for chunk in photo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            match = verify_face(student, tmp_path)
            if not match:
                return Response({
                    'error': 'Face match nahi hua. Dobara try karo ya teacher se contact karo.'
                }, status=403)

            # ── Sab checks pass — Attendance mark karo ──
            attendance, created = Attendance.objects.get_or_create(
                student=student,
                subject=session.subject,
                date=session.date,
                defaults={
                    'is_present':         True,
                    'day':                session.date.strftime('%A'),
                    'semester':           session.semester,
                    'academic_year':      session.academic_year,
                    'marked_by':          session.teacher,
                    'method':             'facial',
                    'latitude':           latitude,
                    'longitude':          longitude,
                    'location_verified':  location_verified,
                }
            )
            if not created and not attendance.is_present:
                attendance.is_present        = True
                attendance.method            = 'facial'
                attendance.latitude          = latitude
                attendance.longitude         = longitude
                attendance.location_verified = location_verified
                attendance.save()

            return Response({
                'message':          'Attendance successfully mark ho gayi — Face Recognition',
                'subject':          session.subject.subject_name,
                'date':             str(session.date),
                'location_verified': location_verified,
            })

        except ImportError as e:
            return Response({'error': str(e)}, status=500)
        finally:
            os.unlink(tmp_path)


# ─────────────────────────────────────────────
# METHOD 4: RFID Attendance
# ─────────────────────────────────────────────
class RFIDAttendanceView(APIView):
    """
    POST /api/attendance/rfid/mark/
    RFID reader app sends: { "rfid_number": "xxx", "session_id": 1 }
    Server identifies student → marks present.
    This API is called by your RFID reader application.
    """
    permission_classes = [IsTeacherOrAdmin]

    def post(self, request):
        rfid_number = request.data.get('rfid_number')
        session_id  = request.data.get('session_id')

        if not rfid_number:
            return Response({'error': 'RFID number is required'}, status=400)

        student = Student.objects.filter(rfid_number=rfid_number).first()
        if not student:
            return Response({'error': f'No student found with RFID: {rfid_number}'}, status=404)

        session = get_object_or_404(AttendanceSession, id=session_id, status='active')
        teacher = get_object_or_404(Teacher, user=request.user)

        attendance, created = Attendance.objects.get_or_create(
            student=student,
            subject=session.subject,
            date=session.date,
            defaults={
                'is_present':    True,
                'day':           session.date.strftime('%A'),
                'semester':      session.semester,
                'academic_year': session.academic_year,
                'marked_by':     teacher,
                'method':        'rfid',
            }
        )

        return Response({
            'message':           'Attendance marked via RFID',
            'student_name':      getattr(student, 'profile', None) and student.profile.name,
            'enrollment_number': student.enrollment_number,
            'subject':           session.subject.subject_name,
        })


class BulkRFIDAttendanceView(APIView):
    """
    POST /api/attendance/rfid/bulk/
    RFID reader sends multiple RFID numbers at once.
    Body: { "session_id": 1, "rfid_numbers": ["abc", "def", ...], "academic_year": "2024-2025" }
    """
    permission_classes = [IsTeacherOrAdmin]

    def post(self, request):
        session_id   = request.data.get('session_id')
        rfid_numbers = request.data.get('rfid_numbers', [])
        academic_year = request.data.get('academic_year')

        session = get_object_or_404(AttendanceSession, id=session_id, status='active')
        teacher = get_object_or_404(Teacher, user=request.user)

        results = {'marked': [], 'not_found': []}

        for rfid in rfid_numbers:
            student = Student.objects.filter(rfid_number=rfid).first()
            if not student:
                results['not_found'].append(rfid)
                continue

            Attendance.objects.update_or_create(
                student=student,
                subject=session.subject,
                date=session.date,
                defaults={
                    'is_present':    True,
                    'day':           session.date.strftime('%A'),
                    'semester':      session.semester,
                    'academic_year': academic_year or session.academic_year,
                    'marked_by':     teacher,
                    'method':        'rfid',
                }
            )
            results['marked'].append(student.enrollment_number)

        return Response(results)


# ─────────────────────────────────────────────
# Attendance List / Edit (Admin)
# ─────────────────────────────────────────────
class AttendanceListView(generics.ListAPIView):
    """
    GET /api/attendance/?student=1&subject=2&date=2024-01-15
    """
    serializer_class = AttendanceSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'subject', 'date', 'semester', 'academic_year', 'is_present']

    def get_queryset(self):
        return Attendance.objects.select_related(
            'student__profile', 'subject', 'marked_by'
        ).all()


class AttendanceEditView(APIView):
    """
    PATCH /api/attendance/edit/
    Body: { "student_id": "BCS2024001", "date": "2024-11-15", "subject_id": "CS301", "is_present": true }
    """
    permission_classes = [IsAdmin]
    def patch(self, request):
        student_id = request.data.get('student_id')
        date       = request.data.get('date')
        subject_id = request.data.get('subject_id')
        is_present = request.data.get('is_present')

        if not all([student_id, date, subject_id]):
            return Response(
                {'error': 'student_id, date, subject_id — teeno zaruri hain'},
                status=400
            )

        record = Attendance.objects.filter(
            student_id=student_id,
            date=date,
            subject_id=subject_id,
        ).first()

        if not record:
            return Response(
                {'error': f'Record nahi mila: student={student_id}, date={date}, subject={subject_id}'},
                status=404
            )

        if is_present is not None:
            record.is_present = is_present
            record.save()

        return Response(AttendanceSerializer(record).data)


# ─────────────────────────────────────────────
# Student's Own Attendance
# ─────────────────────────────────────────────
class StudentAttendanceSummaryView(APIView):
    """
    GET /api/attendance/my-summary/?semester=3&academic_year=2024-2025
    Student views their own subject-wise attendance.
    """
    permission_classes = [IsStudent]

    def get(self, request):
        student   = get_object_or_404(Student, user=request.user)
        semester  = request.query_params.get('semester')
        academic_year = request.query_params.get('academic_year')

        if not semester or not academic_year:
            return Response({'error': 'semester and academic_year are required'}, status=400)

        summary = get_student_attendance_summary(student.pk, int(semester), academic_year)
        return Response({'summary': summary})


# ─────────────────────────────────────────────
# Leave Request Views
# ─────────────────────────────────────────────
class LeaveRequestListCreateView(generics.ListCreateAPIView):
    """
    Student: POST to apply for leave
    Teacher/Admin: GET to see all leave requests
    Supports ?status=pending|approved|rejected filter
    """
    serializer_class = LeaveRequestSerializer
    filter_backends  = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering_fields  = ['applied_on']
    ordering         = ['-applied_on']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsStudent()]
        if self.request.user.role == 'student':
            return [IsStudent()]
        return [IsTeacherOrAdmin()]

    def get_queryset(self):
        qs = LeaveRequest.objects.select_related('student__profile', 'reviewed_by').all()
        # Student sees only their own leaves
        if self.request.user.role == 'student':
            student = get_object_or_404(Student, user=self.request.user)
            return qs.filter(student=student)
        return qs

    def perform_create(self, serializer):
        student = get_object_or_404(Student, user=self.request.user)
        serializer.save(student=student)


class LeaveRequestActionView(APIView):
    """
    POST /api/attendance/leaves/<id>/action/
    Teacher approves or rejects leave.
    Body: { "action": "approved" | "rejected", "remarks": "..." }
    """
    permission_classes = [IsTeacherOrAdmin]

    def post(self, request, pk):
        leave   = get_object_or_404(LeaveRequest, id=pk)
        action  = request.data.get('action')
        remarks = request.data.get('remarks', '')

        if action not in ['approved', 'rejected']:
            return Response({'error': 'Invalid action. Use approved or rejected'}, status=400)

        # teacher = get_object_or_404(Teacher, user=request.user)
        teacher = Teacher.objects.filter(user=request.user).first()

        leave.status      = action
        leave.reviewed_by = teacher
        leave.reviewed_on = timezone.now()
        leave.remarks     = remarks
        leave.save()

        # If approved, update attendance records
        if action == 'approved':
            updated = apply_approved_leave_to_attendance(leave)
            return Response({
                'message':          f'Leave approved. {updated} attendance records updated.',
                'leave_id':         leave.id,
            })

        return Response({'message': f'Leave {action} successfully', 'leave_id': leave.id})


# ─────────────────────────────────────────────
# Teacher Dashboard Summary
# ─────────────────────────────────────────────
class TeacherDashboardView(APIView):
    """
    GET /api/attendance/dashboard/teacher/
    Teacher's dashboard summary:
    - Total lectures taken
    - Pending leaves count
    - Students below 75%, 60%, 50% per subject
    """
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        teacher = get_object_or_404(Teacher, user=request.user)
        academic_year = request.query_params.get('academic_year', '')

        # Total sessions taken by this teacher
        sessions_taken = AttendanceSession.objects.filter(
            teacher=teacher, status='closed'
        ).count()

        # Pending leaves
        pending_leaves = LeaveRequest.objects.filter(
            status='pending'
        ).count()

        # Subject-wise class stats
        subjects = teacher.subjects.all()
        subject_stats = []
        for subject in subjects:
            total_classes = AttendanceSession.objects.filter(
                teacher=teacher, subject=subject, status='closed'
            ).count()

            # Students below 75 in this subject
            from academics.models import CourseRegistration
            regs = CourseRegistration.objects.filter(subject=subject).count()

            subject_stats.append({
                'subject_code':  subject.subject_code,
                'subject_name':  subject.subject_name,
                'total_classes': total_classes,
                'enrolled':      regs,
            })

        return Response({
            'total_sessions_taken': sessions_taken,
            'pending_leaves':       pending_leaves,
            'subjects':             subject_stats,
        })


# ─────────────────────────────────────────────
# Attendance Requests (Teacher → Admin)
# ─────────────────────────────────────────────
class TeacherAttendanceRequestView(APIView):
    """
    Teacher creates an attendance request for a student who could not mark
    attendance via face/RFID during the session.
    GET  → list my submitted requests (with admin remark visible)
    POST → submit a new request
    """
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        teacher = get_object_or_404(Teacher, user=request.user)
        requests = AttendanceRequest.objects.filter(
            teacher=teacher
        ).select_related(
            'student__profile', 'session__subject'
        ).order_by('-created_at')

        data = [{
            'id':           req.id,
            'student_id':   req.student_id,
            'student_name': getattr(req.student, 'profile', None) and req.student.profile.name,
            'session_id':   req.session_id,
            'subject':      req.session.subject.subject_name if req.session else '',
            'date':         req.session.date.isoformat() if req.session else '',
            'reason':       req.reason,
            'status':       req.status,
            'admin_remark': req.admin_remark,
            'created_at':   req.created_at.isoformat(),
            'resolved_at':  req.resolved_at.isoformat() if req.resolved_at else None,
        } for req in requests]

        return Response({'requests': data})

    def post(self, request):
        teacher    = get_object_or_404(Teacher, user=request.user)
        student_id = request.data.get('student_id')
        session_id = request.data.get('session_id')
        reason     = request.data.get('reason', '').strip()

        if not student_id or not session_id or not reason:
            return Response(
                {'error': 'student_id, session_id, and reason are all required'},
                status=400
            )

        from accounts.models import Student
        student = get_object_or_404(Student, pk=student_id)
        session = get_object_or_404(AttendanceSession, pk=session_id)

        if AttendanceRequest.objects.filter(session=session, student=student).exists():
            return Response(
                {'error': 'A request already exists for this student & session'},
                status=400
            )

        req = AttendanceRequest.objects.create(
            session=session, student=student, teacher=teacher, reason=reason
        )

        try:
            from analytics.utils import send_professional_email
            send_professional_email(
                to=teacher.email,
                subject='Attendance Request Submitted — AttendX',
                heading='Request Submitted Successfully',
                body=(
                    f"Your attendance request has been submitted to the administrator.\n\n"
                    f"Student: {student.profile.name if hasattr(student, 'profile') else student_id}\n"
                    f"Session: {session.subject.subject_name} | {session.date}\n"
                    f"Reason: {reason}\n\n"
                    f"You will be notified once the admin reviews your request."
                ),
                footer='AttendX Attendance Management System',
            )
        except Exception:
            pass

        return Response({
            'message': 'Request submitted. Admin will be notified.',
            'request_id': req.id,
        }, status=201)


class AdminAttendanceRequestView(APIView):
    """
    Admin lists and resolves attendance requests from teachers.
    GET        → list requests filtered by status (default: pending)
    PATCH /<pk>→ approve or reject a specific request
    """
    permission_classes = [IsAdmin]

    def get(self, request):
        status_filter = request.query_params.get('status', 'pending')
        requests = AttendanceRequest.objects.filter(
            status=status_filter
        ).select_related(
            'student__profile', 'session__subject', 'teacher'
        ).order_by('-created_at')

        data = [{
            'id':           req.id,
            'student_id':   req.student_id,
            'student_name': getattr(req.student, 'profile', None) and req.student.profile.name,
            'teacher_name': req.teacher.name if req.teacher else '',
            'teacher_id':   req.teacher.employee_id if req.teacher else '',
            'session_id':   req.session_id,
            'subject':      req.session.subject.subject_name if req.session else '',
            'date':         req.session.date.isoformat() if req.session else '',
            'reason':       req.reason,
            'status':       req.status,
            'admin_remark': req.admin_remark,
            'created_at':   req.created_at.isoformat(),
        } for req in requests]

        return Response({'requests': data, 'total': len(data)})

    def patch(self, request, pk):
        req    = get_object_or_404(AttendanceRequest, pk=pk)
        action = request.data.get('action')
        remark = request.data.get('remark', '').strip()

        if action not in ('approved', 'rejected'):
            return Response({'error': "action must be 'approved' or 'rejected'"}, status=400)

        req.status       = action
        req.admin_remark = remark
        req.resolved_at  = timezone.now()
        req.resolved_by  = request.user
        req.save()

        if action == 'approved':
            Attendance.objects.update_or_create(
                student=req.student,
                subject=req.session.subject,
                date=req.session.date,
                defaults={
                    'is_present':        True,
                    'day':               req.session.date.strftime('%A'),
                    'semester':          req.session.semester,
                    'academic_year':     req.session.academic_year,
                    'marked_by':         req.teacher,
                    'method':            'manual',
                    'location_verified': False,
                }
            )

        try:
            from analytics.utils import send_professional_email
            status_word  = 'Approved ✓' if action == 'approved' else 'Rejected ✗'
            student_name = getattr(req.student, 'profile', None) and req.student.profile.name
            send_professional_email(
                to=req.teacher.email,
                subject=f'Attendance Request {status_word} — AttendX',
                heading=f'Your Attendance Request Has Been {status_word}',
                body=(
                    f"Your attendance request has been reviewed by the administrator.\n\n"
                    f"Student: {student_name or req.student_id}\n"
                    f"Subject: {req.session.subject.subject_name}\n"
                    f"Date: {req.session.date}\n"
                    f"Decision: {status_word}\n"
                    f"Admin Remark: {remark or 'No remarks provided.'}\n\n"
                    + (
                        "The attendance has been marked as Present in the system."
                        if action == 'approved' else
                        "The request was not approved. Please contact the administrator for further details."
                    )
                ),
                footer='AttendX Attendance Management System',
            )
        except Exception:
            pass

        return Response({
            'message':           f'Request {action} successfully.',
            'request_id':        req.id,
            'attendance_marked': action == 'approved',
        })