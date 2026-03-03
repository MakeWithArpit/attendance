"""
academics/views.py
"""
import datetime
from rest_framework import generics, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from .models import Subject, CourseRegistration, TimeTable
from .serializers import SubjectSerializer, CourseRegistrationSerializer, TimeTableSerializer
from accounts.permissions import IsAdmin, IsTeacherOrAdmin


class SubjectListCreateView(generics.ListCreateAPIView):
    queryset = Subject.objects.select_related('assigned_teacher').all()
    serializer_class = SubjectSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['subject_code', 'subject_name']
    filterset_fields = ['subject_type', 'subject_classification']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [IsTeacherOrAdmin()]


class SubjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAdmin]


class CourseRegistrationListCreateView(generics.ListCreateAPIView):
    """
    Admin enrolls students into subjects.
    Teacher/Admin can query registrations to get student lists.
    GET params: branch, semester, section, subject
    """
    serializer_class = CourseRegistrationSerializer
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['branch', 'semester', 'section', 'subject', 'student']

    def get_queryset(self):
        return CourseRegistration.objects.select_related(
            'student__profile', 'subject', 'branch'
        ).all()

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [IsTeacherOrAdmin()]


class BulkCourseRegistrationView(APIView):
    """
    POST /api/academics/course-registrations/bulk/
    Enroll multiple students at once
    Body: { branch, semester, section, subject, student_ids: [1,2,3] }
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        branch_id   = request.data.get('branch')
        semester    = request.data.get('semester')
        section     = request.data.get('section')
        subject_id  = request.data.get('subject')
        student_ids = request.data.get('student_ids', [])

        created = []
        for sid in student_ids:
            reg, _ = CourseRegistration.objects.get_or_create(
                student_id=sid,
                branch_id=branch_id,
                subject_id=subject_id,
                semester=semester,
                section=section,
            )
            created.append(reg.id)

        return Response({'message': f'{len(created)} registrations created/found', 'ids': created})


class TimeTableListCreateView(generics.ListCreateAPIView):
    """
    Admin creates timetable; teachers can view their schedule.
    """
    serializer_class = TimeTableSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['branch', 'semester', 'section', 'day', 'academic_year']

    def get_queryset(self):
        return TimeTable.objects.select_related('branch', 'subject', 'subject__assigned_teacher').all()

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [IsTeacherOrAdmin()]


class MyTimetableView(APIView):
    """
    GET /api/academics/my-timetable/
    Teacher sees their own weekly schedule (based on assigned subjects).
    Also returns today's schedule highlighted.
    """
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        teacher = getattr(request.user, 'teacher', None)
        if not teacher:
            return Response({'error': 'Not a teacher account'}, status=400)

        # Get all subjects assigned to this teacher
        teacher_subjects = teacher.subjects.values_list('pk', flat=True)

        timetable = TimeTable.objects.filter(
            subject__in=teacher_subjects
        ).select_related('branch', 'subject').order_by('day', 'period_number')

        today = datetime.date.today().strftime('%A')  # e.g., "Monday"
        today_schedule = timetable.filter(day=today)
        weekly_schedule = timetable

        return Response({
            'today': today,
            'today_schedule': TimeTableSerializer(today_schedule, many=True).data,
            'weekly_schedule': TimeTableSerializer(weekly_schedule, many=True).data,
        })


