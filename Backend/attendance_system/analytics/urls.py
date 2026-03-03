"""
analytics/urls.py
"""
from django.urls import path
from .views import (
    SubjectWiseAnalyticsView,
    MonthlyAttendanceTrendView,
    StudentAttendanceDetailView,
    ClassAttendanceThresholdView,
    AttendanceReportView,
    NotifyParentsView,
    AdminAttendanceCorrectionView,
)

urlpatterns = [
    path('subject-wise/',              SubjectWiseAnalyticsView.as_view(),       name='subject_analytics'),
    path('monthly-trend/',             MonthlyAttendanceTrendView.as_view(),      name='monthly_trend'),
    path('student/<str:pk>/',          StudentAttendanceDetailView.as_view(),     name='student_analytics'),
    path('thresholds/',                ClassAttendanceThresholdView.as_view(),    name='attendance_thresholds'),
    path('report/',                    AttendanceReportView.as_view(),            name='attendance_report'),
    path('notify-parents/',            NotifyParentsView.as_view(),               name='notify_parents'),
    path('admin/attendance/<str:pk>/', AdminAttendanceCorrectionView.as_view(),   name='admin_correction'),
]
