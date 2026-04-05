"""
accounts/urls.py
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    LoginView, LogoutView, ChangePasswordView, MyProfileView,
    ForgotPasswordView, ResetPasswordView,
    BranchListCreateView, BranchDetailView,
    StudentListView, StudentCreateView, StudentDetailView,
    TeacherListView, TeacherCreateView, TeacherDetailView,
    VerifyDeviceOTPView, AdminDeviceResetView,
    NextStudentIdView, NextTeacherIdView,
    # WebAuthn (Passkey)
    WebAuthnRegisterBeginView, WebAuthnRegisterCompleteView,
    AdminWebAuthnStatusView,
)

urlpatterns = [
    # Auth
    path('login/',            LoginView.as_view(),          name='login'),
    path('logout/',           LogoutView.as_view(),          name='logout'),
    path('token/refresh/',    TokenRefreshView.as_view(),    name='token_refresh'),
    path('change-password/',  ChangePasswordView.as_view(),  name='change_password'),
    path('me/',               MyProfileView.as_view(),       name='my_profile'),

    # Forgot Password (accessible without login)
    path('forgot-password/',  ForgotPasswordView.as_view(),  name='forgot_password'),
    path('reset-password/',   ResetPasswordView.as_view(),   name='reset_password'),

    # Device OTP verification (new device login)
    path('verify-device-otp/', VerifyDeviceOTPView.as_view(), name='verify_device_otp'),

    # Admin — Device token management
    path('admin/device-reset/', AdminDeviceResetView.as_view(), name='admin_device_reset'),

    # Branch
    path('branches/',           BranchListCreateView.as_view(), name='branch_list'),
    path('branches/<str:pk>/',  BranchDetailView.as_view(),     name='branch_detail'),

    # Students
    path('students/',           StudentListView.as_view(),   name='student_list'),
    path('students/create/',    StudentCreateView.as_view(), name='student_create'),
    path('students/<str:pk>/',  StudentDetailView.as_view(), name='student_detail'),

    # ID Generators — DB-checked unique IDs
    path('next-student-id/', NextStudentIdView.as_view(), name='next_student_id'),
    path('next-teacher-id/', NextTeacherIdView.as_view(), name='next_teacher_id'),

    # Teachers
    path('teachers/',           TeacherListView.as_view(),   name='teacher_list'),
    path('teachers/create/',    TeacherCreateView.as_view(), name='teacher_create'),
    path('teachers/<str:pk>/',  TeacherDetailView.as_view(), name='teacher_detail'),

    # ── WebAuthn (Passkey) ────────────────────────────────────────
    # Registration — one-time, from student's profile page
    path('webauthn/register/begin/',    WebAuthnRegisterBeginView.as_view(),    name='webauthn_register_begin'),
    path('webauthn/register/complete/', WebAuthnRegisterCompleteView.as_view(), name='webauthn_register_complete'),

    # Admin — passkey status dashboard
    path('webauthn/admin/status/',      AdminWebAuthnStatusView.as_view(),      name='webauthn_admin_status'),
]
