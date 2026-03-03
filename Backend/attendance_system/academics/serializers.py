"""
academics/serializers.py
"""
from rest_framework import serializers
from .models import Subject, CourseRegistration, TimeTable


class SubjectSerializer(serializers.ModelSerializer):
    assigned_teacher_name = serializers.CharField(source='assigned_teacher.name', read_only=True)

    class Meta:
        model = Subject
        fields = '__all__'


class CourseRegistrationSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.subject_name', read_only=True)
    subject_code = serializers.CharField(source='subject.subject_code', read_only=True)

    class Meta:
        model = CourseRegistration
        fields = '__all__'


class TimeTableSerializer(serializers.ModelSerializer):
    subject_name         = serializers.CharField(source='subject.subject_name', read_only=True)
    teacher_name         = serializers.CharField(source='subject.assigned_teacher.name', read_only=True)
    branch_name          = serializers.CharField(source='branch.branch_name', read_only=True)

    class Meta:
        model = TimeTable
        fields = '__all__'
