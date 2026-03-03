"""
attendance/serializers.py
"""
from rest_framework import serializers
from .models import Attendance, AttendanceSession, LeaveRequest


class AttendanceSerializer(serializers.ModelSerializer):
    student_name       = serializers.CharField(source='student.profile.name', read_only=True)
    enrollment_number  = serializers.CharField(source='student.enrollment_number', read_only=True)
    subject_name       = serializers.CharField(source='subject.subject_name', read_only=True)
    subject_code       = serializers.CharField(source='subject.subject_code', read_only=True)

    class Meta:
        model = Attendance
        fields = '__all__'


class AttendanceSessionSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.subject_name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.name', read_only=True)

    class Meta:
        model = AttendanceSession
        fields = '__all__'


class LeaveRequestSerializer(serializers.ModelSerializer):
    student_name       = serializers.CharField(source='student.profile.name', read_only=True)
    enrollment_number  = serializers.CharField(source='student.enrollment_number', read_only=True)
    reviewer_name      = serializers.CharField(source='reviewed_by.name', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = '__all__'
        read_only_fields = ['student', 'status', 'reviewed_by', 'reviewed_on', 'applied_on']


class BulkAttendanceSerializer(serializers.Serializer):
    """
    Used when teacher marks attendance for entire class.
    """
    session_id    = serializers.IntegerField()
    academic_year = serializers.CharField()
    attendance    = serializers.ListField(
        child=serializers.DictField()
        # Each item: {"student_id": 1, "is_present": true}
    )
