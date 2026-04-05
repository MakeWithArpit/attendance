"""
accounts/views.py
Authentication + Student/Teacher management endpoints
"""
import random
import datetime
from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend

from .models import User, Student, Teacher, Branch, PasswordResetOTP, DeviceToken, StudentProfile, ParentDetail, PermanentAddress, PresentAddress, WebAuthnCredential, WebAuthnChallenge
from .serializers import (
    CustomTokenObtainPairSerializer,
    StudentSerializer, StudentCreateSerializer,
    TeacherSerializer, TeacherCreateSerializer,
    BranchSerializer,
    ForgotPasswordSerializer, VerifyOTPSerializer,
)
from .permissions import IsAdmin, IsTeacherOrAdmin


# ─────────────────────────────────────────────
# Auth Views
# ─────────────────────────────────────────────
class LoginView(TokenObtainPairView):
    """
    POST /api/auth/login/
    Body: { "username": "STU001", "password": "xxxx", "device_id": "...", "device_label": "..." }
    Returns: access_token, refresh_token, role, name
    If a student logs in from a new device: returns { requires_device_otp: True, user_id }
    and sends a 6-digit OTP to their registered email.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        from django.utils import timezone as tz

        # Run standard JWT authentication first
        response = super().post(request, *args, **kwargs)

        if response.status_code != 200:
            return response

        username = request.data.get('username', '')
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return response

        device_id    = request.data.get('device_id', '').strip()
        device_label = request.data.get(
            'device_label',
            request.META.get('HTTP_USER_AGENT', '')[:200]
        )

        if user.role == 'student' and device_id:
            try:
                student  = user.student
                existing = DeviceToken.objects.filter(student=student)

                if not existing.exists():
                    # First ever login — register this device automatically
                    DeviceToken.objects.create(
                        student=student,
                        device_id=device_id,
                        device_label=device_label,
                        is_primary=True,
                    )

                elif not existing.filter(device_id=device_id).exists():
                    # Known student, unknown device — block login and require OTP
                    otp_code = str(random.randint(100000, 999999))

                    # Expire any previous unused OTPs for this user
                    PasswordResetOTP.objects.filter(
                        user=user, is_used=False
                    ).update(is_used=True)

                    PasswordResetOTP.objects.create(
                        user=user,
                        otp=otp_code,
                        expires_at=tz.now() + datetime.timedelta(minutes=10),
                    )

                    profile = getattr(student, 'profile', None)
                    if profile and profile.email:
                        # Send email in background — don't block login response
                        import threading as _threading
                        _email = profile.email
                        _name  = profile.name
                        _otp   = otp_code
                        def _send_device_otp():
                            try:
                                from analytics.utils import send_device_otp_email
                                send_device_otp_email(
                                    user_email=_email,
                                    user_name=_name,
                                    otp_code=_otp,
                                )
                            except Exception:
                                pass
                        _threading.Thread(target=_send_device_otp, daemon=True).start()

                    # Return special response — do NOT include JWT tokens yet
                    return Response({
                        'requires_device_otp': True,
                        'user_id': user.id,
                        'message': 'New device detected. OTP sent to your registered email.',
                    }, status=200)

                else:
                    # Known device — update last_login timestamp
                    existing.filter(device_id=device_id).update(last_login=tz.now())

            except Exception:
                pass  # Device check failed silently — do not block login

        return response


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Blacklists the refresh token.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logged out successfully'}, status=200)
        except Exception:
            return Response({'error': 'Invalid token'}, status=400)


class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not user.check_password(old_password):
            return Response({'error': 'Old password is incorrect'}, status=400)

        user.set_password(new_password)
        user.save()
        return Response({'message': 'Password changed successfully'})


# ─────────────────────────────────────────────
# Device OTP Verification
# ─────────────────────────────────────────────
class VerifyDeviceOTPView(APIView):
    """
    POST /api/auth/verify-device-otp/
    Called after LoginView returns { requires_device_otp: True }.
    Verifies the OTP, registers the new device, and returns JWT tokens.

    Body: { user_id, otp, device_id, device_label }
    """
    permission_classes = []  # AllowAny — called before login

    def post(self, request):
        from django.utils import timezone as tz

        user_id      = request.data.get('user_id')
        otp_code     = request.data.get('otp', '').strip()
        device_id    = request.data.get('device_id', '').strip()
        device_label = request.data.get('device_label', '')

        if not all([user_id, otp_code, device_id]):
            return Response(
                {'error': 'user_id, otp, and device_id are all required'},
                status=400
            )

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'Invalid user'}, status=400)

        otp = PasswordResetOTP.objects.filter(
            user=user, otp=otp_code, is_used=False
        ).order_by('-created_at').first()

        if not otp or not otp.is_valid:
            return Response({'error': 'Invalid or expired OTP'}, status=400)

        otp.is_used = True
        otp.save()

        # Register the new device
        if user.role == 'student':
            DeviceToken.objects.get_or_create(
                student=user.student,
                device_id=device_id,
                defaults={'device_label': device_label, 'is_primary': False},
            )

        # Issue JWT tokens
        refresh = RefreshToken.for_user(user)
        name = user.username
        try:
            if user.role == 'student':
                name = user.student.profile.name
            elif user.role == 'teacher':
                name = user.teacher.name
        except Exception:
            pass

        return Response({
            'access':   str(refresh.access_token),
            'refresh':  str(refresh),
            'role':     user.role,
            'username': user.username,
            'name':     name,
        })


# ─────────────────────────────────────────────
# Branch
# ─────────────────────────────────────────────
class BranchListCreateView(generics.ListCreateAPIView):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer

    def get_permissions(self):
        # GET (list) → Teacher + Admin both can see branches
        # POST (create) → Admin only
        if self.request.method == 'GET':
            return [IsTeacherOrAdmin()]
        return [IsAdmin()]


class BranchDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAdmin]


# ─────────────────────────────────────────────
# Student Views
# ─────────────────────────────────────────────
class StudentListView(generics.ListAPIView):
    """
    GET /api/auth/students/
    Admin & Teacher can list all students with filters.
    """
    serializer_class = StudentSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['enrollment_number', 'roll_number', 'profile__name']
    filterset_fields = ['profile__branch', 'profile__academic_year']

    def get_queryset(self):
        return Student.objects.select_related(
            'profile', 'profile__branch', 'parent_detail',
            'permanent_address', 'present_address'
        ).all()


class StudentCreateView(generics.CreateAPIView):
    """
    POST /api/auth/students/create/
    Admin only. Supports multipart/form-data for registered_photo upload.
    """
    serializer_class = StudentCreateSerializer
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        import json as _json, traceback as _tb
        try:
            return self._do_create(request, *args, **kwargs)
        except Exception as exc:
            _tb.print_exc()
            return Response(
                {'error': str(exc), 'trace': _tb.format_exc()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _do_create(self, request, *args, **kwargs):
        import json as _json, traceback as _tb

        if request.user.role != 'admin':
            return Response(
                {'error': 'Only admin can register new students.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # When FormData (multipart) is submitted, request.data is a QueryDict.
        # DRF's nested serializer calls html.parse_html_dict() on it looking for
        # keys like 'profile[name]', but we send 'profile' as a JSON string,
        # so the field appears empty → 400 error.
        # Convert the QueryDict to a plain Python dict first to avoid this.
        data = {}
        for key in request.data:
            data[key] = request.data[key]   # take last value (standard QueryDict behaviour)

        # Separately attach any uploaded files (e.g. registered_photo)
        for key in request.FILES:
            data[key] = request.FILES[key]

        # Parse nested JSON strings into dicts
        for key in ('profile', 'parent_detail', 'permanent_address', 'present_address'):
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = _json.loads(data[key])
                except (ValueError, TypeError):
                    pass
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Validation failed', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            student = serializer.save()
        except Exception as exc:
            _tb.print_exc()
            return Response(
                {'error': str(exc), 'trace': _tb.format_exc()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # ── Auto CourseRegistration ─────────────────────────────────────────
        # Read branch, section, semester from the new student's profile and
        # auto-enroll the student into all matching subjects.
        #
        # Priority:
        #   1★ Subject.branch + Subject.semester (direct tag — fastest)
        #   2. Copy existing CourseRegistrations from peers in the same branch/semester
        #   3. Derive subjects from the TimeTable
        # ─────────────────────────────────────────────────────────────────────
        try:
            from academics.models import Subject, CourseRegistration
            profile = getattr(student, 'profile', None)
            if profile and profile.branch and profile.section and profile.current_semester:
                branch   = profile.branch
                section  = profile.section.strip().upper()
                semester = int(profile.current_semester)

                # Strategy 1 (preferred): subjects directly tagged with branch + semester
                subjects = list(Subject.objects.filter(
                    branch=branch,
                    semester=semester,
                ).distinct())

                # Strategy 2: Copy from existing CourseRegistrations of peers
                if not subjects:
                    subjects = list(Subject.objects.filter(
                        courseregistration__branch=branch,
                        courseregistration__semester=semester,
                    ).distinct())

                # Strategy 3: Derive subjects from TimeTable
                if not subjects:
                    from academics.models import TimeTable
                    subjects = list(Subject.objects.filter(
                        timetable__branch=branch,
                        timetable__semester=semester,
                    ).distinct())

                for subj in subjects:
                    CourseRegistration.objects.get_or_create(
                        student=student,
                        subject=subj,
                        semester=semester,
                        defaults={'branch': branch, 'section': section}
                    )
        except Exception as _e:
            _logger.warning(f'Auto-enroll failed for student (non-fatal): {_e}')

        try:
            response_data = StudentSerializer(student).data
        except Exception as exc:
            _tb.print_exc()   # log the error server-side
            # Student was created — return a minimal response
            response_data = {
                'student_id': student.student_id,
                'enrollment_number': student.enrollment_number,
                'roll_number': student.roll_number,
            }
        return Response(response_data, status=201)


class StudentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/auth/students/<id>/
    Admin can write. Teacher can only read.

    PATCH expects body:
    {
      "enrollment_number": "...",        # optional
      "roll_number": "...",              # optional
      "password": "...",                 # optional — change password
      "profile": {                       # optional — any subset of fields
          "name", "dob", "gender", "mobile_number", "email",
          "domicile_state", "academic_year", "branch", "date_of_joining"
      },
      "parent_detail": {                 # optional
          "father_name", "father_mobile", "father_occupation",
          "father_email", "mother_name", "mother_mobile"
      },
      "permanent_address": {             # optional
          "address_line1", "state", "place", "pincode"
      }
    }
    """
    queryset = Student.objects.select_related(
        'profile', 'parent_detail', 'permanent_address', 'present_address'
    ).all()
    serializer_class = StudentSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsTeacherOrAdmin()]
        return [IsAdmin()]

    def update(self, request, *args, **kwargs):
        return self._do_update(request)

    def partial_update(self, request, *args, **kwargs):
        return self._do_update(request)

    def _do_update(self, request):
        student = self.get_object()
        data = request.data

        # ── 1. Student base fields ──────────────────────────────
        base_fields = ('enrollment_number', 'roll_number', 'rfid_number', 'aadhar_number')
        changed = False
        for field in base_fields:
            if field in data:
                setattr(student, field, data[field] or None if field in ('rfid_number', 'aadhar_number') else data[field])
                changed = True
        if changed:
            student.save()

        # ── 2. Password (optional) ──────────────────────────────
        new_pass = str(data.get('password', '')).strip()
        if new_pass:
            student.user.set_password(new_pass)
            student.user.save()

        # ── 3. Profile update ───────────────────────────────────
        profile_data = data.get('profile')
        if profile_data and isinstance(profile_data, dict):
            profile, _ = StudentProfile.objects.get_or_create(student=student)
            for field in ('name', 'dob', 'gender', 'mobile_number', 'email',
                          'domicile_state', 'academic_year', 'date_of_joining',
                          'nationality', 'marital_status',
                          'section', 'current_semester'):
                if field in profile_data:
                    setattr(profile, field, profile_data[field])
            # branch is a FK — accept branch_code string
            if 'branch' in profile_data:
                profile.branch_id = profile_data['branch'] or None
            profile.save()

        # ── 4. Parent Detail update ─────────────────────────────
        parent_data = data.get('parent_detail')
        if parent_data and isinstance(parent_data, dict):
            parent, _ = ParentDetail.objects.get_or_create(student=student)
            for field in ('father_name', 'father_occupation', 'father_mobile',
                          'father_email', 'mother_name', 'mother_occupation', 'mother_mobile'):
                if field in parent_data:
                    setattr(parent, field, parent_data[field])
            parent.save()

        # ── 5. Permanent Address update ─────────────────────────
        perm_data = data.get('permanent_address')
        if perm_data and isinstance(perm_data, dict):
            perm, _ = PermanentAddress.objects.get_or_create(student=student)
            for field in ('address_line1', 'address_line2', 'address_line3', 'state', 'place', 'pincode'):
                if field in perm_data:
                    setattr(perm, field, perm_data[field])
            perm.save()

        # ── Return fresh data ───────────────────────────────────
        student = Student.objects.select_related(
            'profile', 'parent_detail', 'permanent_address', 'present_address'
        ).get(pk=student.pk)
        return Response(StudentSerializer(student).data)


