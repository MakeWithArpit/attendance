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
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend

from .models import User, Student, Teacher, Branch, PasswordResetOTP, DeviceToken
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
                        try:
                            from analytics.utils import send_professional_email
                            send_professional_email(
                                to=profile.email,
                                subject='New Device Login OTP — AttendX',
                                heading='New Device Detected',
                                body=(
                                    f"Dear {profile.name},\n\n"
                                    f"A login attempt was detected from a new device. "
                                    f"To verify that this is you, please enter the following OTP:\n\n"
                                    f"                {otp_code}\n\n"
                                    f"This OTP is valid for 10 minutes only.\n\n"
                                    f"If you did not attempt to log in, please change your password "
                                    f"immediately and contact your institution."
                                ),
                                footer='AttendX Attendance Management System',
                            )
                        except Exception:
                            pass

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
    permission_classes = [IsAdmin]


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
    Admin only.
    """
    serializer_class = StudentCreateSerializer
    permission_classes = [IsAdmin]

    def create(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only admin can register new students.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = serializer.save()
        return Response(StudentSerializer(student).data, status=201)


class StudentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/auth/students/<id>/
    Admin can write. Teacher can only read.
    """
    queryset = Student.objects.select_related('profile', 'parent_detail').all()
    serializer_class = StudentSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsTeacherOrAdmin()]
        return [IsAdmin()]


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
            return Response(StudentSerializer(student).data)
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
    Clears all registered device tokens for a student so they can
    log in from a new device (OTP will be required on next login).

    GET /api/auth/admin/device-reset/
    Lists all students and their registered device tokens.
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        student_id = request.data.get('student_id', '').strip()
        if not student_id:
            return Response({'error': 'student_id is required'}, status=400)

        from django.shortcuts import get_object_or_404
        student = get_object_or_404(Student, pk=student_id)
        count   = DeviceToken.objects.filter(student=student).count()
        DeviceToken.objects.filter(student=student).delete()

        try:
            profile = student.profile
            if profile.email:
                from analytics.utils import send_professional_email
                send_professional_email(
                    to=profile.email,
                    subject='Device Registration Reset — AttendX',
                    heading='Your Device Registration Has Been Reset',
                    body=(
                        f"Dear {profile.name},\n\n"
                        f"Your registered device has been reset by the administrator. "
                        f"This is typically done when you have changed or lost your device.\n\n"
                        f"The next time you log into AttendX from a new device, "
                        f"that device will be automatically registered.\n\n"
                        f"If you did not request this reset, please contact your institution immediately."
                    ),
                    footer='AttendX Attendance Management System',
                )
        except Exception:
            pass

        return Response({
            'message':    f'{count} device token(s) cleared for {student_id}.',
            'student_id': student_id,
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
    """
    permission_classes = []  # AllowAny

    def post(self, request):
        from django.utils import timezone
        from django.conf import settings

        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        user     = User.objects.get(username=username)
        email    = self._get_email(user)

        otp_code = str(random.randint(100000, 999999))

        PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)
        PasswordResetOTP.objects.create(
            user=user,
            otp=otp_code,
            expires_at=timezone.now() + datetime.timedelta(minutes=10),
        )

        try:
            from analytics.utils import send_password_reset_otp_email
            send_password_reset_otp_email(
                user_email=email,
                user_name=self._get_name(user),
                otp_code=otp_code,
            )
        except Exception as e:
            return Response(
                {'error': f'Email send karne mein error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            'message': f'OTP successfully bhej diya gaya hai {self._mask_email(email)} par.',
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
            return Response({'error': 'Username galat hai.'}, status=400)

        otp_record = PasswordResetOTP.objects.filter(
            user=user, is_used=False
        ).order_by('-created_at').first()

        if not otp_record:
            return Response(
                {'error': 'Koi OTP nahi mila. Pehle forgot password request karo.'},
                status=400
            )

        if timezone.now() > otp_record.expires_at:
            otp_record.is_used = True
            otp_record.save()
            return Response(
                {'error': 'OTP expire ho gaya hai. Dobara forgot password karo.'},
                status=400
            )

        if otp_record.otp != otp_entered:
            return Response({'error': 'OTP galat hai. Dobara check karo.'}, status=400)

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
            'message': 'Password successfully change ho gaya hai. Ab naye password se login karo.',
        })