"""
accounts/models.py
Custom User model with role-based access: Student, Teacher, Admin

"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


# ─────────────────────────────────────────────
# Custom User Manager
# ─────────────────────────────────────────────
class UserManager(BaseUserManager):

    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("Username is required")
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(username, password, **extra_fields)


# ─────────────────────────────────────────────
# Base User Model (Student ID / Employee ID login)
# ─────────────────────────────────────────────
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin',   'Admin'),
    ]

    username   = models.CharField(max_length=50, unique=True)
    role       = models.CharField(max_length=10, choices=ROLE_CHOICES)
    is_active  = models.BooleanField(default=True)
    is_staff   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD  = 'username'
    REQUIRED_FIELDS = ['role']

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"{self.username} ({self.role})"


# ─────────────────────────────────────────────
# Branch
# ─────────────────────────────────────────────
class Branch(models.Model):
    branch_code = models.CharField(max_length=10, primary_key=True)
    branch_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'branches'

    def __str__(self):
        return f"{self.branch_code} - {self.branch_name}"


# ─────────────────────────────────────────────
# Student Models
# ─────────────────────────────────────────────
class Student(models.Model):
    student_id        = models.CharField(max_length=20, primary_key=True,
                            help_text="Unique student ID e.g. BCS2024001 — login username bhi yahi hota hai.")
    user              = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student')
    enrollment_number = models.CharField(max_length=20, unique=True)
    roll_number       = models.CharField(max_length=20)
    rfid_number       = models.CharField(max_length=50, blank=True, null=True, unique=True)
    aadhar_number     = models.CharField(max_length=12, blank=True, null=True, unique=True)

    # ── Facial Recognition ───────────────────────────────────────────────────
    # PURANA tha: face_encoding = BinaryField  (numpy array bytes store hote the)
    # NAYA hai:   registered_photo = ImageField (sirf photo store karo)
    #
    # Kyun badla?
    #   face_recognition library mein dlib/CMake chahiye tha — install karna mushkil tha.
    #   DeepFace library directly do photos compare karti hai — encoding ki zarurat nahi.
    #   Admin/Teacher ek baar student ki clear photo upload karta hai.
    #   Baad mein student jo selfie bhejta hai use is photo se compare kiya jaata hai.
    registered_photo  = models.ImageField(
        upload_to='students/face_photos/',
        blank=True,
        null=True,
        help_text="Facial recognition ke liye student ki clear front-facing photo. "
                  "Admin ya Teacher upload karta hai."
    )

    class Meta:
        db_table = 'students'

    def __str__(self):
        return self.student_id

    @property
    def has_face_registered(self):
        """Frontend ko batata hai ki face registered hai ya nahi."""
        return bool(self.registered_photo)


class StudentProfile(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]
    MARITAL_CHOICES = [('single', 'Single'), ('married', 'Married')]

    student         = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='profile')
    name            = models.CharField(max_length=100)
    dob             = models.DateField()
    gender          = models.CharField(max_length=1, choices=GENDER_CHOICES)
    mobile_number   = models.CharField(max_length=15)
    email           = models.EmailField(blank=True, null=True)
    nationality     = models.CharField(max_length=50, default='Indian')
    marital_status  = models.CharField(max_length=10, choices=MARITAL_CHOICES, default='single')
    domicile_state  = models.CharField(max_length=50)
    date_of_joining = models.DateField()
    academic_year    = models.CharField(max_length=9)
    section          = models.CharField(max_length=10, blank=True, null=True)
    current_semester = models.IntegerField(blank=True, null=True)
    branch           = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True)
    photo           = models.ImageField(upload_to='students/photos/', blank=True, null=True)

    class Meta:
        db_table = 'student_profiles'

    def __str__(self):
        return self.name


class ParentDetail(models.Model):
    student            = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='parent_detail')
    father_name        = models.CharField(max_length=100)
    father_occupation  = models.CharField(max_length=100, blank=True)
    father_mobile      = models.CharField(max_length=15)
    father_email       = models.EmailField(blank=True, null=True)
    mother_name        = models.CharField(max_length=100)
    mother_occupation  = models.CharField(max_length=100, blank=True)
    mother_mobile      = models.CharField(max_length=15)

    class Meta:
        db_table = 'parent_details'


class PermanentAddress(models.Model):
    student       = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='permanent_address')
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    address_line3 = models.CharField(max_length=200, blank=True)
    state         = models.CharField(max_length=50)
    place         = models.CharField(max_length=100)
    pincode       = models.CharField(max_length=6)

    class Meta:
        db_table = 'permanent_addresses'


class PresentAddress(models.Model):
    student       = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='present_address')
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    address_line3 = models.CharField(max_length=200, blank=True)
    state         = models.CharField(max_length=50)
    place         = models.CharField(max_length=100)
    pincode       = models.CharField(max_length=6)

    class Meta:
        db_table = 'present_addresses'


# ─────────────────────────────────────────────
# Teacher Models
# ─────────────────────────────────────────────
class Teacher(models.Model):
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher')
    employee_id = models.CharField(max_length=20, primary_key=True)
    department  = models.CharField(max_length=100)
    name        = models.CharField(max_length=100)
    email       = models.EmailField()
    mobile      = models.CharField(max_length=15)
    designation = models.CharField(max_length=100, blank=True)
    photo       = models.ImageField(upload_to='teachers/photos/', blank=True, null=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        db_table = 'teachers'

    def __str__(self):
        return f"{self.employee_id} - {self.name}"


# ─────────────────────────────────────────────
# Password Reset OTP
# ─────────────────────────────────────────────
class PasswordResetOTP(models.Model):
    """
    Jab user 'Forgot Password' karta hai:
    1. Ek 6-digit OTP generate hota hai
    2. User ki email par bheja jaata hai
    3. Yahan store hota hai with 10 min expiry
    4. User OTP + new password bhejta hai → verified → password change
    """
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_requests')
    otp        = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used    = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_reset_otps'

    @property
    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"OTP for {self.user.username} | Valid: {self.is_valid}"


# ─────────────────────────────────────────────
# Device Token
# ─────────────────────────────────────────────
class DeviceToken(models.Model):
    """
    Stores the browser fingerprint (device_id) for each student.
    First login from a device registers it automatically.
    New device requires OTP verification before login.
    Admin can reset (clear) device tokens.
    """
    student        = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='device_tokens')
    device_id      = models.CharField(max_length=100)
    device_label   = models.CharField(max_length=200, blank=True, help_text='User-Agent snippet')
    is_primary     = models.BooleanField(default=True)
    registered_at  = models.DateTimeField(auto_now_add=True)
    last_login     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'device_tokens'
        unique_together = ('student', 'device_id')

    def __str__(self):
        return f"{self.student_id} — {self.device_id[:12]}"