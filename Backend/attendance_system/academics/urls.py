"""
academics/urls.py
"""
from django.urls import path
from .views import (
    SubjectListCreateView, SubjectDetailView,
    CourseRegistrationListCreateView, BulkCourseRegistrationView,
    TimeTableListCreateView, MyTimetableView,
)

urlpatterns = [
    path('subjects/',                    SubjectListCreateView.as_view(),        name='subject_list'),
    path('subjects/<int:pk>/',           SubjectDetailView.as_view(),            name='subject_detail'),
    path('course-registrations/',        CourseRegistrationListCreateView.as_view(), name='course_reg_list'),
    path('course-registrations/bulk/',   BulkCourseRegistrationView.as_view(),   name='course_reg_bulk'),
    path('timetable/',                   TimeTableListCreateView.as_view(),       name='timetable_list'),
    path('my-timetable/',               MyTimetableView.as_view(),              name='my_timetable'),
]
