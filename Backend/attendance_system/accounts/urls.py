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
)

urlpatterns = [
    # Auth
    path('login/',            LoginView.as_view(),          name='login'),
    path('logout/',           LogoutView.as_view(),          name='logout'),
    path('token/refresh/',    TokenRefreshView.as_view(),    name='token_refresh'),
    path('change-password/',  ChangePasswordView.as_view(),  name='change_password'),
    path('me/',               MyProfileView.as_view(),       name='my_profile'),

    # Forgot Password (login ke bina access)
    path('forgot-password/',  ForgotPasswordView.as_view(),  name='forgot_password'),
    path('reset-password/',   ResetPasswordView.as_view(),   name='reset_password'),

    # Branch
    path('branches/',           BranchListCreateView.as_view(), name='branch_list'),
    path('branches/<str:pk>/',  BranchDetailView.as_view(),     name='branch_detail'),

    # Students
    path('students/',           StudentListView.as_view(),   name='student_list'),
    path('students/create/',    StudentCreateView.as_view(), name='student_create'),
    path('students/<str:pk>/',  StudentDetailView.as_view(), name='student_detail'),

    # Teachers
    path('teachers/',           TeacherListView.as_view(),   name='teacher_list'),
    path('teachers/create/',    TeacherCreateView.as_view(), name='teacher_create'),
    path('teachers/<str:pk>/',  TeacherDetailView.as_view(), name='teacher_detail'),
]