class MyProfileView(APIView):
    """
    GET /api/auth/me/
    Returns the authenticated user's own profile.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == 'student':
            student = Student.objects.select_related(
                'profile', 'parent_detail', 'permanent_address', 'present_address'
            ).get(user=user)
            data = StudentSerializer(student).data

            # WebAuthn passkey status — frontend uses this to enable/disable
            # the "Register Passkey" button in the profile page.
            try:
                cred = student.webauthn_credential
                data['webauthn_registered'] = True
                data['webauthn_registered_at'] = cred.registered_at.isoformat()
                data['webauthn_device_label']   = cred.device_label
            except WebAuthnCredential.DoesNotExist:
                data['webauthn_registered']     = False
                data['webauthn_registered_at']  = None
                data['webauthn_device_label']   = None

            return Response(data)
        elif user.role == 'teacher':
            teacher = Teacher.objects.get(user=user)
            return Response(TeacherSerializer(teacher).data)
        return Response({'role': 'admin', 'username': user.username})


# ─────────────────────────────────────────────
# Teacher Views
# ─────────────────────────────────────────────
class TeacherListView(generics.ListAPIView):
    """GET /api/auth/teachers/"""
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    permission_classes = [IsAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'employee_id', 'department']


class TeacherCreateView(generics.CreateAPIView):
    """POST /api/auth/teachers/create/ — Admin only"""
    serializer_class = TeacherCreateSerializer
    permission_classes = [IsAdmin]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        teacher = serializer.save()
        return Response(TeacherSerializer(teacher).data, status=201)


class TeacherDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE /api/auth/teachers/<id>/ — Admin only"""
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    permission_classes = [IsAdmin]


