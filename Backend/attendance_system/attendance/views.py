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


def _auto_academic_year() -> str:
    """March 2026 → '2025-2026', August 2026 → '2026-2027'"""
    now = datetime.date.today()
    y   = now.year
    return f"{y}-{y+1}" if now.month >= 7 else f"{y-1}-{y}"


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
        """Return this teacher's assigned subjects + current active session (if any)."""
        teacher = get_object_or_404(Teacher, user=request.user)
        subjects = Subject.objects.filter(assigned_teacher=teacher)
        from academics.serializers import SubjectSerializer

        # Check for any active non-expired session for this teacher
        active_session = None
        active_students = []
        qs = AttendanceSession.objects.filter(
            teacher=teacher, status='active'
        ).select_related('subject').order_by('-created_at').first()

        if qs:
            # Expired session — still show it as-is, don't silently close it.
            # Teacher can close it manually via End Session button.
            active_session = AttendanceSessionSerializer(qs).data
            # Also return enrolled students for this active session
            students = CourseRegistration.objects.filter(
                subject=qs.subject,
                semester=qs.semester,
                section=qs.section,
                branch_id=qs.branch_id,
            ).select_related('student__profile', 'student__parent_detail')

            def _fname(s):
                try: return s.parent_detail.father_name or ''
                except Exception: return ''

            active_students = [{
                'student_id':        s.student.pk,
                'enrollment_number': s.student.enrollment_number,
                'roll_number':       s.student.roll_number,
                'name':              getattr(s.student, 'profile', None) and s.student.profile.name,
                'father_name':       _fname(s.student),
            } for s in students]

        return Response({
            'subjects':        SubjectSerializer(subjects, many=True).data,
            'active_session':  active_session,
            'students':        active_students,
            'total_students':  len(active_students),
        })

    def post(self, request):
        teacher = get_object_or_404(Teacher, user=request.user)
        data    = request.data
        subject = get_object_or_404(Subject, pk=data.get('subject_id'))

        # ── Block if this teacher already has an active session ──
        existing = AttendanceSession.objects.filter(
            teacher=teacher, status='active'
        ).select_related('subject').first()
        if existing:
            return Response({
                'error': (
                    f'Aapki "{existing.subject.subject_name}" ki session abhi bhi active hai '
                    f'(ID: {existing.id}). Pehle us session ko End Session se close karo, tabhi nayi session start kar sakte ho.'
                ),
                'active_session': AttendanceSessionSerializer(existing).data,
            }, status=400)

        # ── Restriction: subject must be assigned to this teacher ──
        if request.user.role == 'teacher':
            if subject.assigned_teacher_id != teacher.employee_id:
                return Response({
                    'error': (
                        f'You are not assigned to teach "{subject.subject_name}". '
                        'You can only start sessions for your own subjects.'
                    )
                }, status=403)

        session = AttendanceSession.objects.create(
            teacher=teacher,
            subject=subject,
            branch_id=data.get('branch_id'),
            semester=data.get('semester'),
            section=data.get('section'),
            date=data.get('date', datetime.date.today()),
            academic_year=data.get('academic_year') or _auto_academic_year(),
            status='active',
            facial_enabled=data.get('facial_enabled', False),
            geo_fencing_enabled=data.get('geo_fencing_enabled', False),
            campus_latitude=data.get('campus_latitude'),
            campus_longitude=data.get('campus_longitude'),
            allowed_radius_meters=data.get('allowed_radius_meters', 200),
        )

        # ── Auto-expiry: set expires_at if duration_minutes provided ──
        duration_minutes = data.get('duration_minutes')
        if duration_minutes:
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
        ).select_related('student__profile', 'student__parent_detail')

        def get_father_name(student):
            try:
                return student.parent_detail.father_name or ''
            except Exception:
                return ''

        student_list = [{
            'student_id':        s.student.pk,
            'enrollment_number': s.student.enrollment_number,
            'roll_number':       s.student.roll_number,
            'name':              getattr(s.student, 'profile', None) and s.student.profile.name,
            'father_name':       get_father_name(s.student),
        } for s in students]

        return Response({
            'session':        AttendanceSessionSerializer(session).data,
            'students':       student_list,
            'total_students': len(student_list),
        }, status=201)


