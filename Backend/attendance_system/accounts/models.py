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
                            help_text="Unique student ID e.g. BCS2024001 — also used as the login username.")
    user              = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student')
    enrollment_number = models.CharField(max_length=20, unique=True)
    roll_number       = models.CharField(max_length=20)
    rfid_number       = models.CharField(max_length=50, blank=True, null=True, unique=True)
    aadhar_number     = models.CharField(max_length=12, blank=True, null=True, unique=True)

    # ── Facial Recognition ───────────────────────────────────────────────────
    # PURANA tha: face_encoding = BinaryField  (numpy array bytes store hote the)
    # New approach: registered_photo = ImageField (store only the photo)
    #
    # Kyun badla?
    #   face_recognition required dlib/CMake — difficult to install.
    #   DeepFace compares photos directly — no face encoding required.
    #   Admin/Teacher uploads a clear photo of the student once.
    #   The selfie submitted later is compared against this stored photo.
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
        """Returns True if the student has a registered face photo."""
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
    domicile_state  = models.CharField(max_length=50, blank=True, default='')
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
    father_name        = models.CharField(max_length=100, blank=True, default='')
    father_occupation  = models.CharField(max_length=100, blank=True)
    father_mobile      = models.CharField(max_length=15, blank=True, default='')
    father_email       = models.EmailField(blank=True, null=True)
    mother_name        = models.CharField(max_length=100, blank=True, default='')
    mother_occupation  = models.CharField(max_length=100, blank=True)
    mother_mobile      = models.CharField(max_length=15, blank=True, default='')

    class Meta:
        db_table = 'parent_details'


class PermanentAddress(models.Model):
    student       = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='permanent_address')
    address_line1 = models.CharField(max_length=200, blank=True, default='')
    address_line2 = models.CharField(max_length=200, blank=True, default='')
    address_line3 = models.CharField(max_length=200, blank=True, default='')
    state         = models.CharField(max_length=50,  blank=True, default='')
    place         = models.CharField(max_length=100, blank=True, default='')
    pincode       = models.CharField(max_length=6,   blank=True, default='')

    class Meta:
        db_table = 'permanent_addresses'


class PresentAddress(models.Model):
    student       = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='present_address')
    address_line1 = models.CharField(max_length=200, blank=True, default='')
    address_line2 = models.CharField(max_length=200, blank=True, default='')
    address_line3 = models.CharField(max_length=200, blank=True, default='')
    state         = models.CharField(max_length=50,  blank=True, default='')
    place         = models.CharField(max_length=100, blank=True, default='')
    pincode       = models.CharField(max_length=6,   blank=True, default='')

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


# ─────────────────────────────────────────────
# WebAuthn Passkey Credential
# ─────────────────────────────────────────────
class WebAuthnCredential(models.Model):
    """
    Stores a student's WebAuthn passkey credential (registered once per device).

    Flow:
      Registration  → browser generates a public/private key pair on the device.
                      Private key never leaves the device.
                      We store only the public key + credential_id here.

      Authentication → browser signs a server challenge with the private key.
                       We verify the signature using the stored public_key.
                       sign_count is incremented each time — if the incoming
                       count is <= stored count, it signals a cloned authenticator
                       (replay / proxy attempt) and we reject the request.

    One credential per student (enforced via OneToOneField).
    Admin can delete this record (along with DeviceToken) to let a student
    re-register from a new device — see AdminDeviceResetView.
    """

    student       = models.OneToOneField(
        'Student',
        on_delete=models.CASCADE,
        related_name='webauthn_credential',
    )
    # Raw credential ID returned by the browser (base64url-encoded bytes stored as text)
    credential_id = models.TextField(unique=True)
    # CBOR-encoded public key (base64url stored as text) — used to verify signatures
    public_key    = models.TextField()
    # Monotonically increasing counter — each successful auth increments this.
    # A value that doesn't increase signals a cloned authenticator.
    sign_count    = models.PositiveIntegerField(default=0)
    # Human-readable label — e.g. "Chrome on Android", "Safari on iPhone"
    device_label  = models.CharField(max_length=200, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'webauthn_credentials'

    def __str__(self):
        return f"{self.student_id} — passkey ({self.device_label or 'unknown device'})"