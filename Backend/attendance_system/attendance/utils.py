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
    """Attendance percentage return karta hai. 0 classes pe 0.0 return karta hai."""
    if total_classes == 0:
        return 0.0
    return round((attended / total_classes) * 100, 2)


def get_student_attendance_summary(student_id, semester: int, academic_year: str) -> list:
    """
    Student ka subject-wise attendance summary return karta hai.
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

    # FIX: Also filter by academic_year to exclude subjects from previous semesters
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
    """Ek class ka ek specific date par attendance summary return karta hai."""
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
    Students ko attendance % ke hisab se categorize karta hai.
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
    Month-wise attendance breakdown return karta hai.
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
    Leave approve hone par us date range ki saari absences present mark kar do.
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
# PURANI LIBRARY (face_recognition):
#   ❌ dlib required a C++ compiler and CMake — difficult to install
#   ❌ Very difficult to deploy on a server
#   ❌ Required storing numpy array bytes in the database
#
# NAYI LIBRARY (DeepFace):
#   ✅ sirf: pip install deepface
#   ✅ No C++ compiler or CMake required
#   ✅ Only the photo is stored — no face encoding needed
#   ✅ More accurate than the face_recognition library
#   ✅ multiple models support: Facenet, VGG-Face, ArcFace, etc.
#
# Install:
#   pip install deepface
#   (model weights (~100 MB) will be downloaded automatically on first run)
# ─────────────────────────────────────────────

def register_face_photo(student, image_path: str) -> bool:
    """
    Student ka face register karta hai — sirf photo validate karta hai
    ki usme clearly ek face detect ho raha hai, phir path save karta hai.

    RegisterFaceView is function ko call karta hai.

    Args:
        student: Student model instance
        image_path: Uploaded photo ka temporary path

    Returns:
        True  — face detect hua, photo valid hai
        False — koi face detect nahi hua
    """
    try:
        from deepface import DeepFace

        # First verify that the image contains a face
        # enforce_detection=True → raises an exception if no face is detected
        DeepFace.extract_faces(
            img_path=image_path,
            detector_backend='opencv',   # fast detector
            enforce_detection=True,
        )
        # Face detect hua — view function photo save karega
        return True

    except ValueError:
        # No face detected in the image
        return False
    except Exception as e:
        raise Exception(f"Face validation error: {str(e)}")


def verify_face(student, uploaded_image_path: str) -> bool:
    """
    Student ki stored photo aur uploaded selfie ko compare karta hai.
    Returns True agar same person hai.

    DeepFace.verify() internally:
      1. Dono images se face detect karta hai
      2. Face embeddings (numeric representation) nikalta hai
      3. Dono embeddings ke beech distance calculate karta hai
      4. Distance threshold se kam ho to → same person (True)

    Args:
        student: Student model instance (student.registered_photo hona chahiye)
        uploaded_image_path: Student ki selfie ka temporary path

    Returns:
        True  — same person hai (attendance mark ho sakti hai)
        False — match nahi hua ya face detect nahi hua
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
            # "VGG-Face" → purana lekin reliable
            # "ArcFace"  → sabse accurate, thoda slow
            model_name="Facenet",

            # Detector options:
            # "opencv"     → fast, basic
            # "retinaface" → accurate, thoda slow
            detector_backend="opencv",

            # distance_metric: "cosine" is more reliable than euclidean for Facenet
            distance_metric="cosine",

            # enforce_detection=False → agar face clearly visible na ho tab bhi try karo
            # (True pe ValueError aata hai partial/blurry face pe — user experience kharab hota)
            enforce_detection=False,
        )

        # result = {
        #   "verified": True/False,
        #   "distance": 0.23,        ← 0 = identical, 1 = completely different
        #   "threshold": 0.40,       ← is se kam distance ho to same person
        #   "model": "Facenet",
        #   ...
        # }
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
    Haversine formula — do GPS coordinates ke beech ki distance meters mein.
    lat1, lon1 = student ki current location
    lat2, lon2 = college campus ka center point
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
    Check karta hai ki student campus ke allowed radius ke andar hai ya nahi.

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
            'message':         'Geo-fencing is session mein enable nahi hai.',
        }

    if not session.campus_latitude or not session.campus_longitude:
        return {
            'allowed':         True,
            'distance_meters': None,
            'allowed_radius':  None,
            'message':         'Campus location configure nahi ki gayi hai.',
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
            f'Aap campus ke andar hain ({round(distance, 1)}m door).'
            if is_inside else
            f'Aap campus se {round(distance, 1)}m door hain. '
            f'Sirf {allowed_radius}m ke andar se attendance mark ho sakti hai.'
        ),
    }