# ─────────────────────────────────────────────
# Device Management (Admin)
# ─────────────────────────────────────────────
class AdminDeviceResetView(APIView):
    """
    POST /api/auth/admin/device-reset/
    Full device reset for a student — used when a student loses their phone
    or needs to register a new device.

    Atomically deletes (all-or-nothing):
      - DeviceToken(s)         -> forces OTP verification on next login
      - WebAuthnCredential     -> removes registered passkey
      - WebAuthnChallenge(s)   -> cleans up any pending challenges

    After reset the student:
      1. Logs into the new device (OTP required — existing DeviceToken flow)
      2. Profile page shows "Register Passkey" button again (one-time option restored)

    GET /api/auth/admin/device-reset/
    Lists all students with their device tokens.
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        from django.shortcuts import get_object_or_404
        from django.db import transaction

        student_id = request.data.get('student_id', '').strip()
        if not student_id:
            return Response({'error': 'student_id is required'}, status=400)

        student = get_object_or_404(Student, pk=student_id)

        # Snapshot counts before deletion (for response message)
        device_count    = DeviceToken.objects.filter(student=student).count()
        passkey_existed = hasattr(student, 'webauthn_credential')

        # Atomic delete — all-or-nothing
        # If any deletion fails the entire operation rolls back,
        # leaving the student's data in a consistent state.
        with transaction.atomic():
            DeviceToken.objects.filter(student=student).delete()
            WebAuthnCredential.objects.filter(student=student).delete()
            WebAuthnChallenge.objects.filter(student=student).delete()

        # Notify student via email (non-blocking, non-critical)
        try:
            profile = student.profile
            if profile.email:
                import threading as _t
                _email = profile.email
                _name  = profile.name
                def _send():
                    try:
                        from analytics.utils import send_device_reset_email
                        send_device_reset_email(
                            user_email=_email,
                            user_name=_name,
                        )
                    except Exception:
                        pass
                _t.Thread(target=_send, daemon=True).start()
        except Exception:
            pass

        return Response({
            'message':         'Device reset successful. Student must log in again from new device.',
            'student_id':      student_id,
            'devices_cleared': device_count,
            'passkey_cleared': passkey_existed,
        })

    def get(self, request):
        tokens = DeviceToken.objects.select_related('student__profile').all()
        data = [{
            'student_id':    t.student_id,
            'student_name':  getattr(t.student, 'profile', None) and t.student.profile.name,
            'device_id':     t.device_id[:12] + '...',
            'device_label':  t.device_label[:60],
            'registered_at': t.registered_at.isoformat(),
            'last_login':    t.last_login.isoformat(),
        } for t in tokens]
        return Response({'devices': data, 'total': len(data)})


# ─────────────────────────────────────────────
# Forgot Password — Step 1: Send OTP
# ─────────────────────────────────────────────
class ForgotPasswordView(APIView):
    """
    POST /api/auth/forgot-password/
    Body: { "username": "STU2024001" }
    Generates a 6-digit OTP and emails it to the user's registered address.
    Email is sent in a background thread so the API responds immediately.
    """
    permission_classes = []  # AllowAny

    def post(self, request):
        import threading
        from django.utils import timezone

        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        user     = User.objects.get(username=username)
        email    = self._get_email(user)

        otp_code = str(random.randint(100000, 999999))

        # Save OTP to DB (expire old ones)
        PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)
        PasswordResetOTP.objects.create(
            user=user,
            otp=otp_code,
            expires_at=timezone.now() + datetime.timedelta(minutes=10),
        )

        # Send email in background — API responds immediately, no Broken Pipe
        def _send_email():
            try:
                from analytics.utils import send_password_reset_otp_email
                send_password_reset_otp_email(
                    user_email=email,
                    user_name=self._get_name(user),
                    otp_code=otp_code,
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"OTP email failed for {username}: {e}")

        threading.Thread(target=_send_email, daemon=True).start()

        return Response({
            'message': f'OTP has been sent successfully to {self._mask_email(email)}.',
            'email':   self._mask_email(email),
        })

    def _get_email(self, user):
        if user.role == 'student':
            return user.student.profile.email
        elif user.role == 'teacher':
            return user.teacher.email
        return getattr(user, 'email', '')

    def _get_name(self, user):
        try:
            if user.role == 'student':
                return user.student.profile.name
            elif user.role == 'teacher':
                return user.teacher.name
        except Exception:
            pass
        return user.username

    def _mask_email(self, email):
        try:
            local, domain = email.split('@')
            return f"{local[:2]}***@{domain}"
        except Exception:
            return '***'


# ─────────────────────────────────────────────
# Forgot Password — Step 2: Verify OTP + Reset
# ─────────────────────────────────────────────
class ResetPasswordView(APIView):
    """
    POST /api/auth/reset-password/
    Body: { "username": "STU2024001", "otp": "482910", "new_password": "NewPass@456" }
    """
    permission_classes = []  # AllowAny

    def post(self, request):
        from django.utils import timezone

        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username     = serializer.validated_data['username']
        otp_entered  = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'Invalid username.'}, status=400)

        otp_record = PasswordResetOTP.objects.filter(
            user=user, is_used=False
        ).order_by('-created_at').first()

        if not otp_record:
            return Response(
                {'error': 'No OTP found. Please initiate a forgot password request first.'},
                status=400
            )

        if timezone.now() > otp_record.expires_at:
            otp_record.is_used = True
            otp_record.save()
            return Response(
                {'error': 'OTP has expired. Please request a new forgot password OTP.'},
                status=400
            )

        if otp_record.otp != otp_entered:
            return Response({'error': 'Invalid OTP. Please try again.'}, status=400)

        user.set_password(new_password)
        user.save()

        otp_record.is_used = True
        otp_record.save()

        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)
        except Exception:
            pass

        return Response({
            'message': 'Password changed successfully. Please log in with your new password.',
        })

class NextStudentIdView(APIView):
    """
    GET /api/auth/next-student-id/?branch=ECE
    Returns next available student_id, enrollment_number, roll_number for a branch.
    Checks the database to guarantee unique IDs with no collisions.
    """
    permission_classes = [IsAdmin]

    def get(self, request):
        branch_code = request.query_params.get('branch', '').strip().upper()
        if not branch_code:
            return Response({'error': 'branch parameter required'}, status=400)

        from django.db.models import Q
        import datetime
        yyyy = str(datetime.date.today().year)
        prefix = branch_code + yyyy  # e.g. "ECE2026"

        used_seqs = set()

        # 1. Student table — student_id check
        for sid in Student.objects.filter(
            student_id__istartswith=prefix
        ).values_list('student_id', flat=True):
            try:
                used_seqs.add(int(sid.upper()[len(prefix):]))
            except ValueError:
                pass

        # 2. User table — check usernames (orphan users from partial creates)
        for uname in User.objects.filter(
            username__istartswith=prefix
        ).values_list('username', flat=True):
            try:
                used_seqs.add(int(uname.upper()[len(prefix):]))
            except ValueError:
                pass

        # 3. Enrollment number check
        enr_prefix = f'EN{yyyy}{branch_code}'
        for enr in Student.objects.filter(
            enrollment_number__istartswith=enr_prefix
        ).values_list('enrollment_number', flat=True):
            try:
                used_seqs.add(int(enr.upper()[len(enr_prefix):]))
            except ValueError:
                pass

        # Find the first unused sequence number
        seq = 1
        while seq in used_seqs:
            seq += 1

        padded = str(seq).zfill(3)
        return Response({
            'student_id':        f'{branch_code}{yyyy}{padded}',
            'enrollment_number': f'EN{yyyy}{branch_code}{padded}',
            'roll_number':       f'{branch_code}{padded}',
        })


class NextTeacherIdView(APIView):
    """
    GET /api/auth/next-teacher-id/?dept=Computer+Science+%26+Engineering
    Returns next available employee_id for a department.
    """
    permission_classes = [IsAdmin]

    def get(self, request):
        dept = request.query_params.get('dept', '').strip()
        if not dept:
            return Response({'error': 'dept parameter required'}, status=400)

        import re
        dept_code = re.sub(r'[^A-Z0-9]', '', ''.join(
            w[0] for w in re.sub(r'[^A-Z0-9 ]', '', dept.upper()).split() if w
        ))[:4] or dept[:3].upper()

        prefix = f'T-{dept_code}'

        used_seqs = set()

        # Teacher table check
        for eid in Teacher.objects.filter(
            employee_id__istartswith=prefix
        ).values_list('employee_id', flat=True):
            try:
                used_seqs.add(int(eid.upper()[len(prefix):]))
            except ValueError:
                pass

        # User table check — orphan users
        for uname in User.objects.filter(
            username__istartswith=prefix
        ).values_list('username', flat=True):
            try:
                used_seqs.add(int(uname.upper()[len(prefix):]))
            except ValueError:
                pass

        seq = 1
        while seq in used_seqs:
            seq += 1

        return Response({
            'employee_id': f'{prefix}{str(seq).zfill(3)}',
        })

# ═══════════════════════════════════════════════════════════════════
# WebAuthn (Passkey) Views
# ═══════════════════════════════════════════════════════════════════
#
# Registration flow (one-time, from student profile page):
#   POST /api/auth/webauthn/register/begin/     → generate options
#   POST /api/auth/webauthn/register/complete/  → verify + save credential
#
# Authentication flow (every attendance marking):
#   POST /api/auth/webauthn/auth/begin/         → generate challenge
#   POST /api/auth/webauthn/auth/complete/      → verify + mark attendance
#
# Admin:
#   GET  /api/auth/webauthn/admin/status/       → passkey status for all students
#
# ─────────────────────────────────────────────────────────────────

import base64
import json as _json

from django.conf import settings as django_settings
from django.utils import timezone as _tz

from .permissions import IsStudent


# ── Internal helpers ─────────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    """bytes → base64url string without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _b64url_decode(s: str) -> bytes:
    """base64url string → bytes (handles missing = padding)."""
    s = s + '=' * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def _get_challenge_or_404(student, purpose):
    """
    Retrieve the pending WebAuthnChallenge for this student+purpose.
    Returns (challenge_bytes, challenge_record) or raises a descriptive error dict.
    """
    from datetime import timedelta

    timeout_seconds = getattr(django_settings, 'WEBAUTHN_CHALLENGE_TIMEOUT', 300)
    cutoff = _tz.now() - timedelta(seconds=timeout_seconds)

    record = WebAuthnChallenge.objects.filter(
        student=student,
        purpose=purpose,
        created_at__gte=cutoff,
    ).first()

    if not record:
        return None, None

    return _b64url_decode(record.challenge), record


