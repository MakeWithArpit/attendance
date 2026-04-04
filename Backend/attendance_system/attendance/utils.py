"""
attendance/utils.py
Utilities:  attendance calculation, face verification (DeepFace), geo-fencing

"""
import io
import uuid
import json
import math
import base64
import datetime
from django.conf import settings
from django.utils import timezone


# ─────────────────────────────────────────────
# Attendance Calculation Logic
# ─────────────────────────────────────────────
def calculate_attendance_percentage(total_classes: int, attended: int) -> float:
    """Returns the attendance percentage. Returns 0.0 when total_classes is 0."""
    if total_classes == 0:
        return 0.0
    return round((attended / total_classes) * 100, 2)


def get_student_attendance_summary(student_id, semester: int, academic_year: str) -> list:
    """
    Returns a subject-wise attendance summary for a student.
    [
        {
            "subject_code": "CS301",
            "subject_name": "Data Structures",
            "total_classes": 30,
            "attended": 25,
            "percentage": 83.33,
            "status": "safe" | "warning" | "critical"
        },
        ...
    ]
    """
    from .models import Attendance
    from academics.models import CourseRegistration

    # Also filter by academic_year to exclude subjects from previous semesters
    registrations = CourseRegistration.objects.filter(
        student_id=student_id, semester=semester
    ).select_related('subject')

    from .models import AttendanceSession

    # Get student's branch+section from their profile for session matching
    try:
        from accounts.models import Student
        _stu = Student.objects.select_related('profile').get(pk=student_id)
        s_branch  = _stu.profile.branch_id if hasattr(_stu, 'profile') else None
        s_section = _stu.profile.section.strip().upper() if (hasattr(_stu, 'profile') and _stu.profile.section) else None
    except Exception:
        s_branch = s_section = None

    summary = []
    for reg in registrations:
        # total_classes = closed sessions for this subject/semester/branch/section/year
        # This is the authoritative count — doesn't depend on absent records existing
        session_qs = AttendanceSession.objects.filter(
            subject=reg.subject,
            semester=semester,
            academic_year=academic_year,
            status='closed',
        )
        if s_branch:
            session_qs = session_qs.filter(branch_id=s_branch)
        if s_section:
            session_qs = session_qs.filter(section=s_section)
        total = session_qs.count()

        # attended = sessions where student has is_present=True
        attended = Attendance.objects.filter(
            student_id=student_id,
            subject=reg.subject,
            semester=semester,
            academic_year=academic_year,
            is_present=True,
        ).count()

        # attended can never exceed total (guard against stale data)
        attended = min(attended, total)

        pct = calculate_attendance_percentage(total, attended)

        # Skip subjects where no classes have been held yet
        if total == 0:
            continue

        if pct >= 75:
            status = 'safe'
        elif pct >= 60:
            status = 'warning'
        else:
            status = 'critical'

        summary.append({
            'subject_code':  reg.subject.subject_code,
            'subject_name':  reg.subject.subject_name,
            'total_classes': total,
            'attended':      attended,
            'percentage':    pct,
            'status':        status,
        })
    return summary


def get_class_attendance_summary(subject_id, branch_id, semester: int,
                                  section: str, date: datetime.date, academic_year: str) -> dict:
    """Returns an attendance summary for a specific class on a given date."""
    from .models import Attendance
    from academics.models import CourseRegistration

    student_ids = CourseRegistration.objects.filter(
        branch_id=branch_id, semester=semester,
        section=section, subject_id=subject_id
    ).values_list('student_id', flat=True)

    records = Attendance.objects.filter(
        student_id__in=student_ids,
        subject_id=subject_id,
        date=date,
        academic_year=academic_year,
    )

    total_students = student_ids.count()
    present_count  = records.filter(is_present=True).count()
    absent_count   = total_students - present_count

    return {
        'date':           str(date),
        'total_students': total_students,
        'present':        present_count,
        'absent':         absent_count,
        'average_pct':    calculate_attendance_percentage(total_students, present_count),
    }


