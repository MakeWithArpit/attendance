"""
management/commands/seed_data.py

Usage:
    python manage.py seed_data           # Full reset + seed
    python manage.py seed_data --keep    # Sirf naya data add (existing delete nahi)

Creates:
  - 1 Admin
  - 4 Branches (CSE, ECE, ME, CE)
  - 6 Teachers (T001–T006)
  - 13 Subjects (CS301–CS308, CS401–CS403, MA301, PH301)
  - 20 Students (BCS2024001–020) with full profiles, parent details, addresses
  - Course Registrations (CSE students → CS subjects)
  - Timetable entries
  - Attendance Sessions (past 30 days)
  - Attendance Records (realistic patterns — good/average/poor students)
  - Leave Requests (various statuses)
"""

import random
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction


class Command(BaseCommand):
    help = 'Seed database with realistic test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep',
            action='store_true',
            help='Existing data delete mat karo — sirf naya add karo',
        )

    def handle(self, *args, **options):
        keep = options.get('keep', False)

        self.stdout.write(self.style.WARNING('\n🌱 AttendX Seed Data Starting...\n'))

        with transaction.atomic():
            if not keep:
                self._clear_data()
            self._create_admin()
            self._create_branches()
            self._create_teachers()
            self._create_subjects()
            self._create_students()
            self._create_course_registrations()
            self._create_timetable()
            self._create_attendance()
            self._create_leaves()

        self.stdout.write(self.style.SUCCESS('\n✅ Seed complete!\n'))
        self._print_credentials()

    # ─────────────────────────────────────────────────────────────────────
    def _clear_data(self):
        from accounts.models import User, Branch, Student, Teacher
        from academics.models import Subject, CourseRegistration, TimeTable
        from attendance.models import Attendance, AttendanceSession, LeaveRequest

        self.stdout.write('🗑  Clearing old data...')
        LeaveRequest.objects.all().delete()
        Attendance.objects.all().delete()
        AttendanceSession.objects.all().delete()
        CourseRegistration.objects.all().delete()
        TimeTable.objects.all().delete()
        Subject.objects.all().delete()
        Student.objects.all().delete()
        Teacher.objects.all().delete()
        Branch.objects.all().delete()
        User.objects.filter(role__in=['student', 'teacher']).delete()
        User.objects.filter(username='admin001').delete()
        self.stdout.write(self.style.SUCCESS('   ✓ Done'))

    # ─────────────────────────────────────────────────────────────────────
    def _create_admin(self):
        from accounts.models import User
        self.stdout.write('👑 Creating admin...')
        if not User.objects.filter(username='admin001').exists():
            User.objects.create_superuser(
                username='admin001',
                password='admin@123',
                role='admin',
            )
        self.stdout.write(self.style.SUCCESS('   ✓ admin001 / admin@123'))

    # ─────────────────────────────────────────────────────────────────────
    def _create_branches(self):
        from accounts.models import Branch
        self.stdout.write('🏫 Creating branches...')
        branches = [
            ('CSE', 'Computer Science & Engineering'),
            ('ECE', 'Electronics & Communication Engineering'),
            ('ME',  'Mechanical Engineering'),
            ('CE',  'Civil Engineering'),
        ]
        for code, name in branches:
            Branch.objects.get_or_create(branch_code=code, defaults={'branch_name': name})
        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(branches)} branches'))

    # ─────────────────────────────────────────────────────────────────────
    def _create_teachers(self):
        from accounts.models import User, Teacher
        self.stdout.write('👨‍🏫 Creating teachers...')

        teachers_data = [
            {
                'employee_id': 'T001', 'name': 'Dr. Rajesh Kumar',
                'email': 'rajesh.kumar@college.edu', 'mobile': '9811001001',
                'department': 'Computer Science', 'designation': 'Professor',
            },
            {
                'employee_id': 'T002', 'name': 'Prof. Sunita Sharma',
                'email': 'sunita.sharma@college.edu', 'mobile': '9811001002',
                'department': 'Computer Science', 'designation': 'Associate Professor',
            },
            {
                'employee_id': 'T003', 'name': 'Dr. Amit Verma',
                'email': 'amit.verma@college.edu', 'mobile': '9811001003',
                'department': 'Electronics', 'designation': 'Assistant Professor',
            },
            {
                'employee_id': 'T004', 'name': 'Prof. Meena Gupta',
                'email': 'meena.gupta@college.edu', 'mobile': '9811001004',
                'department': 'Mathematics', 'designation': 'Associate Professor',
            },
            {
                'employee_id': 'T005', 'name': 'Dr. Vikram Singh',
                'email': 'vikram.singh@college.edu', 'mobile': '9811001005',
                'department': 'Physics', 'designation': 'Professor',
            },
            {
                'employee_id': 'T006', 'name': 'Prof. Priya Nair',
                'email': 'priya.nair@college.edu', 'mobile': '9811001006',
                'department': 'Computer Science', 'designation': 'Assistant Professor',
            },
        ]

        for td in teachers_data:
            if not User.objects.filter(username=td['employee_id']).exists():
                user = User.objects.create_user(
                    username=td['employee_id'],
                    password='teacher@123',
                    role='teacher',
                )
                Teacher.objects.get_or_create(
                    employee_id=td['employee_id'],
                    defaults={
                        'user': user,
                        'name': td['name'],
                        'email': td['email'],
                        'mobile': td['mobile'],
                        'department': td['department'],
                        'designation': td['designation'],
                    }
                )

        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(teachers_data)} teachers (T001–T006 / teacher@123)'))

    # ─────────────────────────────────────────────────────────────────────
    def _create_subjects(self):
        from accounts.models import Teacher
        from academics.models import Subject
        self.stdout.write('📚 Creating subjects...')

        t1 = Teacher.objects.get(employee_id='T001')
        t2 = Teacher.objects.get(employee_id='T002')
        t3 = Teacher.objects.get(employee_id='T003')
        t4 = Teacher.objects.get(employee_id='T004')
        t5 = Teacher.objects.get(employee_id='T005')
        t6 = Teacher.objects.get(employee_id='T006')

        subjects_data = [
            # Semester 3
            ('CS301', 'Data Structures & Algorithms',    'theory',    'core',     4, t1),
            ('CS302', 'Computer Organization',           'theory',    'core',     3, t2),
            ('CS303', 'Discrete Mathematics',            'theory',    'core',     3, t4),
            ('CS304', 'Object Oriented Programming',     'theory',    'core',     3, t6),
            ('CS305', 'OOP Lab',                         'practical', 'lab',      2, t6),
            ('CS306', 'Data Structures Lab',             'practical', 'lab',      2, t1),
            ('MA301', 'Engineering Mathematics III',     'theory',    'core',     4, t4),
            ('PH301', 'Applied Physics',                 'theory',    'core',     3, t5),
            # Semester 4
            ('CS307', 'Operating Systems',               'theory',    'core',     4, t1),
            ('CS308', 'Database Management Systems',     'theory',    'core',     4, t2),
            # Semester 5
            ('CS401', 'Computer Networks',               'theory',    'core',     4, t3),
            ('CS402', 'Software Engineering',            'theory',    'core',     3, t2),
            ('CS403', 'Theory of Computation',           'theory',    'core',     3, t4),
        ]

        for code, name, stype, sclass, credits, teacher in subjects_data:
            Subject.objects.get_or_create(
                subject_code=code,
                defaults={
                    'subject_name': name,
                    'subject_type': stype,
                    'subject_classification': sclass,
                    'subject_credit': credits,
                    'assigned_teacher': teacher,
                }
            )

        self.stdout.write(self.style.SUCCESS(f'   ✓ {len(subjects_data)} subjects'))

    # ─────────────────────────────────────────────────────────────────────
    def _create_students(self):
        from accounts.models import User, Branch, Student, StudentProfile, ParentDetail, PermanentAddress, PresentAddress
        self.stdout.write('🎓 Creating students...')

        cse = Branch.objects.get(branch_code='CSE')

        # Student data: (student_id, enrollment, roll, name, dob, gender, mobile, email, state, father_name, father_mobile, father_email, mother_name, mother_mobile)
        students_raw = [
            ('BCS2024001', 'EN24CSE001', 'CSE3A01', 'Aarav Sharma',     '2003-05-14', 'M', '9900001001', 'aarav.sharma@gmail.com',    'Uttar Pradesh',  'Suresh Sharma',    '9800001001', 'suresh.s@gmail.com',    'Kavita Sharma',    '9800001002'),
            ('BCS2024002', 'EN24CSE002', 'CSE3A02', 'Priya Singh',      '2003-08-22', 'F', '9900001002', 'priya.singh@gmail.com',     'Delhi',          'Mohan Singh',      '9800001003', 'mohan.s@gmail.com',     'Asha Singh',       '9800001004'),
            ('BCS2024003', 'EN24CSE003', 'CSE3A03', 'Rohan Verma',      '2002-11-30', 'M', '9900001003', 'rohan.verma@gmail.com',     'Haryana',        'Ramesh Verma',     '9800001005', 'ramesh.v@gmail.com',    'Sunita Verma',     '9800001006'),
            ('BCS2024004', 'EN24CSE004', 'CSE3A04', 'Sneha Gupta',      '2003-03-17', 'F', '9900001004', 'sneha.gupta@gmail.com',     'Rajasthan',      'Anil Gupta',       '9800001007', 'anil.g@gmail.com',      'Reena Gupta',      '9800001008'),
            ('BCS2024005', 'EN24CSE005', 'CSE3A05', 'Arjun Patel',      '2003-07-09', 'M', '9900001005', 'arjun.patel@gmail.com',     'Gujarat',        'Dinesh Patel',     '9800001009', 'dinesh.p@gmail.com',    'Hema Patel',       '9800001010'),
            ('BCS2024006', 'EN24CSE006', 'CSE3A06', 'Kavya Nair',       '2002-12-25', 'F', '9900001006', 'kavya.nair@gmail.com',      'Kerala',         'Vijay Nair',       '9800001011', 'vijay.n@gmail.com',     'Lakshmi Nair',     '9800001012'),
            ('BCS2024007', 'EN24CSE007', 'CSE3A07', 'Dev Mishra',       '2003-02-14', 'M', '9900001007', 'dev.mishra@gmail.com',      'Uttar Pradesh',  'Prakash Mishra',   '9800001013', 'prakash.m@gmail.com',   'Suman Mishra',     '9800001014'),
            ('BCS2024008', 'EN24CSE008', 'CSE3A08', 'Ananya Rao',       '2003-06-11', 'F', '9900001008', 'ananya.rao@gmail.com',      'Andhra Pradesh', 'Krishna Rao',      '9800001015', 'krishna.r@gmail.com',   'Padma Rao',        '9800001016'),
            ('BCS2024009', 'EN24CSE009', 'CSE3A09', 'Karan Malhotra',   '2002-09-28', 'M', '9900001009', 'karan.m@gmail.com',         'Punjab',         'Harpreet Malhotra','9800001017', 'harpreet.m@gmail.com',  'Gurpreet Malhotra','9800001018'),
            ('BCS2024010', 'EN24CSE010', 'CSE3A10', 'Ishita Joshi',     '2003-04-05', 'F', '9900001010', 'ishita.joshi@gmail.com',    'Uttarakhand',    'Manoj Joshi',      '9800001019', 'manoj.j@gmail.com',     'Pooja Joshi',      '9800001020'),
            ('BCS2024011', 'EN24CSE011', 'CSE3B01', 'Ravi Kumar',       '2003-01-19', 'M', '9900001011', 'ravi.kumar@gmail.com',      'Bihar',          'Ramkumar',         '9800001021', 'ramkumar@gmail.com',    'Savita Devi',      '9800001022'),
            ('BCS2024012', 'EN24CSE012', 'CSE3B02', 'Pooja Bansal',     '2002-10-07', 'F', '9900001012', 'pooja.bansal@gmail.com',    'Haryana',        'Naresh Bansal',    '9800001023', 'naresh.b@gmail.com',    'Rekha Bansal',     '9800001024'),
            ('BCS2024013', 'EN24CSE013', 'CSE3B03', 'Aditya Chauhan',   '2003-05-23', 'M', '9900001013', 'aditya.c@gmail.com',        'Himachal Pradesh','Rajiv Chauhan',   '9800001025', 'rajiv.c@gmail.com',     'Meena Chauhan',    '9800001026'),
            ('BCS2024014', 'EN24CSE014', 'CSE3B04', 'Nisha Tiwari',     '2003-08-16', 'F', '9900001014', 'nisha.tiwari@gmail.com',    'Madhya Pradesh', 'Shiv Tiwari',      '9800001027', 'shiv.t@gmail.com',      'Geeta Tiwari',     '9800001028'),
            ('BCS2024015', 'EN24CSE015', 'CSE3B05', 'Siddharth Bose',   '2002-11-03', 'M', '9900001015', 'siddharth.b@gmail.com',     'West Bengal',    'Subrata Bose',     '9800001029', 'subrata.b@gmail.com',   'Mita Bose',        '9800001030'),
            ('BCS2024016', 'EN24CSE016', 'CSE3B06', 'Divya Menon',      '2003-03-29', 'F', '9900001016', 'divya.menon@gmail.com',     'Kerala',         'Sunil Menon',      '9800001031', 'sunil.m@gmail.com',     'Asha Menon',       '9800001032'),
            ('BCS2024017', 'EN24CSE017', 'CSE3B07', 'Yash Agarwal',     '2003-07-15', 'M', '9900001017', 'yash.agarwal@gmail.com',    'Uttar Pradesh',  'Rakesh Agarwal',   '9800001033', 'rakesh.a@gmail.com',    'Seema Agarwal',    '9800001034'),
            ('BCS2024018', 'EN24CSE018', 'CSE3B08', 'Megha Pillai',     '2002-12-08', 'F', '9900001018', 'megha.pillai@gmail.com',    'Tamil Nadu',     'Rajan Pillai',     '9800001035', 'rajan.p@gmail.com',     'Uma Pillai',       '9800001036'),
            ('BCS2024019', 'EN24CSE019', 'CSE3B09', 'Harsh Pandey',     '2003-02-27', 'M', '9900001019', 'harsh.pandey@gmail.com',    'Uttar Pradesh',  'Umesh Pandey',     '9800001037', 'umesh.p@gmail.com',     'Anita Pandey',     '9800001038'),
            ('BCS2024020', 'EN24CSE020', 'CSE3B10', 'Swati Desai',      '2003-06-20', 'F', '9900001020', 'swati.desai@gmail.com',     'Maharashtra',    'Nitin Desai',      '9800001039', 'nitin.d@gmail.com',     'Smita Desai',      '9800001040'),
        ]

        cities = ['Lucknow', 'Delhi', 'Gurgaon', 'Jaipur', 'Ahmedabad', 'Kochi', 'Kanpur', 'Hyderabad',
                  'Chandigarh', 'Dehradun', 'Patna', 'Faridabad', 'Shimla', 'Bhopal', 'Kolkata',
                  'Thiruvananthapuram', 'Agra', 'Chennai', 'Varanasi', 'Pune']
        pincodes = ['226001', '110001', '122001', '302001', '380001', '682001', '208001', '500001',
                    '160001', '248001', '800001', '121001', '171001', '462001', '700001',
                    '695001', '282001', '600001', '221001', '411001']

        for i, (sid, enroll, roll, name, dob, gender, mobile, email, state, fname, fmob, femail, mname, mmob) in enumerate(students_raw):
            if User.objects.filter(username=sid).exists():
                continue

            section = 'A' if i < 10 else 'B'

            user = User.objects.create_user(username=sid, password='student@123', role='student')

            student = Student.objects.create(
                student_id=sid,
                user=user,
                enrollment_number=enroll,
                roll_number=roll,
                rfid_number=f'RFID{str(i+1).zfill(4)}',
                aadhar_number=f'{str(i+1).zfill(4)}00000000{str(i+1).zfill(2)}',
            )

            StudentProfile.objects.create(
                student=student,
                name=name,
                dob=dob,
                gender=gender,
                mobile_number=mobile,
                email=email,
                nationality='Indian',
                marital_status='single',
                domicile_state=state,
                date_of_joining='2024-08-01',
                academic_year='2024-2025',
                branch=cse,
            )

            ParentDetail.objects.create(
                student=student,
                father_name=fname,
                father_occupation='Business',
                father_mobile=fmob,
                father_email=femail,
                mother_name=mname,
                mother_occupation='Homemaker',
                mother_mobile=mmob,
            )

            city = cities[i]
            pin  = pincodes[i]

            PermanentAddress.objects.create(
                student=student,
                address_line1=f'House No. {i+1}, Main Road',
                address_line2=f'{city} Colony',
                state=state,
                place=city,
                pincode=pin,
            )

            PresentAddress.objects.create(
                student=student,
                address_line1=f'Room {i+101}, Hostel Block {chr(65 + i % 4)}',
                address_line2='College Campus',
                state='Haryana',
                place='Faridabad',
                pincode='121001',
            )

        self.stdout.write(self.style.SUCCESS(f'   ✓ 20 students (BCS2024001–020 / student@123)'))

    # ─────────────────────────────────────────────────────────────────────
    def _create_course_registrations(self):
        from accounts.models import Student
        from academics.models import Subject, CourseRegistration
        self.stdout.write('📋 Creating course registrations...')

        students_a = list(Student.objects.filter(roll_number__contains='3A'))
        students_b = list(Student.objects.filter(roll_number__contains='3B'))

        sem3_subjects = ['CS301', 'CS302', 'CS303', 'CS304', 'CS305', 'CS306', 'MA301', 'PH301']

        count = 0
        for subj_code in sem3_subjects:
            subj = Subject.objects.get(subject_code=subj_code)

            for student in students_a:
                CourseRegistration.objects.get_or_create(
                    student=student, subject=subj,
                    defaults={'branch_id': 'CSE', 'semester': 3, 'section': 'A'}
                )
                count += 1

            for student in students_b:
                CourseRegistration.objects.get_or_create(
                    student=student, subject=subj,
                    defaults={'branch_id': 'CSE', 'semester': 3, 'section': 'B'}
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {count} registrations'))

    # ─────────────────────────────────────────────────────────────────────
    def _create_timetable(self):
        from academics.models import Subject, TimeTable
        self.stdout.write('🗓  Creating timetable...')

        # Section A timetable
        timetable_a = [
            # (subject_code, day, period, start_time, end_time)
            ('CS301', 'Monday',    1, '09:00', '10:00'),
            ('CS302', 'Monday',    2, '10:00', '11:00'),
            ('MA301', 'Monday',    3, '11:15', '12:15'),
            ('CS303', 'Tuesday',   1, '09:00', '10:00'),
            ('CS304', 'Tuesday',   2, '10:00', '11:00'),
            ('PH301', 'Tuesday',   3, '11:15', '12:15'),
            ('CS301', 'Wednesday', 1, '09:00', '10:00'),
            ('CS305', 'Wednesday', 2, '10:00', '12:00'),  # Lab — 2 hours
            ('CS302', 'Thursday',  1, '09:00', '10:00'),
            ('MA301', 'Thursday',  2, '10:00', '11:00'),
            ('CS303', 'Friday',    1, '09:00', '10:00'),
            ('CS306', 'Friday',    2, '10:00', '12:00'),  # Lab
        ]

        count = 0
        for subj_code, day, period, start, end in timetable_a:
            subj = Subject.objects.get(subject_code=subj_code)
            for section in ['A', 'B']:
                TimeTable.objects.get_or_create(
                    branch_id='CSE', subject=subj, semester=3,
                    section=section, day=day, period_number=period,
                    defaults={'start_time': start, 'end_time': end, 'academic_year': '2024-2025'}
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f'   ✓ {count} timetable entries'))

    # ─────────────────────────────────────────────────────────────────────
    def _create_attendance(self):
        from accounts.models import Student, Teacher
        from academics.models import Subject
        from attendance.models import Attendance, AttendanceSession
        self.stdout.write('📊 Creating attendance sessions & records...')

        t1 = Teacher.objects.get(employee_id='T001')
        t2 = Teacher.objects.get(employee_id='T002')
        t4 = Teacher.objects.get(employee_id='T004')
        t6 = Teacher.objects.get(employee_id='T006')

        students_a = list(Student.objects.filter(roll_number__contains='3A'))
        students_b = list(Student.objects.filter(roll_number__contains='3B'))

        # Attendance patterns: student_id → present probability
        # Good students ~90%, average ~75%, poor ~55%, critical ~40%
        patterns = {
            'BCS2024001': 0.92, 'BCS2024002': 0.88, 'BCS2024003': 0.78,
            'BCS2024004': 0.95, 'BCS2024005': 0.65, 'BCS2024006': 0.82,
            'BCS2024007': 0.45, 'BCS2024008': 0.90, 'BCS2024009': 0.72,
            'BCS2024010': 0.55, 'BCS2024011': 0.88, 'BCS2024012': 0.76,
            'BCS2024013': 0.92, 'BCS2024014': 0.40, 'BCS2024015': 0.85,
            'BCS2024016': 0.70, 'BCS2024017': 0.60, 'BCS2024018': 0.95,
            'BCS2024019': 0.48, 'BCS2024020': 0.80,
        }

        # Sessions to create: (subject_code, teacher, section, days_per_week)
        session_configs = [
            ('CS301', t1, ['A', 'B'], ['Monday', 'Wednesday']),
            ('CS302', t2, ['A', 'B'], ['Monday', 'Thursday']),
            ('CS303', t4, ['A', 'B'], ['Tuesday', 'Friday']),
            ('CS304', t6, ['A', 'B'], ['Tuesday']),
            ('MA301', t4, ['A', 'B'], ['Monday', 'Thursday']),
        ]

        today = datetime.date.today()
        total_sessions = 0
        total_records  = 0

        for subj_code, teacher, sections, weekdays in session_configs:
            subj = Subject.objects.get(subject_code=subj_code)

            for section in sections:
                students = students_a if section == 'A' else students_b

                # Generate past 35 days of sessions for this subject
                current = today - datetime.timedelta(days=35)
                while current <= today - datetime.timedelta(days=1):
                    day_name = current.strftime('%A')

                    if day_name in weekdays:
                        # Create session
                        session, created = AttendanceSession.objects.get_or_create(
                            subject=subj,
                            branch_id='CSE',
                            teacher=teacher,
                            semester=3,
                            section=section,
                            date=current,
                            defaults={
                                'academic_year': '2024-2025',
                                'status': 'closed',
                                'facial_enabled': False,
                                'geo_fencing_enabled': False,
                            }
                        )
                        if created:
                            total_sessions += 1

                        # Create attendance for each student
                        for student in students:
                            prob = patterns.get(student.student_id, 0.75)
                            # Add some randomness
                            is_present = random.random() < prob

                            _, att_created = Attendance.objects.get_or_create(
                                student=student,
                                subject=subj,
                                date=current,
                                defaults={
                                    'is_present': is_present,
                                    'day': day_name,
                                    'semester': 3,
                                    'academic_year': '2024-2025',
                                    'marked_by': teacher,
                                    'method': 'manual',
                                    'location_verified': False,
                                }
                            )
                            if att_created:
                                total_records += 1

                    current += datetime.timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f'   ✓ {total_sessions} sessions, {total_records} attendance records'))

    # ─────────────────────────────────────────────────────────────────────
    def _create_leaves(self):
        from accounts.models import Student, Teacher
        from attendance.models import LeaveRequest
        self.stdout.write('📝 Creating leave requests...')

        t1 = Teacher.objects.get(employee_id='T001')
        today = datetime.date.today()

        leaves_data = [
            # (student_id, reason, from_date, to_date, status, remarks)
            ('BCS2024001', 'Medical emergency — hospitalized', today - datetime.timedelta(days=20), today - datetime.timedelta(days=18), 'approved',  'Medical certificate verified'),
            ('BCS2024003', 'Family function — sister marriage', today - datetime.timedelta(days=15), today - datetime.timedelta(days=13), 'approved',  'Approved'),
            ('BCS2024005', 'Fever and cold', today - datetime.timedelta(days=10), today - datetime.timedelta(days=9),  'approved',  'Get well soon'),
            ('BCS2024007', 'Personal reasons', today - datetime.timedelta(days=8),  today - datetime.timedelta(days=7),  'rejected',  'Insufficient reason provided'),
            ('BCS2024010', 'Inter-college sports event', today - datetime.timedelta(days=6),  today - datetime.timedelta(days=5),  'approved',  'Sports achievement — approved'),
            ('BCS2024014', 'Exam preparation — board exam', today - datetime.timedelta(days=4),  today - datetime.timedelta(days=3),  'rejected',  'Cannot approve during semester'),
            ('BCS2024019', 'Death in family', today - datetime.timedelta(days=12), today - datetime.timedelta(days=10), 'approved',  'Condolences — approved'),
            # Pending leaves
            ('BCS2024002', 'Medical appointment — doctor visit', today + datetime.timedelta(days=2),  today + datetime.timedelta(days=2),  'pending',   ''),
            ('BCS2024009', 'Out-of-station family program', today + datetime.timedelta(days=3),  today + datetime.timedelta(days=5),  'pending',   ''),
            ('BCS2024016', 'Fever — feeling unwell', today + datetime.timedelta(days=1),  today + datetime.timedelta(days=1),  'pending',   ''),
        ]

        count = 0
        for sid, reason, from_date, to_date, status, remarks in leaves_data:
            try:
                student = Student.objects.get(student_id=sid)
                leave, created = LeaveRequest.objects.get_or_create(
                    student=student,
                    from_date=from_date,
                    to_date=to_date,
                    defaults={
                        'reason': reason,
                        'status': status,
                        'remarks': remarks,
                        'reviewed_by': t1 if status != 'pending' else None,
                        'reviewed_on': timezone.now() if status != 'pending' else None,
                    }
                )
                if created:
                    count += 1
            except Student.DoesNotExist:
                pass

        self.stdout.write(self.style.SUCCESS(f'   ✓ {count} leave requests (approved/rejected/pending)'))

    # ─────────────────────────────────────────────────────────────────────
    def _print_credentials(self):
        self.stdout.write('\n' + '='*55)
        self.stdout.write(self.style.SUCCESS('  LOGIN CREDENTIALS'))
        self.stdout.write('='*55)
        self.stdout.write(self.style.WARNING('  ADMIN'))
        self.stdout.write('  Username : admin001')
        self.stdout.write('  Password : admin@123')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('  TEACHERS  (T001–T006)'))
        self.stdout.write('  Username : T001, T002, T003, T004, T005, T006')
        self.stdout.write('  Password : teacher@123')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('  STUDENTS  (BCS2024001–020)'))
        self.stdout.write('  Username : BCS2024001 ... BCS2024020')
        self.stdout.write('  Password : student@123')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('  ATTENDANCE PATTERNS'))
        self.stdout.write('  ~90%+ : BCS2024001, 002, 004, 008, 011, 013, 015, 018')
        self.stdout.write('  ~75%  : BCS2024003, 006, 009, 012, 016, 020')
        self.stdout.write('  ~55%  : BCS2024005, 010, 017')
        self.stdout.write('  ~45%  : BCS2024007, 014, 019  ← critical')
        self.stdout.write('='*55 + '\n')
