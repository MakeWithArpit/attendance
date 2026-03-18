"""
academics/models.py
Subject, CourseRegistration, TimeTable
"""
from django.db import models
from accounts.models import Branch, Teacher, Student


class Subject(models.Model):
    CLASSIFICATION_CHOICES = [
        ('core',      'Core'),
        ('elective',  'Elective'),
        ('lab',       'Lab'),
        ('theory',    'Theory'),
    ]
    TYPE_CHOICES = [
        ('theory', 'Theory'),
        ('practical', 'Practical'),
        ('tutorial', 'Tutorial'),
    ]

    SEMESTER_CHOICES = [(i, f'Semester {i}') for i in range(1, 9)]

    subject_code           = models.CharField(max_length=20, primary_key=True)
    subject_name           = models.CharField(max_length=100)
    subject_classification = models.CharField(max_length=20, choices=CLASSIFICATION_CHOICES)
    subject_type           = models.CharField(max_length=20, choices=TYPE_CHOICES)
    subject_credit         = models.PositiveSmallIntegerField()
    assigned_teacher       = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='subjects'
    )

    # ── Fields for auto-enrollment: defines which branch and semester this subject belongs to ──
    # Once set, new students will be automatically enrolled in this subject
    # branch: e.g. "ECE", "CSE" — optional (NULL = applies to all branches)
    # semester: 1-8 — optional (NULL = applies to all semesters)
    branch   = models.ForeignKey(
        Branch, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='subjects',
        help_text='Branch this subject belongs to (required for auto-enrollment)'
    )
    semester = models.PositiveSmallIntegerField(
        choices=SEMESTER_CHOICES,
        null=True, blank=True,
        help_text='Semester this subject belongs to (required for auto-enrollment)'
    )

    class Meta:
        db_table = 'subjects'

    def __str__(self):
        branch_str = f' [{self.branch_id}]' if self.branch_id else ''
        sem_str    = f' Sem{self.semester}' if self.semester else ''
        return f"{self.subject_code}{branch_str}{sem_str} - {self.subject_name}"


class CourseRegistration(models.Model):
    """
    Links a student to the subjects they are enrolled in
    for a particular semester, branch, and section.
    """
    SEMESTER_CHOICES = [(i, f'Semester {i}') for i in range(1, 9)]
    SECTION_CHOICES  = [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]

    student  = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='course_registrations')
    branch   = models.ForeignKey(Branch, on_delete=models.CASCADE)
    subject  = models.ForeignKey(Subject, on_delete=models.CASCADE)
    semester = models.PositiveSmallIntegerField(choices=SEMESTER_CHOICES)
    section  = models.CharField(max_length=1, choices=SECTION_CHOICES)

    class Meta:
        db_table = 'course_registrations'
        unique_together = ['student', 'subject', 'semester']

    def __str__(self):
        return f"{self.student.enrollment_number} - {self.subject.subject_code}"


class TimeTable(models.Model):
    """
    Weekly timetable created by admin; appears in teacher's dashboard.
    """
    DAY_CHOICES = [
        ('Monday', 'Monday'), ('Tuesday', 'Tuesday'), ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'), ('Friday', 'Friday'), ('Saturday', 'Saturday'),
    ]
    SEMESTER_CHOICES = [(i, f'Semester {i}') for i in range(1, 9)]
    SECTION_CHOICES  = [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]

    branch        = models.ForeignKey(Branch, on_delete=models.CASCADE)
    semester      = models.PositiveSmallIntegerField(choices=SEMESTER_CHOICES)
    section       = models.CharField(max_length=1, choices=SECTION_CHOICES)
    day           = models.CharField(max_length=10, choices=DAY_CHOICES)
    period_number = models.PositiveSmallIntegerField()
    subject       = models.ForeignKey(Subject, on_delete=models.CASCADE)
    start_time    = models.TimeField()
    end_time      = models.TimeField()
    academic_year = models.CharField(max_length=9)  # e.g., "2024-2025"

    class Meta:
        db_table = 'timetables'
        unique_together = ['branch', 'semester', 'section', 'day', 'period_number', 'academic_year']

    def __str__(self):
        return f"{self.branch} | Sem {self.semester} | {self.day} | Period {self.period_number}"