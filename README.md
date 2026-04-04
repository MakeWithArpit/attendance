# Prahari — Smart Attendance Management System

Prahari is a full-stack attendance management system built for Invertis University. It supports three user roles (Admin, Teacher, Student) and provides multiple attendance methods including manual/bulk, facial recognition, and RFID — alongside leave management, analytics, PDF/CSV exports, and parent email notifications.

---

## Project Structure

```
attendance/
│
├── Backend/
│   ├── requirements.txt
│   └── attendance_system/
│       ├── manage.py
│       ├── db.sqlite3
│       ├── dummy_subjects.py
│       │
│       ├── attendance_system/       # Django project config
│       │   ├── settings.py
│       │   ├── urls.py
│       │   ├── wsgi.py
│       │   └── asgi.py
│       │
│       ├── accounts/                # Users, Students, Teachers, Device binding
│       ├── academics/               # Subjects, Timetable, Course Registration
│       ├── attendance/              # Sessions, Attendance Records, Leave Requests
│       └── analytics/               # Reports, PDF/CSV, Email alerts
│
└── Frontend/
    ├── index.html                   # Landing page (portal selector)
    ├── login.html                   # Unified login for all roles
    ├── admin.html                   # Admin dashboard
    ├── teacher.html                 # Teacher dashboard
    ├── student.html                 # Student dashboard
    ├── api.js                       # Centralised API call helpers
    └── styles.css                   # Global stylesheet
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend Framework | Django 4.2.7 + Django REST Framework |
| Authentication | JWT via `djangorestframework-simplejwt` |
| Facial Recognition | DeepFace + tf-keras |
| Phone Detection | YOLOv8 (ultralytics) + OpenCV |
| Image Handling | Pillow (Django ImageField dependency) |
| PDF Export | ReportLab |
| CSV Export | Python stdlib `csv` module |
| Cross-Origin | django-cors-headers |
| Email | Gmail SMTP |
| Frontend | Vanilla HTML, CSS, JavaScript |
| Database | SQLite (development) |

---

## User Roles

| Role | Login ID | Access |
|------|----------|--------|
| Admin | Admin username | Full system control, user creation, request approvals |
| Teacher | Employee ID | Start sessions, mark attendance, manage leaves |
| Student | Student ID | View attendance, mark via face recognition, apply for leave |

---

## Core Features

### Authentication
- JWT-based login with Bearer token
- Forgot password via 6-digit OTP sent to registered email (10-minute expiry)
- Browser fingerprint-based device binding — new device triggers OTP verification before login
- Admin can reset device tokens

### Attendance Sessions
- Teacher starts a session for a specific branch, semester, section, and subject
- Session supports a configurable auto-close timer (in minutes)
- Per-session flags for facial recognition and geo-fencing

### Attendance Methods
- **Manual / Bulk**: Teacher marks all students present or absent using checkboxes
- **Facial Recognition**: Student submits a selfie; DeepFace compares it against the registered photo stored by the admin. Liveness detection (blink/nod) is handled on the frontend via MediaPipe and validated on the backend via a multi-frame challenge-response flow with YOLOv8 phone detection
- **RFID**: RFID card number linked to student profile
- **Geo-fencing**: Student's GPS coordinates are verified to be within the campus boundary (configurable radius, default 200 m) before attendance is accepted

### Leave and Attendance Requests
- Students apply for leave with a date range, reason, and optional document upload
- Approved leaves are automatically counted as present in attendance records
- Teachers can raise an attendance request to admin for a student who could not mark via face/RFID during a session
- Admin approves or rejects with remarks

### Analytics and Reports
- Subject-wise average attendance percentage per class
- Students below a configurable attendance threshold
- Monthly attendance trend
- PDF and CSV export of attendance reports
- Parent alert emails via Gmail SMTP when student attendance falls below the threshold
- WhatsApp message link generation for parent notifications

---

## Database Models

### accounts app
| Model | Description |
|-------|-------------|
| User | Custom AbstractBaseUser with roles: student, teacher, admin |
| Branch | Branch code and name (e.g., CSE, ECE) |
| Student | Student ID, enrollment number, roll number, RFID, registered face photo |
| StudentProfile | Name, DOB, gender, mobile, branch, semester, section, academic year |
| ParentDetail | Father and mother contact information |
| PermanentAddress / PresentAddress | Student address records |
| Teacher | Employee ID, department, name, email, designation |
| DeviceToken | Browser fingerprint per student for device binding |
| PasswordResetOTP | OTP record with expiry for forgot-password and device-verification flows |

### academics app
| Model | Description |
|-------|-------------|
| Subject | Subject code, name, type, credits, assigned teacher, branch, semester |
| CourseRegistration | Links a student to subjects for a given semester and section |
| TimeTable | Weekly period-wise timetable per branch, semester, section |

### attendance app
| Model | Description |
|-------|-------------|
| AttendanceSession | Teacher-created session with method flags, timer, and geo-fencing config |
| Attendance | Per-student per-subject per-date record with method, GPS, and session reference |
| LeaveRequest | Student leave application with approval workflow |
| AttendanceRequest | Teacher request to admin for manual attendance correction |

---

## API Endpoints

| Prefix | App |
|--------|-----|
| `/api/auth/` | accounts — login, register, OTP, device verification |
| `/api/academics/` | subjects, timetable, course registration |
| `/api/attendance/` | sessions, bulk/facial/RFID marking, leave requests |
| `/api/analytics/` | reports, exports, parent alerts |
| `/admin/` | Django admin panel |

---

## Installation and Setup

**1. Clone the repository**

```bash
git clone https://github.com/yourusername/attendance.git
cd attendance/Backend
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

> **Note:** DeepFace downloads model weights (~100 MB) automatically on first use. YOLOv8 (`yolov8n.pt`) is included in the repo under `media/` and is loaded at runtime.

**4. Configure environment**

Open `attendance_system/settings.py` and update:

```python
SECRET_KEY = 'your-secret-key'
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'   # Gmail App Password
CORS_ALLOWED_ORIGINS = ['http://localhost:5500']
```

**5. Run migrations and create a superuser**

```bash
cd attendance_system
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

**6. Frontend**

Open any HTML file in a browser or serve them with Live Server (VS Code). No build step is required.

---

## Deployment

| Part | Platform |
|------|----------|
| Frontend | Vercel (`https://attendance-ashen-ten.vercel.app`) |
| Backend | Any WSGI host (Gunicorn + Nginx recommended) |
| Media files | Served via Django in development; use S3 or similar in production |

Before going live, update `settings.py`:
- Set `DEBUG = False`
- Set `CORS_ALLOW_ALL_ORIGINS = False` and add your frontend URL to `CORS_ALLOWED_ORIGINS`
- Rotate `SECRET_KEY`

---

## Requirements

```
Django==4.2.7
djangorestframework
djangorestframework-simplejwt
django-cors-headers
django-filter
deepface
tf-keras
ultralytics
opencv-python-headless
Pillow
reportlab
```

---

## License

This project is licensed under the **MIT License**.

---

## Author

**Arpit Gangwar**  
B.Tech Computer Science and Engineering  
Invertis University, Bareilly