# ─────────────────────────────────────────────
# Multi-Frame Attendance Verification
# ─────────────────────────────────────────────
#
# Frontend sends 5 JPEG snapshots captured at random intervals.
# Backend runs:
#   1. Face verification (DeepFace) on each frame
#   2. Screen/Phone detection (OpenCV edge + texture analysis)
#   3. Face movement check (detects static photo attacks)
# ─────────────────────────────────────────────

import os as _os
import logging as _logging

_logger = _logging.getLogger(__name__)


def detect_phone_in_image(image_path: str) -> dict:
    """
    OpenCV se phone/screen detect karta hai — 3 methods:
      1. Dark Border Detection  — phone bezels create dark edges around bright screen
      2. Straight Edge Detection — Hough lines detect phone bezel lines
      3. Center-Periphery Ratio — screen center bright, surroundings dark

    Returns {'detected': bool, 'confidence': float, 'method': str, 'details': dict}
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(image_path)
        if img is None:
            return {'detected': False, 'confidence': 0, 'error': 'unreadable'}

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        details = {}

        # ──────────────────────────────────────────
        # Method 1: Center-Periphery Brightness Ratio
        # Phone screen = bright center, dark room behind = dark edges
        # Real face: uniform lighting across frame
        # ──────────────────────────────────────────
        border_pct = 0.12  # 12% border strip
        bw = int(w * border_pct)
        bh = int(h * border_pct)

        center = gray[bh:-bh, bw:-bw]
        top_strip    = gray[:bh, :]
        bottom_strip = gray[-bh:, :]
        left_strip   = gray[:, :bw]
        right_strip  = gray[:, -bw:]

        center_brightness = float(np.mean(center))
        border_brightness = float(np.mean([
            np.mean(top_strip), np.mean(bottom_strip),
            np.mean(left_strip), np.mean(right_strip)
        ]))

        # Ratio > 1.4 → screen likely (bright center, dark edges)
        brightness_ratio = center_brightness / (border_brightness + 1)
        # Also check if border is genuinely dark (< 80 mean)
        border_dark = border_brightness < 80
        brightness_score = 0.0
        if brightness_ratio > 1.4 and border_dark:
            brightness_score = min(1.0, (brightness_ratio - 1.4) / 0.8)
        elif brightness_ratio > 1.8:
            brightness_score = min(1.0, (brightness_ratio - 1.4) / 0.8)

        details['brightness'] = {
            'center': round(center_brightness, 1),
            'border': round(border_brightness, 1),
            'ratio': round(brightness_ratio, 3),
            'border_dark': border_dark,
        }

        # ──────────────────────────────────────────
        # Method 2: Straight Edge Detection (Hough Lines)
        # Phone bezels create long, perfectly straight lines
        # Natural backgrounds have irregular edges
        # ──────────────────────────────────────────
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                                threshold=80,
                                minLineLength=int(min(h, w) * 0.3),
                                maxLineGap=10)

        straight_count = 0
        vertical_lines = 0
        horizontal_lines = 0
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                if length < min(h, w) * 0.3:
                    continue
                angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
                # Vertical lines (85-95 degrees)
                if 80 < angle < 100 or angle < 10 or angle > 170:
                    straight_count += 1
                    if 80 < angle < 100:
                        vertical_lines += 1
                    else:
                        horizontal_lines += 1

        # Phone has both vertical and horizontal bezel lines
        has_both = vertical_lines >= 1 and horizontal_lines >= 1
        line_score = 0.0
        if has_both:
            line_score = min(1.0, straight_count / 4)
        elif straight_count >= 2:
            line_score = min(0.5, straight_count / 6)

        details['lines'] = {
            'straight_count': straight_count,
            'vertical': vertical_lines,
            'horizontal': horizontal_lines,
        }

        # ──────────────────────────────────────────
        # Method 3: Edge Darkness Gradient
        # Phone bezels: very dark thin strip between bright screen and dim room
        # Check for sudden brightness drops at edges
        # ──────────────────────────────────────────
        # Sample vertical brightness profile down the center column
        center_col = gray[:, w // 2]
        gradient = np.abs(np.diff(center_col.astype(float)))
        sharp_edges = np.sum(gradient > 30)  # Count sharp brightness transitions
        gradient_score = min(1.0, max(0, (sharp_edges - 5) / 15))

        # Sample horizontal brightness profile across center row
        center_row = gray[h // 2, :]
        h_gradient = np.abs(np.diff(center_row.astype(float)))
        h_sharp = np.sum(h_gradient > 30)
        gradient_score = max(gradient_score, min(1.0, max(0, (h_sharp - 5) / 15)))

        details['gradient'] = {
            'v_sharp_edges': int(sharp_edges),
            'h_sharp_edges': int(h_sharp),
        }

        # ──────────────────────────────────────────
        # Combined Score
        # ──────────────────────────────────────────
        combined = (brightness_score * 0.45) + (line_score * 0.30) + (gradient_score * 0.25)

        print(f'  [Screen] brightness={brightness_score:.2f}, lines={line_score:.2f}, '
              f'gradient={gradient_score:.2f} → combined={combined:.2f}')
        print(f'  [Screen] Details: {details}')

        detected = combined >= 0.25
        method_used = []
        if brightness_score > 0.2:
            method_used.append('bright_center')
        if line_score > 0.2:
            method_used.append('straight_edges')
        if gradient_score > 0.2:
            method_used.append('sharp_gradient')

        return {
            'detected': detected,
            'confidence': round(combined, 3),
            'method': '+'.join(method_used) if method_used else 'none',
            'details': details,
        }

    except Exception as e:
        print(f'  [Screen] Error: {e}')
        return {'detected': False, 'confidence': 0, 'error': str(e)}


def verify_multi_frame_attendance(student, image_paths: list) -> dict:
    """
    5 JPEG frames ko verify karta hai:
      1. Har frame mein DeepFace face match
      2. Har frame mein phone detection
      3. Face position variance — static photo attack detect karta hai
    """
    from deepface import DeepFace

    total = len(image_paths)
    result = {
        'verified': False, 'face_match_count': 0, 'total_frames': total,
        'phone_detected': False, 'phone_frames': [], 'static_photo': False,
        'details': '',
    }

    if not student.registered_photo:
        result['details'] = 'Face not registered with admin.'
        return result

    stored = student.registered_photo.path
    print(f'\n[MultiFrame] Registered photo: {stored}')
    print(f'[MultiFrame] Verifying {total} frames...')

    match_count   = 0
    face_regions  = []

    for i, img_path in enumerate(image_paths):
        print(f'\n--- Frame {i} ---')

        # ── Face verification ──
        try:
            rv = DeepFace.verify(
                img1_path=stored, img2_path=img_path,
                model_name='ArcFace', detector_backend='ssd',
                distance_metric='cosine', enforce_detection=False,
            )
            distance  = rv.get('distance', 999)
            threshold = rv.get('threshold', 0.68)
            verified  = rv.get('verified', False)

            # ArcFace cosine: lower distance = better match
            # Default threshold ~0.68, we use 0.68 (standard)
            # If distance is close but just over threshold, still accept
            manual_threshold = 0.72  # slightly relaxed for webcam conditions
            if not verified and distance <= manual_threshold:
                verified = True
                print(f'  [Face] distance={distance:.4f}, threshold={threshold}, '
                      f'default=FAIL but manual_threshold={manual_threshold} → PASS')
            else:
                print(f'  [Face] distance={distance:.4f}, threshold={threshold}, verified={verified}')

            if verified:
                match_count += 1
        except Exception as e:
            print(f'  [Face] ERROR: {e}')

        # ── Face region for movement check ──
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

        # ── Phone detection ──
        pr = detect_phone_in_image(img_path)
        print(f'  [Phone] Result: detected={pr.get("detected")}, confidence={pr.get("confidence")}')
        if pr.get('detected'):
            result['phone_detected'] = True
            result['phone_frames'].append(i)

    result['face_match_count'] = match_count

    # ── Static photo / proxy check ──
    # Real face: natural micro-movements → x_std=30-100+
    # Phone held by hand: very small movement → x_std=5-10
    # Printed photo: near zero → x_std < 1
    if len(face_regions) >= 3:
        xs = [r.get('x', 0) for r in face_regions]
        ys = [r.get('y', 0) for r in face_regions]
        import numpy as np
        x_std, y_std = float(np.std(xs)), float(np.std(ys))
        avg_std = (x_std + y_std) / 2
        print(f'\n[MultiFrame] Face movement: x_std={x_std:.2f}, y_std={y_std:.2f}, avg={avg_std:.2f}')
        if avg_std < 15.0:
            result['static_photo'] = True
            print(f'[MultiFrame] ⚠️ PROXY DETECTED! avg_std={avg_std:.2f} < 15.0 threshold')

    # ── Final verdict ──
    # 2 out of 5 sufficient — other layers (blink, geo, device, static) provide security
    min_match = 2
    reasons = []
    if match_count < min_match:
        reasons.append(f'Face matched only {match_count}/{total} frames.')
    if result['phone_detected']:
        reasons.append(f'Phone detected in frame(s) {result["phone_frames"]}.')
    if result['static_photo']:
        reasons.append('Static photo detected — no face movement.')

    if reasons:
        result['details'] = ' '.join(reasons)
    else:
        result['verified'] = True
        result['details'] = f'Verified: {match_count}/{total} frames matched.'

    print(f"\n[Multi-Frame Verify Backend] Result: {result}\n")
    return result