"""
attendance/urls.py
"""
from django.urls import path
from .views import (
    StartAttendanceSessionView,
    BulkManualAttendanceView,
    RegisterFaceView, FacialAttendanceView, ActiveSessionsForStudentView,
    RFIDAttendanceView, BulkRFIDAttendanceView,
    AttendanceListView, AttendanceEditView,
    StudentAttendanceSummaryView,
    LeaveRequestListCreateView, LeaveRequestActionView,
    TeacherDashboardView,
)

urlpatterns = [
    # Session
    path('sessions/start/',          StartAttendanceSessionView.as_view(),    name='start_session'),
    path('sessions/active/',         ActiveSessionsForStudentView.as_view(),  name='active_sessions'),

    # Method 1 - Manual
    path('mark/manual/',             BulkManualAttendanceView.as_view(),  name='manual_attendance'),

    # Method 2 - Facial Recognition
    path('face/register/',           RegisterFaceView.as_view(),          name='register_face'),
    path('face/mark/',               FacialAttendanceView.as_view(),      name='facial_attendance'),

    # Method 3 - RFID
    path('rfid/mark/',               RFIDAttendanceView.as_view(),        name='rfid_attendance'),
    path('rfid/bulk/',               BulkRFIDAttendanceView.as_view(),    name='rfid_bulk'),

    # View & Edit
    path('',                         AttendanceListView.as_view(),        name='attendance_list'),
    path('edit/',                    AttendanceEditView.as_view(),        name='attendance_edit'),

    # Student's own
    path('my-summary/',              StudentAttendanceSummaryView.as_view(), name='my_attendance'),

    # Leave
    path('leaves/',                  LeaveRequestListCreateView.as_view(),   name='leave_list'),
    path('leaves/<int:pk>/action/',  LeaveRequestActionView.as_view(),       name='leave_action'),

    # Dashboard
    path('dashboard/teacher/',       TeacherDashboardView.as_view(),         name='teacher_dashboard'),
]