class CloseSessionView(APIView):
    """
    PATCH /api/attendance/sessions/<id>/close/
    Teacher manually closes an active session.
    """
    permission_classes = [IsTeacherOrAdmin]

    def patch(self, request, pk):
        teacher = get_object_or_404(Teacher, user=request.user)
        session = get_object_or_404(AttendanceSession, pk=pk, teacher=teacher)
        if session.status == 'closed':
            return Response({'error': 'Session already closed.'}, status=400)
        session.status = 'closed'
        session.save(update_fields=['status'])

        # ── BUG 2 FIX: Create absent records for students who didn't attend ──
        # Without this, facial/rfid sessions leave absent students with 0 records,
        # making total_classes=0 for them → wrong percentage in "My Attendance".
        from academics.models import CourseRegistration
        enrolled_students = CourseRegistration.objects.filter(
            subject=session.subject,
            semester=session.semester,
            section=session.section,
            branch_id=session.branch_id,
        ).values_list('student_id', flat=True)

        # Find students who already have a record for this session
        already_marked_ids = set(
            Attendance.objects.filter(session=session).values_list('student_id', flat=True)
        )

        absent_records = []
        for sid in enrolled_students:
            if sid not in already_marked_ids:
                absent_records.append(Attendance(
                    student_id=sid,
                    subject=session.subject,
                    date=session.date,
                    day=session.date.strftime('%A'),
                    semester=session.semester,
                    academic_year=session.academic_year,
                    is_present=False,
                    method='manual',
                    session=session,
                ))
        if absent_records:
            Attendance.objects.bulk_create(absent_records, ignore_conflicts=True)

        return Response({'message': 'Session closed successfully.', 'session_id': session.id})


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
                session=session,   # ← include session in lookup so two sessions on same date don't collide
                defaults={
                    'is_present':    entry['is_present'],
                    'day':           session.date.strftime('%A'),
                    'semester':      session.semester,
                    'academic_year': academic_year or session.academic_year or _auto_academic_year(),
                    'marked_by':     teacher,
                    'method':        'manual',
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        # Session band mat karo — teacher manually End Session button se close karega.
        # (Pehle yahan session.status='closed' tha — yahi "auto-close" bug tha)

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

        student = get_object_or_404(Student, pk=student_id)

        # Save temp file and encode
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            for chunk in photo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            from .utils import register_face_photo
            face_valid = register_face_photo(student, tmp_path)
            if not face_valid:
                return Response({'error': 'No face detected in the image. Please upload a clear front-facing photo.'}, status=400)

            # Save photo — store in the registered_photo field
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
    The student selects a session and marks attendance via face recognition.

    Response includes:
    - Session details
    - facial_enabled: True/False  ← show face option only when True
    - geo_fencing_enabled: True/False
    """
    permission_classes = [IsStudent]

    def get(self, request):
        student = get_object_or_404(Student, user=request.user)

        from academics.models import CourseRegistration
        from django.utils import timezone as tz
        import datetime

        # Today's date in IST (works correctly with USE_TZ=True)
        today = tz.localdate()

        # Fetch student's enrolled subjects and their branch/section/semester
        enrollments = CourseRegistration.objects.filter(
            student=student
        ).select_related('branch')

        enrolled_subject_ids = enrollments.values_list('subject_id', flat=True)

        # Extract branch, section, semester from the student's profile
        # (a session should only be visible to students in the matching section)
        try:
            profile  = student.profile
            s_branch  = profile.branch_id      # branch_code string
            s_section = profile.section.strip().upper() if profile.section else None
            s_semester = profile.current_semester
        except Exception:
            s_branch = s_section = s_semester = None

        # Base filter: today's active sessions for enrolled subjects
        session_filter = dict(
            subject_id__in=enrolled_subject_ids,
            status='active',
            date=today,
        )

        # If the student has a profile with section/branch/semester, match the session accordingly
        # This ensures a Section D student only sees Section D sessions
        if s_branch:
            session_filter['branch_id'] = s_branch
        if s_section:
            session_filter['section'] = s_section
        if s_semester:
            session_filter['semester'] = s_semester

        active_sessions = AttendanceSession.objects.filter(
            **session_filter
        ).select_related('subject', 'teacher')

        sessions_data = []
        for s in active_sessions:
            # Skip expired sessions (those with a duration_minutes limit)
            if s.is_expired:
                continue

            # Has the student already marked attendance for this session?
            # ONLY check session FK — no fallback. Every record now has session set.
            # Fallback was the root cause of false "Teacher ne Marked":
            #   old get_or_create used student+subject+date as lookup (no session FK),
            #   so stale records with session=None, method='manual' (default) were matching.
            att_record = Attendance.objects.filter(
                student=student,
                session=s,
                is_present=True,
            ).values('method').first()

            already_marked = att_record is not None
            marked_method  = att_record['method'] if att_record else None

            sessions_data.append({
                'session_id':          s.id,
                'subject_code':        s.subject.subject_code,
                'subject_name':        s.subject.subject_name,
                'teacher_name':        s.teacher.name,
                'date':                str(s.date),
                'facial_enabled':      s.facial_enabled,
                'geo_fencing_enabled':    s.geo_fencing_enabled,
                'campus_latitude':        float(s.campus_latitude)  if s.campus_latitude  else None,
                'campus_longitude':       float(s.campus_longitude) if s.campus_longitude else None,
                'allowed_radius_meters':  s.allowed_radius_meters,
                'already_marked':         already_marked,
                'marked_method':          marked_method,
                'expires_at':             s.expires_at.isoformat() if s.expires_at else None,
                'duration_minutes':       s.duration_minutes,
                'has_face_registered':    bool(student.registered_photo),
            })

        return Response({
            'active_sessions': sessions_data,
            'count':           len(sessions_data),
        })


class FacialAttendanceView(APIView):
    """
    POST /api/attendance/face/mark/
    Student uploads a selfie → face is matched → attendance is recorded.

    Body (multipart form):
        photo      → selfie image file
        session_id → the ID of the session started by the teacher
        latitude   → student ki current latitude  (geo-fencing ke liye)
        longitude  → student ki current longitude (geo-fencing ke liye)

    The following checks are performed in sequence:
        1. Session active hai?
        2. Is session mein facial_enabled = True hai?
        3. Student is subject mein enrolled hai?
        4. Geo-fencing enable hai toh location campus ke andar hai?
        5. Student ka face registered hai?
        6. Uploaded selfie se face match hota hai?
    """
    permission_classes = [IsStudent]

    def post(self, request):
        session_id     = request.data.get('session_id')
        photo          = request.FILES.get('photo')
        latitude       = request.data.get('latitude')
        longitude      = request.data.get('longitude')
        phone_detected = str(request.data.get('phone_detected', 'false')).lower() == 'true'

        if not photo:
            return Response({'error': 'Photo is required.'}, status=400)
        if not session_id:
            return Response({'error': 'session_id is required.'}, status=400)

        student = get_object_or_404(Student, user=request.user)
        session = get_object_or_404(AttendanceSession, id=session_id, status='active')

        # ── Check 0a: Session expired? ──
        if session.is_expired:
            return Response(
                {'error': 'Session expired. Contact your teacher.'},
                status=400
            )

        # ── Check 0b: Phone detected → mark absent ──
        if phone_detected:
            Attendance.objects.update_or_create(
                student=student,
                subject=session.subject,
                date=session.date,
                session=session,          # ← session FK in lookup — stale records se protect
                defaults={
                    'is_present':    False,
                    'day':           session.date.strftime('%A'),
                    'semester':      session.semester,
                    'academic_year': session.academic_year,
                    'marked_by':     session.teacher,
                    'method':        'facial',
                }
            )
            return Response({
                'error': 'Mobile phone detected in camera. Attendance marked ABSENT as per anti-proxy policy.',
                'code':  'PHONE_DETECTED',
                'marked_absent': True,
            }, status=403)

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

        # ── Check 1: Is facial recognition enabled for this session? ──
        if not session.facial_enabled:
            return Response({
                'error': 'Is session mein facial recognition se attendance allowed nahi hai. '
                         'Teacher se contact karo.'
            }, status=403)

        # ── Check 2: Is the student enrolled in this subject? ──
        from academics.models import CourseRegistration
        enrolled = CourseRegistration.objects.filter(
            student=student,
            subject=session.subject,
            semester=session.semester,
        ).exists()
        if not enrolled:
            return Response({'error': 'You are not enrolled in this subject.'}, status=403)

        # ── Check 3: Geo-fencing check (if enabled) ──
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

        # ── Check 4: Does the student have a registered face photo? ──
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

            # ── All checks passed — mark attendance ──
            # Use update_or_create with session in lookup — prevents stale records
            # (old get_or_create with only student+subject+date was matching records
            #  with session=None and method='manual' default, causing false "Teacher ne Marked")
            attendance, created = Attendance.objects.update_or_create(
                student=student,
                subject=session.subject,
                date=session.date,
                session=session,          # ← session FK in lookup — KEY FIX
                defaults={
                    'is_present':         True,
                    'day':                session.date.strftime('%A'),
                    'semester':           session.semester,
                    'academic_year':      session.academic_year or _auto_academic_year(),
                    'marked_by':          session.teacher,
                    'method':             'facial',
                    'latitude':           latitude,
                    'longitude':          longitude,
                    'location_verified':  location_verified,
                }
            )

            return Response({
                'message':          'Attendance successfully mark ho gayi — Face Recognition',
                'subject':          session.subject.subject_name,
                'date':             str(session.date),
                'location_verified': location_verified,
            })

        except ImportError as e:
            return Response({'error': f'DeepFace library install nahi hai: {str(e)}'}, status=500)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Face attendance error: {str(e)}")
            return Response({'error': 'Face verification mein error aaya. Dobara try karo.'}, status=500)
        finally:
            if os.path.exists(tmp_path):
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

        attendance, created = Attendance.objects.update_or_create(
            student=student,
            subject=session.subject,
            date=session.date,
            session=session,              # ← session FK in lookup
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
                session=session,          # ← session FK in lookup
                defaults={
                    'is_present':    True,
                    'day':           session.date.strftime('%A'),
                    'semester':      session.semester,
                    'academic_year': academic_year or session.academic_year,
                    'marked_by':     teacher,
                    'method':        'rfid',
                    'session':       session,
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
        ).all().order_by('-date', 'student')


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
class TeacherSessionListView(APIView):
    """
    GET /api/attendance/sessions/
    Teacher ki recent sessions list karta hai (last 60 days).
    Optional filter: ?student_pk=<pk>  — student ke enrolled subjects se match karega.
    """
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        teacher = get_object_or_404(Teacher, user=request.user)
        student_pk = request.query_params.get('student_pk')

        sessions_qs = AttendanceSession.objects.filter(
            teacher=teacher
        ).select_related('subject').order_by('-date', '-created_at')[:60]

        # Agar student_pk diya hai to sirf us student ke enrolled subjects ki sessions
        if student_pk:
            try:
                student = Student.objects.get(pk=student_pk)
                enrolled_subject_ids = CourseRegistration.objects.filter(
                    student=student
                ).values_list('subject_id', flat=True)
                sessions_qs = sessions_qs.filter(subject_id__in=enrolled_subject_ids)
            except Student.DoesNotExist:
                pass

        data = [
            {
                'id':           s.id,
                'subject_name': s.subject.subject_name,
                'subject_code': s.subject.subject_code,
                'date':         s.date.strftime('%d %b %Y'),
                'status':       s.status,
            }
            for s in sessions_qs
        ]
        return Response({'sessions': data})


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
        total_students_set = set()  # unique students across all subjects

        for subject in subjects:
            total_classes = AttendanceSession.objects.filter(
                teacher=teacher, subject=subject, status='closed'
            ).count()

            from academics.models import CourseRegistration
            student_ids = CourseRegistration.objects.filter(
                subject=subject
            ).values_list('student_id', flat=True)

            enrolled = len(student_ids)
            total_students_set.update(student_ids)

            subject_stats.append({
                'subject_code':  subject.subject_code,
                'subject_name':  subject.subject_name,
                'total_classes': total_classes,
                'enrolled':      enrolled,
            })

        return Response({
            'total_sessions_taken': sessions_taken,
            'pending_leaves':       pending_leaves,
            'total_students':       len(total_students_set),
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
        # student_id yahan string PK hai (e.g. "BCS2024002")
        student = get_object_or_404(Student, student_id=student_id)
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
            from analytics.utils import send_attendance_request_email
            send_attendance_request_email(
                teacher_email=teacher.email,
                student_name=student.profile.name if hasattr(student, 'profile') else student_id,
                subject_name=session.subject.subject_name,
                date=session.date,
                reason=reason,
                action='submitted',
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
            from analytics.utils import send_attendance_request_email
            student_name = getattr(req.student, 'profile', None) and req.student.profile.name
            send_attendance_request_email(
                teacher_email=req.teacher.email,
                student_name=student_name or req.student_id,
                subject_name=req.session.subject.subject_name,
                date=req.session.date,
                reason=req.reason,
                action=action,
                remark=remark,
            )
        except Exception:
            pass

        return Response({
            'message':           f'Request {action} successfully.',
            'request_id':        req.id,
            'attendance_marked': action == 'approved',
        })

# ─────────────────────────────────────────────
# Parent Notification (Admin + Teacher)
# ─────────────────────────────────────────────
class SendParentNotificationView(APIView):
    """
    POST /api/attendance/notify-parent/
    Admin ya Teacher parent ko attendance alert email bhejta hai.

    Body:
    {
      "student_id": "BCS2024001",
      "subject_code": "CS301",        # optional — specific subject
      "semester": 3,                  # optional
      "academic_year": "2024-2025",   # optional
      "custom_message": "..."         # optional custom note
    }

    Returns:
      { "sent": true, "email": "pa***@gmail.com", "student": "...", "percentage": 72.5 }
    """
    permission_classes = [IsTeacherOrAdmin]

    def post(self, request):
        from accounts.models import Student
        from analytics.utils import send_attendance_alert_email

        student_id   = request.data.get('student_id', '').strip()
        subject_code = request.data.get('subject_code', '').strip()
        semester     = request.data.get('semester')
        academic_year = request.data.get('academic_year', '').strip()
        custom_msg   = request.data.get('custom_message', '').strip()

        if not student_id:
            return Response({'error': 'student_id is required'}, status=400)

        student = get_object_or_404(Student, pk=student_id)
        profile = getattr(student, 'profile', None)
        parent  = getattr(student, 'parent_detail', None)

        if not profile:
            return Response({'error': 'Student profile not found.'}, status=400)

        student_name = profile.name

        # Parent email — father_email first, then mother email fallback
        parent_email = None
        if parent:
            parent_email = parent.father_email or None
        if not parent_email:
            # Try student own email as fallback (notify student too)
            parent_email = profile.email

        if not parent_email:
            return Response({
                'error': 'Is student ke parent ka koi email registered nahi hai. '
                         'Please first student ki family details mein parent email add karo.'
            }, status=400)

        # Calculate attendance percentage
        percentage = None
        subject_name = subject_code  # fallback

        if subject_code and semester and academic_year:
            try:
                from academics.models import Subject
                subject_obj = Subject.objects.filter(subject_code=subject_code).first()
                if subject_obj:
                    subject_name = subject_obj.subject_name
                    total   = Attendance.objects.filter(
                        student=student, subject=subject_obj,
                        semester=semester, academic_year=academic_year
                    ).count()
                    present = Attendance.objects.filter(
                        student=student, subject=subject_obj,
                        semester=semester, academic_year=academic_year,
                        is_present=True
                    ).count()
                    percentage = round((present / total * 100), 1) if total > 0 else 0.0
            except Exception:
                percentage = 0.0
        elif not subject_code:
            # Overall attendance
            if semester and academic_year:
                total   = Attendance.objects.filter(student=student, semester=semester, academic_year=academic_year).count()
                present = Attendance.objects.filter(student=student, semester=semester, academic_year=academic_year, is_present=True).count()
                percentage = round((present / total * 100), 1) if total > 0 else 0.0
                subject_name = 'Overall Attendance'
            else:
                percentage = 0.0
                subject_name = 'Attendance Update'

        if percentage is None:
            percentage = 0.0

        try:
            send_attendance_alert_email(
                parent_email=parent_email,
                student_name=student_name,
                subject_name=subject_name,
                percentage=percentage,
                custom_message=custom_msg,
            )
        except Exception as e:
            return Response({'error': f'Failed to send email: {str(e)}'}, status=500)

        # Mask email for privacy
        try:
            local, domain = parent_email.split('@')
            masked = f"{local[:2]}***@{domain}"
        except Exception:
            masked = '***'

        return Response({
            'sent':       True,
            'email':      masked,
            'student':    student_name,
            'subject':    subject_name,
            'percentage': percentage,
            'message':    f'Parent notification successfully sent to {masked}',
        })