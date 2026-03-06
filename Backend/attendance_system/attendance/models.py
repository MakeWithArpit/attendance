"""
attendance/models.py
Attendance,Leave Requests
"""

from django.db import models
from django.utils import timezone
from accounts.models import Student, Teacher, Branch
from academics.models import Subject


class Attendance(models.Model):
    """
    Core attendance record per student per subject per date.
    """

    METHOD_CHOICES = [
        ("manual", "Manual"),
        ("facial", "Facial Recognition"),
        ("rfid", "RFID"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendance_records"
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    date = models.DateField()
    day = models.CharField(max_length=10)
    semester = models.PositiveSmallIntegerField()
    academic_year = models.CharField(max_length=9)
    is_present = models.BooleanField(default=False)
    marked_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_attendances",
    )
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default="manual")
    marked_at = models.DateTimeField(auto_now_add=True)

    # Geo-fencing — student ki location jab attendance mark hui
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    location_verified = models.BooleanField(
        default=False
    )  # campus ke andar tha ya nahi

    class Meta:
        db_table = "attendance"
        unique_together = ["student", "subject", "date"]
        indexes = [
            models.Index(fields=["student", "subject"]),
            models.Index(fields=["date"]),
            models.Index(fields=["semester", "academic_year"]),
        ]

    def __str__(self):
        status = "Present" if self.is_present else "Absent"
        return f"{self.student.enrollment_number} | {self.subject.subject_code} | {self.date} | {status}"


class AttendanceSession(models.Model):
    """
    Teacher starts a session for attendance.
    Ab facial_enabled flag bhi hai — teacher decide karta hai
    ki is session mein facial recognition allowed hai ya nahi.
    """

    STATUS_CHOICES = [("active", "Active"), ("closed", "Closed")]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    semester = models.PositiveSmallIntegerField()
    section = models.CharField(max_length=1)
    date = models.DateField()
    academic_year = models.CharField(max_length=9)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True) #help_text='Auto-close session after N minutes. 0 = manual close.'
    expires_at = models.DateTimeField(null=True, blank=True) #help_text='Computed at session start. Students cannot mark after this.'

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    # ── Attendance method flags ──────────────────
    facial_enabled = models.BooleanField(default=False)

    # ── Geo-fencing settings ─────────────────────
    geo_fencing_enabled = models.BooleanField(default=False)
    
    # College campus ka center point (admin settings se aa sakta hai)
    campus_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    campus_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    # Kitne meter radius mein hona chahiye (default 200 meter)
    allowed_radius_meters = models.IntegerField(default=200)

    class Meta:
        db_table = "attendance_sessions"

    def __str__(self):
        return f"Session: {self.subject.subject_code} | {self.date} | Facial: {self.facial_enabled}"


class LeaveRequest(models.Model):
    """
    Student applies for leave; teacher approves/rejects.
    Approved leaves are counted as present in attendance.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="leave_requests"
    )
    reason = models.TextField()
    from_date = models.DateField()
    to_date = models.DateField()
    application_file = models.FileField(upload_to="leaves/", blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    applied_on = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_leaves",
    )
    reviewed_on = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        db_table = "leave_requests"

    def __str__(self):
        return f"{self.student.enrollment_number} | {self.from_date} to {self.to_date} | {self.status}"
