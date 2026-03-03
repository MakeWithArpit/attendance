"""
accounts/management/commands/seed_data.py

Dummy data seedar — poora database populate karta hai initial testing ke liye.

Run karne ka tarika:
    python manage.py seed_data

Dobara fresh seed karna ho:
    python manage.py seed_data --flush
"""

import datetime
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Populates the database with realistic dummy data for testing.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Pehle saara data delete karo, phir fresh seed karo.',
        )

    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write(self.style.WARNING('⚠️  Flushing existing data...'))
            self._flush_data()

        self.stdout.write(self.style.MIGRATE_HEADING('\n🌱 Seeding dummy data...\n'))

        with transaction.atomic():
            admin     = self._create_admin()
            branches  = self._create_branches()
            teachers  = self._create_teachers()
            subjects  = self._create_subjects(teachers)
            students  = self._create_students(branches)
            self._create_course_registrations(students, branches, subjects)
            self._create_timetable(branches, subjects)
            self._create_attendance_sessions(teachers, subjects, branches)
            self._create_attendance_records(students, subjects)
            self._create_leave_requests(students, teachers)

        self.stdout.write(self.style.SUCCESS('\n✅  Seed data created successfully!\n'))
        self._print_summary()

    # ──────────────────────────────────────────
    # FLUSH
    # ──────────────────────────────────────────
    def _flush_data(self):
        from attendance.models import Attendance, AttendanceSession, LeaveRequest
        from academics.models import Subject, CourseRegistration, TimeTable
        from accounts.models import User, Student, Teacher, Branch

        LeaveRequest.objects.all().delete()
        AttendanceSession.objects.all().delete()
        Attendance.objects.all().delete()
        CourseRegistration.objects.all().delete()
        TimeTable.objects.all().delete()
        Subject.objects.all().delete()
        Student.objects.all().delete()
        Teacher.objects.all().delete()
        Branch.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write('  Existing data cleared.')

    # ──────────────────────────────────────────
    # ADMIN
    # ──────────────────────────────────────────
    def _create_admin(self):
        from accounts.models import User
        admin, created = User.objects.get_or_create(
            username='admin001',
            defaults={
                'role':         'admin',
                'is_staff':     True,
                'is_superuser': True,
            }
        )
        if created:
            admin.set_password('admin@123')
            admin.save()
            self.stdout.write('  ✔ Admin created  →  username: admin001  |  password: admin@123')
        else:
            self.stdout.write('  ℹ Admin already exists.')
        return admin

    # ──────────────────────────────────────────
    # BRANCHES
    # ──────────────────────────────────────────
    def _create_branches(self):
        from accounts.models import Branch
        branch_data = [
            ('CSE',  'Computer Science & Engineering'),
            ('IT',   'Information Technology'),
            ('ECE',  'Electronics & Communication Engineering'),
            ('ME',   'Mechanical Engineering'),
            ('CIVIL','Civil Engineering'),
        ]
        branches = []
        for code, name in branch_data:
            b, created = Branch.objects.get_or_create(
                branch_code=code, defaults={'branch_name': name}
            )
            branches.append(b)

        self.stdout.write(f'  ✔ {len(branches)} Branches created')
        return branches

    # ──────────────────────────────────────────
    # TEACHERS
    # ──────────────────────────────────────────
    def _create_teachers(self):
        from accounts.models import User, Teacher

        teacher_data = [
            ('T001', 'Dr. Rajesh Kumar',        'raj.kumar@college.edu',    '9876543201', 'Computer Science',  'Associate Professor'),
            ('T002', 'Prof. Sunita Sharma',      'sunita.sharma@college.edu','9876543202', 'Computer Science',  'Assistant Professor'),
            ('T003', 'Dr. Amit Verma',           'amit.verma@college.edu',   '9876543203', 'Information Tech',  'Professor'),
            ('T004', 'Prof. Priya Patel',        'priya.patel@college.edu',  '9876543204', 'Electronics',       'Assistant Professor'),
            ('T005', 'Dr. Mohan Singh',          'mohan.singh@college.edu',  '9876543205', 'Mathematics',       'Associate Professor'),
            ('T006', 'Prof. Kavita Joshi',       'kavita.joshi@college.edu', '9876543206', 'Physics',           'Assistant Professor'),
        ]

        teachers = []
        for emp_id, name, email, mobile, dept, designation in teacher_data:
            user, ucreated = User.objects.get_or_create(
                username=emp_id, defaults={'role': 'teacher'}
            )
            if ucreated:
                user.set_password('teacher@123')
                user.save()

            teacher, _ = Teacher.objects.get_or_create(
                employee_id=emp_id,
                defaults={
                    'user':        user,
                    'name':        name,
                    'email':       email,
                    'mobile':      mobile,
                    'department':  dept,
                    'designation': designation,
                }
            )
            teachers.append(teacher)

        self.stdout.write(f'  ✔ {len(teachers)} Teachers created  →  password: teacher@123')
        return teachers

    # ──────────────────────────────────────────
    # SUBJECTS
    # ──────────────────────────────────────────
    def _create_subjects(self, teachers):
        from academics.models import Subject

        subject_data = [
            ('CS301', 'Data Structures & Algorithms',  'core',     'theory',    4, teachers[0]),
            ('CS302', 'Database Management Systems',   'core',     'theory',    4, teachers[1]),
            ('CS303', 'Operating Systems',             'core',     'theory',    4, teachers[0]),
            ('CS304', 'Computer Networks',             'core',     'theory',    4, teachers[2]),
            ('CS305', 'Software Engineering',          'core',     'theory',    3, teachers[1]),
            ('CS306', 'DBMS Lab',                      'core',     'practical', 2, teachers[1]),
            ('CS307', 'DS Lab',                        'core',     'practical', 2, teachers[0]),
            ('MA301', 'Engineering Mathematics III',   'core',     'theory',    4, teachers[4]),
            ('PH301', 'Engineering Physics',           'core',     'theory',    3, teachers[5]),
            ('CS401', 'Machine Learning',              'elective', 'theory',    4, teachers[2]),
            ('CS402', 'Web Technologies',              'elective', 'theory',    3, teachers[3]),
            ('CS403', 'Cloud Computing',               'elective', 'theory',    3, teachers[2]),
        ]

        subjects = []
        for code, name, cls, typ, credits, teacher in subject_data:
            subj, _ = Subject.objects.get_or_create(
                subject_code=code,
                defaults={
                    'subject_name':           name,
                    'subject_classification': cls,
                    'subject_type':           typ,
                    'subject_credit':         credits,
                    'assigned_teacher':       teacher,
                }
            )
            subjects.append(subj)

        self.stdout.write(f'  ✔ {len(subjects)} Subjects created')
        return subjects

    # ──────────────────────────────────────────
    # STUDENTS (20 students in CSE branch)
    # ──────────────────────────────────────────
    def _create_students(self, branches):
        from accounts.models import (
            User, Student, StudentProfile, ParentDetail,
            PermanentAddress, PresentAddress
        )

        cse_branch = branches[0]  # CSE

        student_data = [
            # (student_id, enrollment, roll, name, dob, gender, mobile, email, father_name, father_mobile, father_email)
            ('STU2024001', 'EN2024CSE001', 'CS301', 'Aarav Sharma',      '2004-03-15', 'M', '8765432101', 'aarav.sharma@gmail.com',    'Ramesh Sharma',    '9876501001', 'ramesh.sharma@gmail.com'),
            ('STU2024002', 'EN2024CSE002', 'CS302', 'Priya Singh',       '2004-07-22', 'F', '8765432102', 'priya.singh@gmail.com',     'Suresh Singh',     '9876501002', 'suresh.singh@gmail.com'),
            ('STU2024003', 'EN2024CSE003', 'CS303', 'Rahul Verma',       '2004-01-10', 'M', '8765432103', 'rahul.verma@gmail.com',     'Mahesh Verma',     '9876501003', 'mahesh.verma@gmail.com'),
            ('STU2024004', 'EN2024CSE004', 'CS304', 'Sneha Patel',       '2004-09-05', 'F', '8765432104', 'sneha.patel@gmail.com',     'Dinesh Patel',     '9876501004', 'dinesh.patel@gmail.com'),
            ('STU2024005', 'EN2024CSE005', 'CS305', 'Arjun Kumar',       '2004-11-18', 'M', '8765432105', 'arjun.kumar@gmail.com',     'Vijay Kumar',      '9876501005', 'vijay.kumar@gmail.com'),
            ('STU2024006', 'EN2024CSE006', 'CS306', 'Anjali Gupta',      '2004-04-25', 'F', '8765432106', 'anjali.gupta@gmail.com',    'Anil Gupta',       '9876501006', 'anil.gupta@gmail.com'),
            ('STU2024007', 'EN2024CSE007', 'CS307', 'Vikram Joshi',      '2004-06-30', 'M', '8765432107', 'vikram.joshi@gmail.com',    'Rajkumar Joshi',   '9876501007', 'rajkumar.joshi@gmail.com'),
            ('STU2024008', 'EN2024CSE008', 'CS308', 'Pooja Yadav',       '2004-02-14', 'F', '8765432108', 'pooja.yadav@gmail.com',     'Hari Yadav',       '9876501008', 'hari.yadav@gmail.com'),
            ('STU2024009', 'EN2024CSE009', 'CS309', 'Ravi Mishra',       '2004-08-08', 'M', '8765432109', 'ravi.mishra@gmail.com',     'Om Mishra',        '9876501009', 'om.mishra@gmail.com'),
            ('STU2024010', 'EN2024CSE010', 'CS310', 'Kavya Nair',        '2004-12-20', 'F', '8765432110', 'kavya.nair@gmail.com',      'Krishna Nair',     '9876501010', 'krishna.nair@gmail.com'),
            ('STU2024011', 'EN2024CSE011', 'CS311', 'Manish Tiwari',     '2004-05-12', 'M', '8765432111', 'manish.tiwari@gmail.com',   'Prakash Tiwari',   '9876501011', 'prakash.tiwari@gmail.com'),
            ('STU2024012', 'EN2024CSE012', 'CS312', 'Divya Agarwal',     '2004-10-17', 'F', '8765432112', 'divya.agarwal@gmail.com',   'Deepak Agarwal',   '9876501012', 'deepak.agarwal@gmail.com'),
            ('STU2024013', 'EN2024CSE013', 'CS313', 'Suraj Pandey',      '2004-03-28', 'M', '8765432113', 'suraj.pandey@gmail.com',    'Shiv Pandey',      '9876501013', 'shiv.pandey@gmail.com'),
            ('STU2024014', 'EN2024CSE014', 'CS314', 'Nidhi Srivastava',  '2004-07-03', 'F', '8765432114', 'nidhi.sri@gmail.com',       'Ram Srivastava',   '9876501014', 'ram.sri@gmail.com'),
            ('STU2024015', 'EN2024CSE015', 'CS315', 'Rohit Chauhan',     '2004-01-22', 'M', '8765432115', 'rohit.chauhan@gmail.com',   'Mohan Chauhan',    '9876501015', 'mohan.chauhan@gmail.com'),
            ('STU2024016', 'EN2024CSE016', 'CS316', 'Shweta Rastogi',    '2004-09-14', 'F', '8765432116', 'shweta.rastogi@gmail.com',  'Vinod Rastogi',    '9876501016', 'vinod.rastogi@gmail.com'),
            ('STU2024017', 'EN2024CSE017', 'CS317', 'Deepak Saxena',     '2004-06-06', 'M', '8765432117', 'deepak.saxena@gmail.com',   'Ajay Saxena',      '9876501017', 'ajay.saxena@gmail.com'),
            ('STU2024018', 'EN2024CSE018', 'CS318', 'Sonia Mehta',       '2004-11-29', 'F', '8765432118', 'sonia.mehta@gmail.com',     'Sunil Mehta',      '9876501018', 'sunil.mehta@gmail.com'),
            ('STU2024019', 'EN2024CSE019', 'CS319', 'Nikhil Bansal',     '2004-04-09', 'M', '8765432119', 'nikhil.bansal@gmail.com',   'Rakesh Bansal',    '9876501019', 'rakesh.bansal@gmail.com'),
            ('STU2024020', 'EN2024CSE020', 'CS320', 'Ritika Kapoor',     '2004-08-19', 'F', '8765432120', 'ritika.kapoor@gmail.com',   'Sanjeev Kapoor',   '9876501020', 'sanjeev.kapoor@gmail.com'),
        ]

        rfid_counter = 1000
        students = []

        for (stu_id, enroll, roll, name, dob, gender,
             mobile, email, father_name, father_mobile, father_email) in student_data:

            user, ucreated = User.objects.get_or_create(
                username=stu_id, defaults={'role': 'student'}
            )
            if ucreated:
                user.set_password('student@123')
                user.save()

            student, screated = Student.objects.get_or_create(
                student_id=stu_id,
                defaults={
                    'user':             user,
                    'enrollment_number': enroll,
                    'roll_number':      roll,
                    'rfid_number':      f'RFID{rfid_counter}',
                }
            )
            rfid_counter += 1

            if screated:
                StudentProfile.objects.create(
                    student=student,
                    name=name,
                    dob=datetime.date.fromisoformat(dob),
                    gender=gender,
                    mobile_number=mobile,
                    email=email,
                    nationality='Indian',
                    marital_status='single',
                    domicile_state='Uttar Pradesh',
                    date_of_joining=datetime.date(2024, 8, 1),
                    academic_year='2024-2025',
                    branch=cse_branch,
                )

                ParentDetail.objects.create(
                    student=student,
                    father_name=father_name,
                    father_occupation='Business',
                    father_mobile=father_mobile,
                    father_email=father_email,
                    mother_name=f'Smt. {name.split()[1]}',
                    mother_occupation='Homemaker',
                    mother_mobile=str(int(father_mobile) + 1),
                )

                PermanentAddress.objects.create(
                    student=student,
                    address_line1=f'H.No. {random.randint(10, 999)}, Sector {random.randint(1, 20)}',
                    address_line2='Near Main Market',
                    state='Uttar Pradesh',
                    place='Lucknow',
                    pincode=f'2260{random.randint(10,99)}',
                )

                PresentAddress.objects.create(
                    student=student,
                    address_line1=f'Room {random.randint(100, 250)}, Boys/Girls Hostel',
                    address_line2='College Campus',
                    state='Uttar Pradesh',
                    place='Lucknow',
                    pincode='226001',
                )

            students.append(student)

        self.stdout.write(f'  ✔ {len(students)} Students created  →  password: student@123')
        return students

    # ──────────────────────────────────────────
    # COURSE REGISTRATIONS
    # ──────────────────────────────────────────
    def _create_course_registrations(self, students, branches, subjects):
        from academics.models import CourseRegistration

        cse = branches[0]
        # Semester 3 subjects (first 7 subjects)
        sem3_subjects = subjects[:7]

        count = 0
        for student in students:
            for subject in sem3_subjects:
                _, created = CourseRegistration.objects.get_or_create(
                    student=student,
                    subject=subject,
                    semester=3,
                    defaults={
                        'branch':  cse,
                        'section': 'A',
                    }
                )
                if created:
                    count += 1

        self.stdout.write(f'  ✔ {count} Course Registrations created (Semester 3, Section A)')

    # ──────────────────────────────────────────
    # TIMETABLE
    # ──────────────────────────────────────────
    def _create_timetable(self, branches, subjects):
        from academics.models import TimeTable

        cse = branches[0]

        # Monday to Friday, 6 periods per day
        schedule = [
            # (day, period, subject_index, start, end)
            ('Monday',    1, 0, '09:00', '10:00'),
            ('Monday',    2, 1, '10:00', '11:00'),
            ('Monday',    3, 2, '11:15', '12:15'),
            ('Monday',    4, 7, '12:15', '01:15'),
            ('Monday',    5, 5, '02:00', '04:00'),  # Lab (2hr)

            ('Tuesday',   1, 3, '09:00', '10:00'),
            ('Tuesday',   2, 0, '10:00', '11:00'),
            ('Tuesday',   3, 4, '11:15', '12:15'),
            ('Tuesday',   4, 8, '12:15', '01:15'),
            ('Tuesday',   5, 6, '02:00', '04:00'),  # Lab (2hr)

            ('Wednesday', 1, 1, '09:00', '10:00'),
            ('Wednesday', 2, 2, '10:00', '11:00'),
            ('Wednesday', 3, 3, '11:15', '12:15'),
            ('Wednesday', 4, 4, '12:15', '01:15'),

            ('Thursday',  1, 0, '09:00', '10:00'),
            ('Thursday',  2, 7, '10:00', '11:00'),
            ('Thursday',  3, 1, '11:15', '12:15'),
            ('Thursday',  4, 8, '12:15', '01:15'),

            ('Friday',    1, 2, '09:00', '10:00'),
            ('Friday',    2, 3, '10:00', '11:00'),
            ('Friday',    3, 4, '11:15', '12:15'),
            ('Friday',    4, 0, '12:15', '01:15'),
        ]

        count = 0
        for day, period, subj_idx, start, end in schedule:
            if subj_idx < len(subjects):
                _, created = TimeTable.objects.get_or_create(
                    branch=cse, semester=3, section='A', day=day, period_number=period,
                    academic_year='2024-2025',
                    defaults={
                        'subject':    subjects[subj_idx],
                        'start_time': start,
                        'end_time':   end,
                    }
                )
                if created:
                    count += 1

        self.stdout.write(f'  ✔ {count} TimeTable entries created (CSE Sem 3, Section A)')

    # ──────────────────────────────────────────
    # ATTENDANCE SESSIONS (past 30 days)
    # ──────────────────────────────────────────
    def _create_attendance_sessions(self, teachers, subjects, branches):
        from attendance.models import AttendanceSession

        cse = branches[0]
        today = datetime.date.today()

        # Generate sessions for past 30 working days
        working_days = []
        d = today - datetime.timedelta(days=45)
        while d <= today:
            if d.weekday() < 5:  # Mon-Fri
                working_days.append(d)
            d += datetime.timedelta(days=1)
        working_days = working_days[-30:]  # Last 30 working days

        session_data = [
            # (subject_index, teacher_index) — one session per subject per working day
            (0, 0),   # DS → T001
            (1, 1),   # DBMS → T002
            (2, 0),   # OS → T001
            (3, 2),   # Networks → T003
            (4, 1),   # SE → T002
        ]

        count = 0
        for day in working_days:
            for subj_idx, teacher_idx in session_data:
                _, created = AttendanceSession.objects.get_or_create(
                    teacher=teachers[teacher_idx],
                    subject=subjects[subj_idx],
                    branch=cse,
                    semester=3,
                    section='A',
                    date=day,
                    academic_year='2024-2025',
                    defaults={'status': 'closed'}
                )
                if created:
                    count += 1

        self.stdout.write(f'  ✔ {count} Attendance Sessions created (last 30 working days)')

    # ──────────────────────────────────────────
    # ATTENDANCE RECORDS
    # Realistic patterns: some students have high, some low attendance
    # ──────────────────────────────────────────
    def _create_attendance_records(self, students, subjects):
        from attendance.models import Attendance, AttendanceSession

        # Attendance pattern per student (probability of being present)
        # Index matches students list
        attendance_probabilities = [
            0.95, 0.90, 0.85, 0.80, 0.75,   # Students 1-5: good
            0.70, 0.65, 0.60, 0.55, 0.50,   # Students 6-10: average/warning
            0.45, 0.40, 0.88, 0.92, 0.78,   # Students 11-15: some critical
            0.83, 0.67, 0.72, 0.48, 0.35,   # Students 16-20: mixed
        ]

        core_subjects = subjects[:5]  # First 5 theory subjects
        sessions = AttendanceSession.objects.filter(
            subject__in=core_subjects, status='closed'
        ).order_by('date')

        random.seed(42)  # For reproducible data
        count = 0

        for session in sessions:
            for i, student in enumerate(students):
                prob = attendance_probabilities[min(i, len(attendance_probabilities) - 1)]
                is_present = random.random() < prob

                _, created = Attendance.objects.get_or_create(
                    student=student,
                    subject=session.subject,
                    date=session.date,
                    defaults={
                        'is_present':    is_present,
                        'day':           session.date.strftime('%A'),
                        'semester':      3,
                        'academic_year': '2024-2025',
                        'marked_by':     session.teacher,
                        'method':        random.choice(['manual', 'manual', 'manual']),
                    }
                )
                if created:
                    count += 1

        self.stdout.write(f'  ✔ {count} Attendance Records created (realistic patterns)')

    # ──────────────────────────────────────────
    # LEAVE REQUESTS
    # ──────────────────────────────────────────
    def _create_leave_requests(self, students, teachers):
        from attendance.models import LeaveRequest

        today = datetime.date.today()
        leave_data = [
            # (student_index, from_date_offset, to_date_offset, reason, status)
            (0,  -20, -18, 'Medical emergency — fever and cold', 'approved'),
            (1,  -15, -14, 'Family function — sister marriage',  'approved'),
            (2,  -10,  -9, 'College sports tournament (state level)', 'approved'),
            (3,   -8,  -8, 'Personal reasons',                   'rejected'),
            (4,   -5,  -4, 'Medical — dental surgery',           'approved'),
            (5,   -3,  -2, 'Outstation — parents unwell',        'pending'),
            (6,   -1,   0, 'Medical certificate attached',       'pending'),
            (7,    1,   2, 'Cultural fest participation (advance)', 'pending'),
            (10, -25, -23, 'Hospital admission — appendix surgery', 'approved'),
            (11, -12, -11, 'Government exam — SSC CGL',          'approved'),
        ]

        count = 0
        for stu_idx, from_off, to_off, reason, status in leave_data:
            student    = students[stu_idx]
            from_date  = today + datetime.timedelta(days=from_off)
            to_date    = today + datetime.timedelta(days=to_off)
            reviewer   = teachers[0] if status != 'pending' else None

            _, created = LeaveRequest.objects.get_or_create(
                student=student,
                from_date=from_date,
                to_date=to_date,
                defaults={
                    'reason':      reason,
                    'status':      status,
                    'reviewed_by': reviewer,
                    'reviewed_on': timezone.now() if status != 'pending' else None,
                    'remarks':     'Approved by class teacher.' if status == 'approved' else
                                   ('Insufficient reason.' if status == 'rejected' else ''),
                }
            )
            if created:
                count += 1

        self.stdout.write(f'  ✔ {count} Leave Requests created (mix of approved/rejected/pending)')

    # ──────────────────────────────────────────
    # SUMMARY TABLE
    # ──────────────────────────────────────────
    def _print_summary(self):
        from accounts.models import User, Student, Teacher, Branch
        from academics.models import Subject, CourseRegistration, TimeTable
        from attendance.models import Attendance, AttendanceSession, LeaveRequest

        self.stdout.write(self.style.MIGRATE_HEADING('\n📊 Database Summary:'))
        self.stdout.write(f'   Users              : {User.objects.count()}')
        self.stdout.write(f'   Branches           : {Branch.objects.count()}')
        self.stdout.write(f'   Teachers           : {Teacher.objects.count()}')
        self.stdout.write(f'   Students           : {Student.objects.count()}')
        self.stdout.write(f'   Subjects           : {Subject.objects.count()}')
        self.stdout.write(f'   Course Registrations: {CourseRegistration.objects.count()}')
        self.stdout.write(f'   TimeTable Entries  : {TimeTable.objects.count()}')
        self.stdout.write(f'   Attendance Sessions: {AttendanceSession.objects.count()}')
        self.stdout.write(f'   Attendance Records : {Attendance.objects.count()}')
        self.stdout.write(f'   Leave Requests     : {LeaveRequest.objects.count()}')

        self.stdout.write(self.style.MIGRATE_HEADING('\n🔑 Login Credentials:'))
        self.stdout.write('   Role     │ Username      │ Password')
        self.stdout.write('   ─────────┼───────────────┼────────────')
        self.stdout.write('   Admin    │ admin001       │ admin@123')
        self.stdout.write('   Teacher  │ T001 – T006    │ teacher@123')
        self.stdout.write('   Student  │ STU2024001–020 │ student@123')

        self.stdout.write(self.style.MIGRATE_HEADING('\n📈 Attendance Patterns (for testing):'))
        self.stdout.write('   STU2024001  Aarav Sharma    ~95% (Safe)')
        self.stdout.write('   STU2024005  Arjun Kumar     ~75% (Borderline)')
        self.stdout.write('   STU2024008  Pooja Yadav     ~60% (Warning ⚠️)')
        self.stdout.write('   STU2024011  Manish Tiwari   ~45% (Critical 🔴)')
        self.stdout.write('   STU2024019  Nikhil Bansal   ~48% (Critical 🔴)')
        self.stdout.write('   STU2024020  Ritika Kapoor   ~35% (Critical 🔴)')