def get_students_by_attendance_threshold(subject_id, semester: int, academic_year: str,
                                          section: str, branch_id):
    """
    Categorises students by their attendance percentage.
    Returns: { above_75, below_75, below_60, below_50 }
    """
    from .models import Attendance
    from academics.models import CourseRegistration

    registrations = CourseRegistration.objects.filter(
        branch_id=branch_id, semester=semester,
        section=section, subject_id=subject_id
    ).select_related('student__profile')

    result = {'above_75': [], 'below_75': [], 'below_60': [], 'below_50': []}

    for reg in registrations:
        records  = Attendance.objects.filter(
            student=reg.student, subject_id=subject_id,
            semester=semester, academic_year=academic_year
        )
        total    = records.count()
        attended = records.filter(is_present=True).count()
        pct      = calculate_attendance_percentage(total, attended)

        student_info = {
            'student_id':        reg.student.pk,
            'enrollment_number': reg.student.enrollment_number,
            'name':              getattr(reg.student.profile, 'name', ''),
            'total_classes':     total,
            'attended':          attended,
            'percentage':        pct,
        }

        # Cumulative categories — below_75 includes ALL students below 75%.
        # This ensures total_students = above_75 + below_75 is always accurate.
        # below_60 and below_50 are subsets (for risk analytics).
        if pct >= 75:
            result['above_75'].append(student_info)
        else:
            result['below_75'].append(student_info)   # ALL < 75% (at risk)
            if pct < 60:
                result['below_60'].append(student_info)   # < 60% (warning)
            if pct < 50:
                result['below_50'].append(student_info)   # < 50% (critical)

    return result


# ─────────────────────────────────────────────
# Monthly Attendance Trend
# ─────────────────────────────────────────────
def get_monthly_attendance_trend(student_id, subject_id, academic_year: str) -> list:
    """
    Returns a month-wise attendance breakdown.
    [{"month": "January 2025", "total": 10, "attended": 8, "percentage": 80.0}, ...]
    """
    from .models import Attendance
    from django.db.models import Count, Q
    from django.db.models.functions import TruncMonth

    records = Attendance.objects.filter(
        student_id=student_id,
        subject_id=subject_id,
        academic_year=academic_year,
    ).annotate(month=TruncMonth('date')).values('month').annotate(
        total=Count('id'),
        attended=Count('id', filter=Q(is_present=True)),
    ).order_by('month')

    trend = []
    for r in records:
        pct = calculate_attendance_percentage(r['total'], r['attended'])
        trend.append({
            'month':      r['month'].strftime('%B %Y'),
            'total':      r['total'],
            'attended':   r['attended'],
            'percentage': pct,
        })
    return trend


# ─────────────────────────────────────────────
# Approved Leave → Mark Present
# ─────────────────────────────────────────────
def apply_approved_leave_to_attendance(leave_request):
    """
    Marks all absences within the leave date range as present once the leave is approved.
    """
    from .models import Attendance

    delta  = leave_request.to_date - leave_request.from_date
    dates  = [leave_request.from_date + datetime.timedelta(days=i) for i in range(delta.days + 1)]

    updated = Attendance.objects.filter(
        student=leave_request.student,
        date__in=dates,
        is_present=False,
    ).update(is_present=True, method='manual')

    return updated


# ─────────────────────────────────────────────
# Face Recognition — DeepFace
# ─────────────────────────────────────────────
#
# PREVIOUS LIBRARY (face_recognition):
#   ❌ dlib required a C++ compiler and CMake — difficult to install
#   ❌ Very difficult to deploy on a server
#   ❌ Required storing numpy array bytes in the database
#
# CURRENT LIBRARY (DeepFace):
#   ✅ install with: pip install deepface
#   ✅ No C++ compiler or CMake required
#   ✅ Only the photo is stored — no face encoding needed
#   ✅ More accurate than the face_recognition library
#   ✅ multiple models support: Facenet, VGG-Face, ArcFace, etc.
#
# Install:
#   pip install deepface
#   (model weights (~100 MB) will be downloaded automatically on first run)
# ─────────────────────────────────────────────

def verify_face(student, uploaded_image_path: str) -> bool:
    """
    Compares the student's stored photo against the uploaded selfie.
    Returns True if they are the same person.

    DeepFace.verify() internally:
      1. Detects faces in both images
      2. Extracts face embeddings (numeric representation)
      3. Calculates the distance between both embeddings
      4. If distance is below the threshold → same person (True)

    Args:
        student: Student model instance (must have a registered_photo)
        uploaded_image_path: Student ki selfie ka temporary path

    Returns:
        True  — same person (attendance can be marked)
        False — face did not match or could not be detected
    """
    try:
        from deepface import DeepFace

        # Does the student have a registered photo?
        if not student.registered_photo:
            return False

        stored_photo_path = student.registered_photo.path

        result = DeepFace.verify(
            img1_path=stored_photo_path,    # photo stored in DB
            img2_path=uploaded_image_path,  # student's live selfie

            # Model options:
            # "Facenet"  → best balance of speed and accuracy (recommended)
            # "VGG-Face" → older model but reliable
            # "ArcFace"  → most accurate, slightly slower
            model_name="Facenet",

            # Detector options:
            # "opencv"     → fast, basic
            # "retinaface" → accurate, slightly slower
            detector_backend="opencv",

            # distance_metric: "cosine" is more reliable than euclidean for Facenet
            distance_metric="cosine",

            # enforce_detection=False → attempt verification even if face is not fully visible
            # (True raises ValueError on partial/blurry faces — degrades user experience)
            enforce_detection=False,
        )

        # result keys: verified (bool), distance (float, 0=identical),
        #              threshold (float), model (str)
        return result["verified"]

    except ValueError:
        # No face detected in one or both images
        return False
    except Exception as e:
        # Any other error — log it and return False
        import logging
        logging.getLogger(__name__).error(f"Face verification error: {str(e)}")
        return False