# ─────────────────────────────────────────────────────────────────
# Phase 2 — Step A: Register Begin
# ─────────────────────────────────────────────────────────────────

class WebAuthnRegisterBeginView(APIView):
    """
    POST /api/auth/webauthn/register/begin/

    Called when a student clicks "Register Passkey" in their profile.
    Generates WebAuthn registration options and stores the challenge.

    Returns: PublicKeyCredentialCreationOptions JSON (consumed by
             navigator.credentials.create() on the frontend).

    Errors:
      409 — student already has a registered passkey (one-time only).
      403 — non-student users cannot register passkeys here.
    """
    permission_classes = [IsStudent]

    def post(self, request):
        import webauthn
        from webauthn.helpers.structs import (
            AuthenticatorSelectionCriteria,
            AuthenticatorAttachment,
            ResidentKeyRequirement,
            UserVerificationRequirement,
            AttestationConveyancePreference,
        )
        from webauthn.helpers.cose import COSEAlgorithmIdentifier

        student = getattr(request.user, 'student', None)
        if not student:
            return Response({'error': 'Student profile not found.'}, status=400)

        # Block if already registered — one-time only
        if hasattr(student, 'webauthn_credential'):
            return Response(
                {'error': 'Passkey already registered. Contact admin to reset.'},
                status=409,
            )

        # Fetch display name from profile (fallback to student_id)
        display_name = student.student_id
        try:
            display_name = student.profile.name
        except Exception:
            pass

        rp_id   = getattr(django_settings, 'WEBAUTHN_RP_ID',   'localhost')
        rp_name = getattr(django_settings, 'WEBAUTHN_RP_NAME', 'Attendance System')

        # Generate registration options
        options = webauthn.generate_registration_options(
            rp_id=rp_id,
            rp_name=rp_name,
            user_id=student.student_id.encode('utf-8'),
            user_name=student.student_id,
            user_display_name=display_name,
            attestation=AttestationConveyancePreference.NONE,
            authenticator_selection=AuthenticatorSelectionCriteria(
                # PLATFORM = on-device biometric/PIN only (no USB security keys)
                authenticator_attachment=AuthenticatorAttachment.PLATFORM,
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            supported_pub_key_algs=[
                COSEAlgorithmIdentifier.ECDSA_SHA_256,
                COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
            ],
            timeout=60000,  # 60 seconds for biometric prompt
        )

        # Store challenge — upsert (delete old, create new)
        WebAuthnChallenge.objects.filter(
            student=student, purpose='register'
        ).delete()
        WebAuthnChallenge.objects.create(
            student=student,
            purpose='register',
            challenge=_b64url_encode(options.challenge),
        )

        # Convert options to JSON-serialisable dict for the frontend
        options_dict = _json.loads(webauthn.options_to_json(options))
        return Response(options_dict, status=200)


# ─────────────────────────────────────────────────────────────────
# Phase 2 — Step B: Register Complete
# ─────────────────────────────────────────────────────────────────

class WebAuthnRegisterCompleteView(APIView):
    """
    POST /api/auth/webauthn/register/complete/

    Called after navigator.credentials.create() resolves on the frontend.
    Body: the PublicKeyCredential JSON returned by the browser.

    Steps:
      1. Retrieve the pending challenge for this student.
      2. Verify the registration response using py_webauthn.
      3. Save WebAuthnCredential (public key + credential ID + sign count).
      4. Delete the used challenge.

    Returns:
      200 { success: true, registered_at, device_label }
      400 { error: ... }   — verification failed or no pending challenge
      409                  — passkey already registered
    """
    permission_classes = [IsStudent]

    def post(self, request):
        import webauthn
        from webauthn.helpers.structs import RegistrationCredential
        from webauthn.exceptions import InvalidCBORData, InvalidRegistrationResponse

        student = getattr(request.user, 'student', None)
        if not student:
            return Response({'error': 'Student profile not found.'}, status=400)

        # Block double registration
        if hasattr(student, 'webauthn_credential'):
            return Response(
                {'error': 'Passkey already registered. Contact admin to reset.'},
                status=409,
            )

        # Retrieve pending challenge
        challenge_bytes, challenge_record = _get_challenge_or_404(student, 'register')
        if not challenge_bytes:
            return Response(
                {'error': 'No valid registration challenge found. '
                          'Please start registration again (challenge may have expired).'},
                status=400,
            )

        # Parse the browser's credential response
        try:
            credential = RegistrationCredential.parse_raw(
                _json.dumps(request.data)
            )
        except Exception as e:
            return Response(
                {'error': f'Invalid credential format: {str(e)}'},
                status=400,
            )

        # Verify with py_webauthn
        rp_id  = getattr(django_settings, 'WEBAUTHN_RP_ID',  'localhost')
        origin = getattr(django_settings, 'WEBAUTHN_ORIGIN', 'http://localhost')

        try:
            verification = webauthn.verify_registration_response(
                credential=credential,
                expected_challenge=challenge_bytes,
                expected_rp_id=rp_id,
                expected_origin=origin,
                require_user_verification=True,
            )
        except Exception as e:
            return Response(
                {'error': f'Passkey verification failed: {str(e)}'},
                status=400,
            )

        # Build device label from User-Agent
        ua = request.META.get('HTTP_USER_AGENT', '')[:200]
        device_label = _parse_device_label(ua)

        # Save credential
        cred = WebAuthnCredential.objects.create(
            student=student,
            credential_id=_b64url_encode(verification.credential_id),
            public_key=_b64url_encode(verification.credential_public_key),
            sign_count=verification.sign_count,
            device_label=device_label,
        )

        # Clean up the used challenge
        challenge_record.delete()

        return Response({
            'success':      True,
            'registered_at': cred.registered_at.isoformat(),
            'device_label':  cred.device_label,
        }, status=200)


# ── Device label helper ──────────────────────────────────────────

def _parse_device_label(user_agent: str) -> str:
    """
    Extract a human-readable device label from User-Agent string.
    e.g. 'Chrome on Android', 'Safari on iPhone', 'Chrome on Windows'
    Falls back to a truncated UA string if pattern is not recognised.
    """
    ua = user_agent.lower()

    # Browser detection
    if 'edg/' in ua or 'edge/' in ua:
        browser = 'Edge'
    elif 'chrome' in ua and 'safari' in ua:
        browser = 'Chrome'
    elif 'firefox' in ua:
        browser = 'Firefox'
    elif 'safari' in ua:
        browser = 'Safari'
    else:
        browser = 'Browser'

    # OS / device detection
    if 'iphone' in ua:
        os_label = 'iPhone'
    elif 'ipad' in ua:
        os_label = 'iPad'
    elif 'android' in ua:
        os_label = 'Android'
    elif 'windows' in ua:
        os_label = 'Windows'
    elif 'macintosh' in ua or 'mac os' in ua:
        os_label = 'Mac'
    elif 'linux' in ua:
        os_label = 'Linux'
    else:
        os_label = 'Unknown Device'

    return f"{browser} on {os_label}"


# ─────────────────────────────────────────────────────────────────
# Phase 4 — Admin WebAuthn Status View
# ─────────────────────────────────────────────────────────────────

class AdminWebAuthnStatusView(APIView):
    """
    GET /api/auth/webauthn/admin/status/

    Admin dashboard view — shows passkey registration status for all students.

    Response:
    {
        "total_students":    120,
        "registered_count":  47,
        "unregistered_count": 73,
        "students": [
            {
                "student_id":     "BCS2024001",
                "name":           "Arpit Gangwar",
                "branch":         "BCS",
                "passkey_status": "registered",          // or "not_registered"
                "registered_at":  "2026-01-12T10:30:00", // null if not registered
                "device_label":   "Chrome on Android",   // null if not registered
            },
            ...
        ]
    }

    Optional query params:
        ?status=registered        — show only registered students
        ?status=not_registered    — show only unregistered students
        ?branch=BCS               — filter by branch code
    """
    permission_classes = [IsAdmin]

    def get(self, request):
        status_filter = request.query_params.get('status', '').strip()
        branch_filter = request.query_params.get('branch', '').strip().upper()

        # Fetch all students with profile + passkey credential (if any)
        students_qs = Student.objects.select_related(
            'profile', 'profile__branch',
        ).prefetch_related('webauthn_credential').all()

        if branch_filter:
            students_qs = students_qs.filter(profile__branch_id=branch_filter)

        students_data = []
        registered_count = 0

        for student in students_qs:
            # Check if passkey is registered
            try:
                cred = student.webauthn_credential
                has_passkey = True
                registered_at = cred.registered_at.isoformat()
                device_label  = cred.device_label
            except WebAuthnCredential.DoesNotExist:
                has_passkey   = False
                registered_at = None
                device_label  = None

            if has_passkey:
                registered_count += 1

            # Apply status filter
            if status_filter == 'registered' and not has_passkey:
                continue
            if status_filter == 'not_registered' and has_passkey:
                continue

            # Student name + branch from profile
            try:
                name   = student.profile.name
                branch = student.profile.branch.branch_code if student.profile.branch else None
            except Exception:
                name   = student.student_id
                branch = None

            students_data.append({
                'student_id':     student.student_id,
                'name':           name,
                'branch':         branch,
                'passkey_status': 'registered' if has_passkey else 'not_registered',
                'registered_at':  registered_at,
                'device_label':   device_label,
            })

        total = Student.objects.count()
        if branch_filter:
            total = students_qs.count()

        return Response({
            'total_students':     total,
            'registered_count':   registered_count,
            'unregistered_count': total - registered_count,
            'students':           students_data,
        })