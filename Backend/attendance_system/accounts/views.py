"""
accounts/views.py
Authentication + Student/Teacher management endpoints
"""
from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend

from .models import User, Student, Teacher, Branch, PasswordResetOTP
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
    Body: { "username": "STU001", "password": "xxx" }
    Returns: access_token, refresh_token, role, name
    """
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Blacklists the refresh token
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
    Admin & Teacher can list all students with filters
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
    ⚠️  ADMIN ONLY — Sirf admin hi student register kar sakta hai.
    Teacher ya koi bhi aur is endpoint ko access nahi kar sakta.
    """
    serializer_class = StudentCreateSerializer
    permission_classes = [IsAdmin]   # Hard-locked to Admin only

    def create(self, request, *args, **kwargs):
        # Double-check: even if permission class bypassed somehow
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
    Admin can edit. Teacher can only read.
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
    Student sees their own profile
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
    """
    GET /api/auth/teachers/
    """
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    permission_classes = [IsAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'employee_id', 'department']


class TeacherCreateView(generics.CreateAPIView):
    """
    POST /api/auth/teachers/create/
    Admin only
    """
    serializer_class = TeacherCreateSerializer
    permission_classes = [IsAdmin]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        teacher = serializer.save()
        return Response(TeacherSerializer(teacher).data, status=201)


class TeacherDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/auth/teachers/<id>/
    Admin only for write operations
    """
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    permission_classes = [IsAdmin]


# ─────────────────────────────────────────────
# Forgot Password — Step 1: OTP Send
# ─────────────────────────────────────────────
class ForgotPasswordView(APIView):
    """
    POST /api/auth/forgot-password/
    Permission: Koi bhi (login ke bina access hoga — AllowAny)

    Body: { "username": "STU2024001" }

    Flow:
      1. Username se user dhundo
      2. Us user ki email nikalo (role ke hisab se)
      3. 6-digit OTP generate karo
      4. DB mein save karo (10 min expiry)
      5. Email par OTP bhejo
    """
    permission_classes = []   # AllowAny — login ke bina access

    def post(self, request):
        from django.utils import timezone
        from django.core.mail import send_mail
        from django.conf import settings
        import random
        import datetime

        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        user     = User.objects.get(username=username)

        # Role ke hisab se email nikalo
        email = self._get_email(user)

        # 6-digit OTP generate karo
        otp = str(random.randint(100000, 999999))

        # Purane OTPs expire karo (is user ke)
        PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)

        # Naya OTP save karo — 10 minute valid
        PasswordResetOTP.objects.create(
            user=user,
            otp=otp,
            expires_at=timezone.now() + datetime.timedelta(minutes=10)
        )

        # Email bhejo
        try:
            send_mail(
                subject="Password Reset OTP — Attendance System",
                message=(
                    f"Dear {self._get_name(user)},\n\n"
                    f"Aapne password reset request kiya hai.\n\n"
                    f"Aapka OTP hai:  {otp}\n\n"
                    f"Yeh OTP sirf 10 minute ke liye valid hai.\n"
                    f"Agar aapne request nahi kiya toh is email ko ignore karein.\n\n"
                    f"Regards,\nAttendance System"
                ),
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            return Response(
                {'error': f'Email bhejne mein error aaya: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Security: email ka sirf kuch hissa dikhao (abc***@gmail.com)
        masked = self._mask_email(email)

        return Response({
            'message': f'OTP successfully bhej diya gaya hai {masked} par.',
            'email':   masked,
        })

    def _get_email(self, user):
        if user.role == 'student':
            return user.student.profile.email
        elif user.role == 'teacher':
            return user.teacher.email
        elif user.role == 'admin':
            return getattr(user, 'email', '')
        return ''

    def _get_name(self, user):
        if user.role == 'student':
            try: return user.student.profile.name
            except: return user.username
        elif user.role == 'teacher':
            try: return user.teacher.name
            except: return user.username
        return 'User'

    def _mask_email(self, email):
        """abc@gmail.com  →  ab***@gmail.com"""
        try:
            local, domain = email.split('@')
            visible = local[:2]
            return f"{visible}***@{domain}"
        except Exception:
            return "***"


# ─────────────────────────────────────────────
# Forgot Password — Step 2: OTP Verify + Reset
# ─────────────────────────────────────────────
class ResetPasswordView(APIView):
    """
    POST /api/auth/reset-password/
    Permission: Koi bhi (login ke bina access)

    Body: {
        "username": "STU2024001",
        "otp": "482910",
        "new_password": "NewPass@456"
    }

    Flow:
      1. Username + OTP match karo DB mein
      2. OTP expired toh nahi? is_used toh nahi?
      3. Sab sahi → password change karo
      4. OTP ko is_used=True mark karo
    """
    permission_classes = []   # AllowAny

    def post(self, request):
        from django.utils import timezone

        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username     = serializer.validated_data['username']
        otp_entered  = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        # User dhundo
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'Username galat hai.'}, status=400)

        # Latest unused OTP dhundo is user ka
        otp_record = PasswordResetOTP.objects.filter(
            user=user,
            is_used=False,
        ).order_by('-created_at').first()

        # OTP exist karta hai?
        if not otp_record:
            return Response(
                {'error': 'Koi OTP nahi mila. Pehle forgot password request karo.'},
                status=400
            )

        # OTP expire toh nahi?
        if timezone.now() > otp_record.expires_at:
            otp_record.is_used = True
            otp_record.save()
            return Response(
                {'error': 'OTP expire ho gaya hai. Dobara forgot password karo.'},
                status=400
            )

        # OTP sahi hai?
        if otp_record.otp != otp_entered:
            return Response(
                {'error': 'OTP galat hai. Dobara check karo.'},
                status=400
            )

        # Sab sahi — password change karo
        user.set_password(new_password)
        user.save()

        # OTP use hua — mark karo
        otp_record.is_used = True
        otp_record.save()

        # Saare active JWT tokens bhi expire kar do (optional but secure)
        # (SimpleJWT ke saath karne ke liye outstanding tokens delete)
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
            tokens = OutstandingToken.objects.filter(user=user)
            for token in tokens:
                BlacklistedToken.objects.get_or_create(token=token)
        except Exception:
            pass   # Agar token blacklist app nahi hai toh skip

        return Response({
            'message': 'Password successfully change ho gaya hai. Ab naye password se login karo.',
        })
