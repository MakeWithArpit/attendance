from academics.models import Subject
from accounts.models import Branch, Teacher

T001 = Teacher.objects.get(employee_id='T001')
T002 = Teacher.objects.get(employee_id='T002')
T003 = Teacher.objects.get(employee_id='T003')
T004 = Teacher.objects.get(employee_id='T004')
T005 = Teacher.objects.get(employee_id='T005')
T006 = Teacher.objects.get(employee_id='T006')
TECE = Teacher.objects.get(employee_id='T-ECE001')
CSE = Branch.objects.get(branch_code='CSE')
ECE = Branch.objects.get(branch_code='ECE')
ME  = Branch.objects.get(branch_code='ME')
CE  = Branch.objects.get(branch_code='CE')

data = [

    # ==================== CSE SEM 1 ====================
    ('CS101','Programming Fundamentals','theory','core',4,1,CSE,T001),
    ('CS102','Introduction to Computing','theory','core',3,1,CSE,T002),
    ('CS103','Programming Lab','practical','lab',2,1,CSE,T001),
    ('MA101','Engineering Mathematics I','theory','core',4,1,CSE,T004),
    ('PH101','Engineering Physics','theory','core',3,1,CSE,T005),
    ('PH102','Physics Lab','practical','lab',1,1,CSE,T005),

    # ==================== CSE SEM 2 ====================
    ('CS201','Object Oriented Programming','theory','core',4,2,CSE,T006),
    ('CS202','Digital Logic Design','theory','core',3,2,CSE,T001),
    ('CS203','OOP Lab','practical','lab',2,2,CSE,T006),
    ('MA201','Engineering Mathematics II','theory','core',4,2,CSE,T004),
    ('CS204','Computer Architecture','theory','core',3,2,CSE,T002),

    # ==================== CSE SEM 3 ====================
    ('CS301','Data Structures and Algorithms','theory','core',4,3,CSE,T001),
    ('CS302','Computer Organization','theory','core',3,3,CSE,T002),
    ('CS303','Discrete Mathematics','theory','core',3,3,CSE,T004),
    ('CS304','Object Oriented Design','theory','core',4,3,CSE,T006),
    ('CS305','OOP Lab','practical','lab',2,3,CSE,T006),
    ('CS306','Data Structures Lab','practical','lab',2,3,CSE,T001),
    ('MA301','Engineering Mathematics III','theory','core',3,3,CSE,T004),
    ('PH301','Applied Physics','theory','core',3,3,CSE,T005),

    # ==================== CSE SEM 4 ====================
    ('CS401','Computer Networks','theory','core',4,4,CSE,T003),
    ('CS402','Software Engineering','theory','core',3,4,CSE,T002),
    ('CS403','Theory of Computation','theory','core',3,4,CSE,TECE),
    ('CS404','Operating Systems','theory','core',4,4,CSE,T001),
    ('CS405','OS Lab','practical','lab',2,4,CSE,T001),
    ('CS406','Network Lab','practical','lab',2,4,CSE,T003),

    # ==================== CSE SEM 5 ====================
    ('CS501','Database Management Systems','theory','core',4,5,CSE,T002),
    ('CS502','Compiler Design','theory','core',3,5,CSE,T001),
    ('CS503','Web Technologies','theory','elective',3,5,CSE,T006),
    ('CS504','DBMS Lab','practical','lab',2,5,CSE,T002),
    ('CS505','Web Tech Lab','practical','lab',2,5,CSE,T006),

    # ==================== CSE SEM 6 ====================
    ('CS601','Artificial Intelligence','theory','core',4,6,CSE,T001),
    ('CS602','Machine Learning','theory','elective',3,6,CSE,T002),
    ('CS603','Cloud Computing','theory','elective',3,6,CSE,T006),
    ('CS604','AI Lab','practical','lab',2,6,CSE,T001),
    ('CS605','Minor Project','practical','core',4,6,CSE,T002),

    # ==================== CSE SEM 7 ====================
    ('CS701','Distributed Systems','theory','core',4,7,CSE,T001),
    ('CS702','Information Security','theory','core',3,7,CSE,T003),
    ('CS703','Mobile Computing','theory','elective',3,7,CSE,T006),
    ('CS704','Security Lab','practical','lab',2,7,CSE,T003),
    ('CS705','Industrial Training','practical','core',4,7,CSE,T002),

    # ==================== CSE SEM 8 ====================
    ('CS801','Big Data Analytics','theory','elective',3,8,CSE,T002),
    ('CS802','Deep Learning','theory','elective',3,8,CSE,T001),
    ('CS803','Major Project','practical','core',8,8,CSE,T006),
    ('CS804','Seminar','practical','core',2,8,CSE,T002),

    # ==================== ECE SEM 1 ====================
    ('ECE101','Basic Electronics','theory','core',4,1,ECE,T003),
    ('ECE102','Circuit Theory','theory','core',3,1,ECE,TECE),
    ('ECE103','Electronics Lab','practical','lab',2,1,ECE,T003),
    ('MA102','Engineering Mathematics I','theory','core',4,1,ECE,T004),
    ('PH103','Engineering Physics','theory','core',3,1,ECE,T005),

    # ==================== ECE SEM 2 ====================
    ('ECE201','Network Analysis','theory','core',4,2,ECE,TECE),
    ('ECE202','Electronic Devices','theory','core',3,2,ECE,T003),
    ('ECE203','Circuit Lab','practical','lab',2,2,ECE,T003),
    ('MA202','Engineering Mathematics II','theory','core',4,2,ECE,T004),
    ('ECE204','Programming in C','theory','core',3,2,ECE,T001),

    # ==================== ECE SEM 3 ====================
    ('ECE301','Signals and Systems','theory','core',4,3,ECE,TECE),
    ('ECE302','Analog Electronics','theory','core',3,3,ECE,T003),
    ('ECE303','Digital Electronics','theory','core',3,3,ECE,TECE),
    ('ECE304','Analog Lab','practical','lab',2,3,ECE,T003),
    ('ECE305','Digital Lab','practical','lab',2,3,ECE,TECE),

    # ==================== ECE SEM 4 ====================
    ('ECE401','Control Systems','theory','core',4,4,ECE,TECE),
    ('ECE402','Electromagnetic Theory','theory','core',3,4,ECE,T003),
    ('ECE403','Microelectronics','theory','core',3,4,ECE,TECE),
    ('ECE404','Control Systems Lab','practical','lab',2,4,ECE,TECE),
    ('ECE405','Microelectronics Lab','practical','lab',2,4,ECE,T003),

    # ==================== ECE SEM 5 ====================
    ('ECE501','Communication Systems','theory','core',4,5,ECE,TECE),
    ('ECE502','Microprocessors','theory','core',3,5,ECE,T003),
    ('ECE503','Embedded Systems','theory','elective',3,5,ECE,TECE),
    ('ECE504','Micro Lab','practical','lab',2,5,ECE,T003),
    ('ECE505','Communication Lab','practical','lab',2,5,ECE,TECE),

    # ==================== ECE SEM 6 ====================
    ('ECE601','Digital Communication','theory','core',4,6,ECE,TECE),
    ('ECE602','Antenna and Wave Propagation','theory','core',3,6,ECE,T003),
    ('ECE603','Power Electronics','theory','elective',3,6,ECE,TECE),
    ('ECE604','Digital Comm Lab','practical','lab',2,6,ECE,TECE),
    ('ECE605','Minor Project','practical','core',4,6,ECE,T003),

    # ==================== ECE SEM 7 ====================
    ('ECE701','Wireless Communication','theory','core',4,7,ECE,TECE),
    ('ECE702','VLSI Design','theory','core',3,7,ECE,T003),
    ('ECE703','Digital Signal Processing','theory','core',3,7,ECE,TECE),
    ('ECE704','VLSI Lab','practical','lab',2,7,ECE,T003),
    ('ECE705','Industrial Training','practical','core',4,7,ECE,TECE),

    # ==================== ECE SEM 8 ====================
    ('ECE801','Digital Signal Processing Adv','theory','core',4,8,ECE,TECE),
    ('ECE802','VLSI Design Advanced','theory','core',3,8,ECE,T003),
    ('ECE803','IoT and Smart Systems','theory','elective',3,8,ECE,TECE),
    ('ECE804','Major Project','practical','core',8,8,ECE,TECE),

    # ==================== ME SEM 1 ====================
    ('ME101','Engineering Mechanics','theory','core',4,1,ME,T005),
    ('ME102','Engineering Drawing','practical','core',3,1,ME,T005),
    ('MA103','Engineering Mathematics I','theory','core',4,1,ME,T004),
    ('PH104','Engineering Physics','theory','core',3,1,ME,T005),
    ('ME103','Workshop Practice','practical','lab',2,1,ME,T005),

    # ==================== ME SEM 2 ====================
    ('ME201','Strength of Materials','theory','core',4,2,ME,T005),
    ('ME202','Thermodynamics I','theory','core',3,2,ME,T005),
    ('ME203','Manufacturing Processes','theory','core',3,2,ME,T005),
    ('ME204','Strength Lab','practical','lab',2,2,ME,T005),
    ('MA203','Engineering Mathematics II','theory','core',4,2,ME,T004),

    # ==================== ME SEM 3 ====================
    ('ME301','Engineering Thermodynamics','theory','core',4,3,ME,T005),
    ('ME302','Fluid Mechanics','theory','core',3,3,ME,T005),
    ('ME303','Manufacturing Technology','theory','core',3,3,ME,T005),
    ('ME304','Thermodynamics Lab','practical','lab',2,3,ME,T005),
    ('ME305','Fluid Mechanics Lab','practical','lab',2,3,ME,T005),

    # ==================== ME SEM 4 ====================
    ('ME401','Kinematics of Machines','theory','core',4,4,ME,T005),
    ('ME402','Heat Transfer','theory','core',3,4,ME,T005),
    ('ME403','Metrology and Measurement','theory','core',3,4,ME,T005),
    ('ME404','Heat Transfer Lab','practical','lab',2,4,ME,T005),
    ('ME405','Metrology Lab','practical','lab',2,4,ME,T005),

    # ==================== ME SEM 5 ====================
    ('ME501','Machine Design','theory','core',4,5,ME,T005),
    ('ME502','Internal Combustion Engines','theory','core',3,5,ME,T005),
    ('ME503','CAD CAM','theory','elective',3,5,ME,T005),
    ('ME504','Machine Design Lab','practical','lab',2,5,ME,T005),
    ('ME505','CAD Lab','practical','lab',2,5,ME,T005),

    # ==================== ME SEM 6 ====================
    ('ME601','Automobile Engineering','theory','core',4,6,ME,T005),
    ('ME602','Refrigeration and AC','theory','core',3,6,ME,T005),
    ('ME603','Industrial Engineering','theory','elective',3,6,ME,T005),
    ('ME604','Automobile Lab','practical','lab',2,6,ME,T005),
    ('ME605','Minor Project','practical','core',4,6,ME,T005),

    # ==================== ME SEM 7 ====================
    ('ME701','Finite Element Analysis','theory','core',4,7,ME,T005),
    ('ME702','Power Plant Engineering','theory','core',3,7,ME,T005),
    ('ME703','Robotics and Automation','theory','elective',3,7,ME,T005),
    ('ME704','FEA Lab','practical','lab',2,7,ME,T005),
    ('ME705','Industrial Training','practical','core',4,7,ME,T005),

    # ==================== ME SEM 8 ====================
    ('ME801','Advanced Manufacturing','theory','elective',3,8,ME,T005),
    ('ME802','Project Management','theory','core',3,8,ME,T005),
    ('ME803','Major Project','practical','core',8,8,ME,T005),
    ('ME804','Seminar','practical','core',2,8,ME,T005),

    # ==================== CE SEM 1 ====================
    ('CE101','Engineering Mechanics','theory','core',4,1,CE,T005),
    ('CE102','Engineering Drawing','practical','core',3,1,CE,T005),
    ('MA104','Engineering Mathematics I','theory','core',4,1,CE,T004),
    ('PH105','Engineering Physics','theory','core',3,1,CE,T005),
    ('CE103','Workshop Lab','practical','lab',2,1,CE,T005),

    # ==================== CE SEM 2 ====================
    ('CE201','Strength of Materials','theory','core',4,2,CE,T005),
    ('CE202','Fluid Mechanics I','theory','core',3,2,CE,T005),
    ('CE203','Engineering Geology','theory','core',3,2,CE,T005),
    ('CE204','Strength Lab','practical','lab',2,2,CE,T005),
    ('MA204','Engineering Mathematics II','theory','core',4,2,CE,T004),

    # ==================== CE SEM 3 ====================
    ('CE301','Structural Analysis','theory','core',4,3,CE,T005),
    ('CE302','Concrete Technology','theory','core',3,3,CE,T005),
    ('CE303','Surveying','theory','core',3,3,CE,T005),
    ('CE304','Surveying Lab','practical','lab',2,3,CE,T005),
    ('CE305','Concrete Lab','practical','lab',2,3,CE,T005),

    # ==================== CE SEM 4 ====================
    ('CE401','Geotechnical Engineering I','theory','core',4,4,CE,T005),
    ('CE402','Water Resources Engineering','theory','core',3,4,CE,T005),
    ('CE403','Design of Structures','theory','core',3,4,CE,T005),
    ('CE404','Geotech Lab','practical','lab',2,4,CE,T005),
    ('CE405','Hydraulics Lab','practical','lab',2,4,CE,T005),

    # ==================== CE SEM 5 ====================
    ('CE501','Geotechnical Engineering II','theory','core',4,5,CE,T005),
    ('CE502','Transportation Engineering','theory','core',3,5,CE,T005),
    ('CE503','Environmental Engineering','theory','elective',3,5,CE,T005),
    ('CE504','Geotech Lab II','practical','lab',2,5,CE,T005),
    ('CE505','Environmental Lab','practical','lab',2,5,CE,T005),

    # ==================== CE SEM 6 ====================
    ('CE601','Structural Design','theory','core',4,6,CE,T005),
    ('CE602','Construction Management','theory','core',3,6,CE,T005),
    ('CE603','Remote Sensing and GIS','theory','elective',3,6,CE,T005),
    ('CE604','Structural Lab','practical','lab',2,6,CE,T005),
    ('CE605','Minor Project','practical','core',4,6,CE,T005),

    # ==================== CE SEM 7 ====================
    ('CE701','Advanced Structural Analysis','theory','core',4,7,CE,T005),
    ('CE702','Bridge Engineering','theory','core',3,7,CE,T005),
    ('CE703','Earthquake Engineering','theory','elective',3,7,CE,T005),
    ('CE704','Bridge Design Lab','practical','lab',2,7,CE,T005),
    ('CE705','Industrial Training','practical','core',4,7,CE,T005),

    # ==================== CE SEM 8 ====================
    ('CE801','Urban Planning','theory','elective',3,8,CE,T005),
    ('CE802','Project Estimation','theory','core',3,8,CE,T005),
    ('CE803','Major Project','practical','core',8,8,CE,T005),
    ('CE804','Seminar','practical','core',2,8,CE,T005),
]

created = updated = 0
for code,name,stype,cls,credit,sem,branch,teacher in data:
    obj, was_created = Subject.objects.update_or_create(
        subject_code=code,
        defaults={
            'subject_name': name,
            'subject_type': stype,
            'subject_classification': cls,
            'subject_credit': credit,
            'semester': sem,
            'branch': branch,
            'assigned_teacher': teacher,
        }
    )
    if was_created:
        created += 1
    else:
        updated += 1

print("Done!")
print("Created:", created)
print("Updated:", updated)
print("Total:", created + updated, "subjects")
print()
for b in ['CSE','ECE','ME','CE']:
    sems = list(Subject.objects.filter(branch__branch_code=b).values_list('semester',flat=True).distinct().order_by('semester'))
    cnt = Subject.objects.filter(branch__branch_code=b).count()
    print(b + ": " + str(cnt) + " subjects | Semesters: " + str(sems))