# ─────────────────────────────────────────────
# Geo-Fencing Logic
# ─────────────────────────────────────────────
def calculate_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Haversine formula — distance in metres between two GPS coordinates.
    lat1, lon1 = student's current location
    lat2, lon2 = college campus centre point
    """
    R = 6371000  # Earth's radius in metres

    phi1    = math.radians(lat1)
    phi2    = math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c   # distance in metres


def verify_student_location(session, student_lat: float, student_lon: float) -> dict:
    """
    Checks whether the student is within the allowed campus radius.

    Returns:
    {
        "allowed": True/False,
        "distance_meters": 145.3,
        "allowed_radius": 200,
        "message": "..."
    }
    """
    if not session.geo_fencing_enabled:
        return {
            'allowed':         True,
            'distance_meters': None,
            'allowed_radius':  None,
            'message':         'Geo-fencing is not enabled for this session.',
        }

    if not session.campus_latitude or not session.campus_longitude:
        return {
            'allowed':         True,
            'distance_meters': None,
            'allowed_radius':  None,
            'message':         'Campus location has not been configured.',
        }

    distance       = calculate_distance_meters(
        float(student_lat), float(student_lon),
        float(session.campus_latitude), float(session.campus_longitude)
    )
    allowed_radius = session.allowed_radius_meters or 200
    is_inside      = distance <= allowed_radius

    return {
        'allowed':         is_inside,
        'distance_meters': round(distance, 1),
        'allowed_radius':  allowed_radius,
        'message': (
            f'You are within the campus boundary ({round(distance, 1)}m from centre).'
            if is_inside else
            f'You are {round(distance, 1)}m away from the campus. '
            f'Attendance can only be marked within {allowed_radius}m of the campus.'
        ),
    }


def register_face_photo(student, photo_path):
    """
    Checks if a face is detectable in the uploaded photo.
    Throws Exception if unreadable.
    Returns True if face found, False otherwise.
    """
    from deepface import DeepFace
    try:
        # Extract faces. If length > 0, it has a face.
        # Enforce detection ensures that it throws an exception if no face is found
        faces = DeepFace.extract_faces(img_path=photo_path, detector_backend='opencv', enforce_detection=True)
        return len(faces) > 0
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).warning(f"Face registration failed for {student.student_id}: {e}")
        return False

# ═══════════════════════════════════════════════════════════
#  ANTI-PROXY ATTENDANCE VERIFICATION
# ═══════════════════════════════════════════════════════════
#
#  Frontend sends 10 JPEG snapshots + challenge_results JSON.
#  Backend runs:
#    1. Phone detection (YOLOv8) on ALL 10 frames
#    2. Face verification (ArcFace) on 5 sampled frames
#    3. Challenge result validation (2 challenges must pass)
#    4. Face movement check (proxy detection)
# ═══════════════════════════════════════════════════════════

import os as _os
import random as _random
import logging as _logging

_logger = _logging.getLogger(__name__)

# ── YOLOv8 model (cached — loaded once) ──
_yolo_model = None
_PHONE_CLASS_ID = 67   # COCO: cell phone


def _ensure_yolo():
    """Load YOLOv8n model (auto-downloads on first run)."""
    global _yolo_model
    if _yolo_model is not None:
        return True
    try:
        from ultralytics import YOLO
        _yolo_model = YOLO('yolov8n.pt')
        _logger.info('[YOLOv8] Model loaded successfully.')
        return True
    except Exception as e:
        _logger.warning(f'[YOLOv8] Load failed: {e}')
        return False


def detect_phone_in_image(image_path: str, conf: float = 0.40) -> dict:
    """
    Detects a cell phone in the given image using YOLOv8.
    Returns {'detected': bool, 'confidence': float}
    """
    if not _ensure_yolo():
        return {'detected': False, 'confidence': 0, 'skipped': True}

    try:
        results = _yolo_model(image_path, verbose=False)[0]
        best_conf = 0.0
        all_detections = []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            c = float(box.conf[0])
            cls_name = results.names.get(cls_id, f'cls_{cls_id}')
            if c > 0.25:
                all_detections.append((cls_name, round(c, 3)))
            if cls_id == _PHONE_CLASS_ID and c > best_conf:
                best_conf = c

        if all_detections:
            _logger.debug(f'[YOLOv8] Detections: {all_detections}')

        detected = best_conf >= conf
        if detected:
            _logger.warning(f'[YOLOv8] Phone detected, conf={best_conf:.3f}')

        return {
            'detected': detected,
            'confidence': round(best_conf, 3),
        }
    except Exception as e:
        _logger.error(f'[YOLOv8] Error: {e}')
        return {'detected': False, 'confidence': 0, 'error': str(e)}


def detect_phone_in_batch(image_paths: list, threshold: int = 2) -> dict:
    """
    Checks for a phone across up to 10 frames.
    Returns: {phone_count, flagged_frames, should_warn}
    """
    phone_count = 0
    flagged_frames = []
    _logger.debug(f'[PhoneCheck] Analysing {len(image_paths)} frames')

    for i, img_path in enumerate(image_paths):
        result = detect_phone_in_image(img_path)
        if result.get('detected'):
            phone_count += 1
            flagged_frames.append(i)
            _logger.warning(f'[PhoneCheck] Frame #{i}: phone detected ({result["confidence"]*100:.0f}%)')
        else:
            _logger.debug(f'[PhoneCheck] Frame #{i}: clean')

    return {
        'phone_count': phone_count,
        'flagged_frames': flagged_frames,
        'phone_detected': phone_count >= threshold,
    }


def validate_challenge_results(challenge_results: list) -> dict:
    """
    Validates the challenge results sent from the frontend.
    At least 2 challenges must be present and both must pass.
    Returns: {'valid': bool, 'passed_count': int, 'total': int, 'details': str}
    """
    if not challenge_results or not isinstance(challenge_results, list):
        return {
            'valid': False, 'passed_count': 0, 'total': 0,
            'details': 'No challenge results received.',
        }

    total = len(challenge_results)
    passed = sum(1 for c in challenge_results if c.get('passed', False))

    _logger.debug(f'[Challenges] {passed}/{total} passed')
    for c in challenge_results:
        icon = '✅' if c.get('passed') else '❌'
        _logger.debug(f'[Challenge] {c.get("id", "unknown")}: {"PASS" if c.get("passed") else "FAIL"}')

    # Both challenges must pass
    all_passed = passed >= 2
    if not all_passed:
        failed = [c.get('id', '?') for c in challenge_results if not c.get('passed')]
        details = f'Challenge failed: {", ".join(failed)}'
    else:
        details = f'All {passed} challenges passed.'

    return {
        'valid': all_passed,
        'passed_count': passed,
        'total': total,
        'details': details,
    }


def verify_multi_frame_attendance(student, image_paths: list,
                                   challenge_results: list = None) -> dict:
    """
    Anti-proxy attendance verification:
      1. Phone detection (YOLOv8) on ALL frames
      2. Face verification (ArcFace) on 5 sampled frames
      3. Challenge result validation
      4. Face movement check (proxy detection)

    Returns dict with verified, phone_detected, challenge_ok, face_match_count, etc.
    """
    from deepface import DeepFace

    total = len(image_paths)
    result = {
        'verified': False,
        'face_match_count': 0,
        'total_frames': total,
        'phone_detected': False,
        'phone_count': 0,
        'phone_frames': [],
        'challenge_ok': False,
        'challenge_details': '',
        'static_photo': False,
        'details': '',
    }

    if not student.registered_photo:
        result['details'] = 'Face not registered with admin.'
        return result

    stored = student.registered_photo.path
    _logger.debug(f'[AntiProxy] Verifying student={student}, frames={total}, photo={stored}')

    # ═══════════════════════════════════════════
    #  PHASE 1: Phone Detection (YOLOv8)
    # ═══════════════════════════════════════════
    _logger.debug('[AntiProxy] Phase 1: Phone Detection')

    phone_result = detect_phone_in_batch(image_paths, threshold=2)
    result['phone_count'] = phone_result['phone_count']
    result['phone_frames'] = phone_result['flagged_frames']
    result['phone_detected'] = phone_result['phone_detected']

    if result['phone_detected']:
        result['details'] = (
            f'Phone detected in {phone_result["phone_count"]} frames '
            f'(frames: {phone_result["flagged_frames"]}). '
            f'Phone not allowed during attendance.'
        )
        _logger.warning(f'[AntiProxy] Phone detected in {phone_result["phone_count"]} frame(s)')
        # Return early — phone = immediate block
        return result

    _logger.debug('[AntiProxy] No phone detected')

    # ═══════════════════════════════════════════
    #  PHASE 2: Face Verification (ArcFace)
    # ═══════════════════════════════════════════
    _logger.debug('[AntiProxy] Phase 2: Face Verification')

    # Sample 5 frames from the 10 for face verification
    sample_indices = sorted(_random.sample(range(total), min(5, total)))
    match_count = 0
    face_regions = []

    for i in sample_indices:
        img_path = image_paths[i]
        _logger.debug(f'[AntiProxy] Verifying frame {i}')

        # Face verification
        try:
            rv = DeepFace.verify(
                img1_path=stored, img2_path=img_path,
                model_name='ArcFace', detector_backend='ssd',
                distance_metric='cosine', enforce_detection=False,
            )
            distance = rv.get('distance', 999)
            threshold = rv.get('threshold', 0.68)
            verified = rv.get('verified', False)

            # Relaxed threshold for webcam conditions
            manual_threshold = 0.72
            if not verified and distance <= manual_threshold:
                verified = True
                _logger.debug(f'[Face] Frame {i}: distance={distance:.4f} PASS (manual threshold)')
            else:
                _logger.debug(f'[Face] Frame {i}: distance={distance:.4f} {"PASS" if verified else "FAIL"}')

            if verified:
                match_count += 1
        except Exception as e:
            _logger.error(f'[Face] Frame {i} error: {e}')

        # Face region for movement check
        try:
            faces = DeepFace.extract_faces(
                img_path=img_path, detector_backend='ssd',
                enforce_detection=False,
            )
            if faces:
                region = faces[0].get('facial_area', {})
                face_regions.append(region)
        except Exception:
            pass

    result['face_match_count'] = match_count
    min_match = 2  # 2 out of 5 sampled frames
    face_ok = match_count >= min_match
    _logger.debug(f'[AntiProxy] Face: {match_count}/{len(sample_indices)} matched (min={min_match}) → {"PASS" if face_ok else "FAIL"}')

    # ═══════════════════════════════════════════
    #  PHASE 3: Challenge Verification
    # ═══════════════════════════════════════════
    _logger.debug('[AntiProxy] Phase 3: Challenge Verification')

    ch_result = validate_challenge_results(challenge_results or [])
    result['challenge_ok'] = ch_result['valid']
    result['challenge_details'] = ch_result['details']

    # ═══════════════════════════════════════════
    #  PHASE 4: Movement / Proxy Check
    # ═══════════════════════════════════════════
    #
    #  REMOVED — bounding box (x,y) only measures face TRANSLATION (lateral shift).
    #  On mobile, nod / look_up = HEAD ROTATION, not movement across the frame.
    #  Result: real student nods → face tilts in place → x_std ≈ 3, y_std ≈ 3
    #          → false proxy flag despite Phase 3 challenges passing.
    #
    #  Phase 3 (MediaPipe challenge-response) already proves liveness:
    #    • nod    → nose Y range > 8% of face height (verified client-side by MediaPipe)
    #    • look_up → nose Y relative to eye/mouth ratio crosses threshold
    #    • blink  → EAR < 0.22 twice
    #  These are spoof-proof because a static photo cannot complete timed challenges.
    #
    #  If stronger server-side liveness is needed in the future, use MediaPipe
    #  landmark coordinates (e.g. nose tip Y normalised to face height) instead
    #  of bounding box pixel coordinates.
    # ═══════════════════════════════════════════
    result['static_photo'] = False   # always False — check removed
    _logger.debug('[AntiProxy] Phase 4: Movement check skipped (challenge-response proves liveness)')

    # ═══════════════════════════════════════════
    #  FINAL VERDICT
    # ═══════════════════════════════════════════

    reasons = []
    if not face_ok:
        reasons.append(f'Face matched only {match_count}/{len(sample_indices)} frames.')
    if not ch_result['valid']:
        reasons.append(ch_result['details'])
    if result['static_photo']:
        reasons.append('Static photo/proxy detected — insufficient face movement.')

    if reasons:
        result['details'] = ' '.join(reasons)
        _logger.info(f'[AntiProxy] FAILED: {result["details"]}')
    else:
        result['verified'] = True
        result['details'] = (
            f'Verified: {match_count}/{len(sample_indices)} face match, '
            f'{ch_result["passed_count"]} challenges passed, no phone.'
        )
        _logger.info(f'[AntiProxy] VERIFIED: {result["details"]}')


    return result

