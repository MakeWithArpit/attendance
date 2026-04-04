"""
accounts/serializers.py
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, Student, StudentProfile, Teacher, Branch, ParentDetail, PermanentAddress, PresentAddress



# ─────────────────────────────────────────────
# Custom JWT Token - adds role & name to token response
# ─────────────────────────────────────────────
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        data['role'] = user.role
        data['user_id'] = user.id
        data['username'] = user.username

        # Add name based on role
        if user.role == 'student' and hasattr(user, 'student'):
            try:
                data['name'] = user.student.profile.name
                data['enrollment'] = user.student.enrollment_number
            except Exception:
                pass
        elif user.role == 'teacher' and hasattr(user, 'teacher'):
            data['name'] = user.teacher.name
            data['employee_id'] = user.teacher.employee_id
        elif user.role == 'admin':
            data['name'] = 'Administrator'

        return data


# ─────────────────────────────────────────────
# Branch
# ─────────────────────────────────────────────
class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = '__all__'


# ─────────────────────────────────────────────
# Student Serializers
# ─────────────────────────────────────────────
class StudentProfileSerializer(serializers.ModelSerializer):
    # Explicitly mark fields that may be blank in the creation form
    name             = serializers.CharField()
    domicile_state   = serializers.CharField(required=False, allow_blank=True, default='')
    date_of_joining  = serializers.DateField(required=False, allow_null=True, default=None)
    section          = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)
    current_semester = serializers.IntegerField(required=False, allow_null=True, default=None)
    email            = serializers.EmailField(required=False, allow_blank=True, allow_null=True, default=None)
    photo            = serializers.ImageField(required=False, allow_null=True, default=None)
    # branch: accepts branch_code string (pk), optional — admin may not always select one
    branch           = serializers.SlugRelatedField(
        slug_field='branch_code',
        queryset=Branch.objects.all(),
        required=False,
        allow_null=True,
        default=None,
    )

    class Meta:
        model = StudentProfile
        exclude = ['student']


class ParentDetailSerializer(serializers.ModelSerializer):
    # All parent fields are optional — guardian may not have both parents' info
    father_name       = serializers.CharField(required=False, allow_blank=True, default='')
    father_mobile     = serializers.CharField(required=False, allow_blank=True, default='')
    father_occupation = serializers.CharField(required=False, allow_blank=True, default='')
    father_email      = serializers.EmailField(required=False, allow_blank=True, allow_null=True, default=None)
    mother_name       = serializers.CharField(required=False, allow_blank=True, default='')
    mother_mobile     = serializers.CharField(required=False, allow_blank=True, default='')
    mother_occupation = serializers.CharField(required=False, allow_blank=True, default='')

    class Meta:
        model = ParentDetail
        exclude = ['student']


class PermanentAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermanentAddress
        exclude = ['student']


class PresentAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = PresentAddress
        exclude = ['student']


class StudentSerializer(serializers.ModelSerializer):
    profile           = StudentProfileSerializer(read_only=True)
    parent_detail     = ParentDetailSerializer(read_only=True)
    permanent_address = PermanentAddressSerializer(read_only=True)
    present_address   = PresentAddressSerializer(read_only=True)
    has_face_registered = serializers.BooleanField(read_only=True)

    class Meta:
        model = Student
        fields = [
            'student_id', 'enrollment_number', 'roll_number', 'rfid_number',
            'has_face_registered',
            'profile', 'parent_detail', 'permanent_address', 'present_address'
        ]

class StudentCreateSerializer(serializers.Serializer):
    """Used by admin to create a new student with full details"""
    # User credentials
    student_id = serializers.CharField()
    password   = serializers.CharField(write_only=True)

    # Student basic info
    enrollment_number = serializers.CharField()
    roll_number       = serializers.CharField()
    rfid_number       = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    aadhar_number     = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    # Face recognition photo (optional at registration — can be uploaded later too)
    registered_photo  = serializers.ImageField(
        required=False, allow_null=True,
        help_text="Student ki clear front-facing photo for face recognition."
    )

    # Profile
    profile = StudentProfileSerializer()

    # Optional nested
    parent_detail     = ParentDetailSerializer(required=False)
    permanent_address = PermanentAddressSerializer(required=False)
    present_address   = PresentAddressSerializer(required=False)

    def create(self, validated_data):
        profile_data         = validated_data.pop('profile')
        parent_data          = validated_data.pop('parent_detail', None)
        permanent_addr_data  = validated_data.pop('permanent_address', None)
        present_addr_data    = validated_data.pop('present_address', None)
        registered_photo     = validated_data.pop('registered_photo', None)

        # Create User
        from django.db import IntegrityError, transaction
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=validated_data['student_id'],
                    password=validated_data['password'],
                    role='student'
                )
                student = Student.objects.create(
                    student_id=validated_data['student_id'],
                    user=user,
                    enrollment_number=validated_data['enrollment_number'],
                    roll_number=validated_data['roll_number'],
                    rfid_number=validated_data.get('rfid_number') or None,
                    aadhar_number=validated_data.get('aadhar_number') or None,
                )
        except IntegrityError as e:
            err = str(e).lower()
            if 'student_id' in err or 'username' in err or 'users' in err:
                raise serializers.ValidationError(
                    {'student_id': f"Student ID '{validated_data['student_id']}' already exists."}
                )
            elif 'enrollment' in err:
                raise serializers.ValidationError(
                    {'enrollment_number': 'This enrollment number is already registered.'}
                )
            elif 'aadhar' in err:
                raise serializers.ValidationError(
                    {'aadhar_number': 'This Aadhar number is already registered.'}
                )
            elif 'rfid' in err:
                raise serializers.ValidationError(
                    {'rfid_number': 'This RFID number is already registered.'}
                )
            else:
                raise serializers.ValidationError({'non_field_errors': f'Duplicate entry: {str(e)}'})

        # Save face photo if provided
        if registered_photo:
            student.registered_photo.save(
                f"face_{student.enrollment_number}.jpg",
                registered_photo,
                save=True
            )

        StudentProfile.objects.create(student=student, **profile_data)

        if parent_data:
            ParentDetail.objects.create(student=student, **parent_data)
        if permanent_addr_data:
            PermanentAddress.objects.create(student=student, **permanent_addr_data)
        if present_addr_data:
            PresentAddress.objects.create(student=student, **present_addr_data)

        return student


# ─────────────────────────────────────────────
# Teacher Serializers
# ─────────────────────────────────────────────
class TeacherSerializer(serializers.ModelSerializer):
    assigned_subject_count = serializers.SerializerMethodField()
    assigned_subjects      = serializers.SerializerMethodField()

    class Meta:
        model  = Teacher
        fields = '__all__'

    def get_assigned_subject_count(self, obj):
        return obj.subjects.count()

    def get_assigned_subjects(self, obj):
        return list(obj.subjects.values('subject_code', 'subject_name', 'branch_id', 'semester'))


class TeacherCreateSerializer(serializers.Serializer):
    employee_id = serializers.CharField()
    password    = serializers.CharField(write_only=True)
    name        = serializers.CharField()
    email       = serializers.EmailField()
    mobile      = serializers.CharField()
    department  = serializers.CharField()
    designation = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['employee_id'],
            password=validated_data['password'],
            role='teacher'
        )
        teacher = Teacher.objects.create(
            user=user,
            employee_id=validated_data['employee_id'],
            name=validated_data['name'],
            email=validated_data['email'],
            mobile=validated_data['mobile'],
            department=validated_data['department'],
            designation=validated_data.get('designation', ''),
        )
        return teacher


# ─────────────────────────────────────────────
# Forgot Password Serializers
# ─────────────────────────────────────────────
class ForgotPasswordSerializer(serializers.Serializer):
    """
    Step 1: User submits their username.
    System looks up the registered email for that user and sends an OTP.
    """
    username = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get('username', '').strip()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError({'error': 'No account found with this username.'})

        email = self._get_user_email(user)
        if not email:
            raise serializers.ValidationError({
                'error': 'No email address is registered for this account. Please contact the admin.'
            })
        attrs['username'] = username
        return attrs

    def validate_username(self, value):
        return value  # handled in validate()

    def _get_user_email(self, user):
        if user.role == 'student':
            try:
                return user.student.profile.email
            except Exception:
                return None
        elif user.role == 'teacher':
            try:
                return user.teacher.email
            except Exception:
                return None
        elif user.role == 'admin':
            return getattr(user, 'email', None)
        return None


class VerifyOTPSerializer(serializers.Serializer):
    """
    Step 2: User submits the OTP along with the new password.
    OTP sahi aur valid hona chahiye (10 min ke andar).
    """
    username     = serializers.CharField()
    otp          = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(min_length=8, write_only=True)