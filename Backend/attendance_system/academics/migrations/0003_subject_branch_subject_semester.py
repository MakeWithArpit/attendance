"""
academics/migrations/0003_subject_branch_subject_semester.py

Subject model mein branch aur semester fields add kiye +
existing subjects ko auto-tag kiya based on subject code prefix.
"""
from django.db import migrations, models
import django.db.models.deletion


def tag_existing_subjects(apps, schema_editor):
    Subject = apps.get_model('academics', 'Subject')
    Branch  = apps.get_model('accounts', 'Branch')

    def get_branch(code):
        try:
            return Branch.objects.get(branch_code=code)
        except Branch.DoesNotExist:
            return None

    cse = get_branch('CSE')
    ece = get_branch('ECE')
    me  = get_branch('ME')
    ce  = get_branch('CE')

    rules = [
        # CSE subjects
        ('CS3', cse, 3), ('MA3', cse, 3), ('PH3', cse, 3),
        ('CS4', cse, 4), ('CS5', cse, 5), ('CS6', cse, 6),
        ('CS7', cse, 7), ('CS8', cse, 8),
        # ECE subjects
        ('ECE3', ece, 3), ('EC3', ece, 3),
        ('ECE4', ece, 4), ('EC4', ece, 4),
        ('ECE5', ece, 5), ('EC5', ece, 5),
        ('ECE6', ece, 6), ('EC6', ece, 6),
        ('ECE7', ece, 7), ('EC7', ece, 7),
        ('ECE8', ece, 8), ('EC8', ece, 8),
        # ME subjects
        ('ME3', me, 3), ('ME4', me, 4), ('ME5', me, 5),
        ('ME6', me, 6), ('ME7', me, 7), ('ME8', me, 8),
        # CE subjects
        ('CE3', ce, 3), ('CE4', ce, 4), ('CE5', ce, 5),
        ('CE6', ce, 6), ('CE7', ce, 7), ('CE8', ce, 8),
    ]

    for subject in Subject.objects.all():
        code = subject.subject_code.upper()
        for prefix, branch, semester in rules:
            if code.startswith(prefix) and branch:
                subject.branch   = branch
                subject.semester = semester
                subject.save()
                print(f"  Tagged: {code} → {branch.branch_code}, Sem {semester}")
                break


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_alter_parentdetail_father_mobile_and_more'),
        ('academics', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='branch',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='subjects', to='accounts.branch',
                help_text='Kis branch ka subject hai (auto-enroll ke liye)',
            ),
        ),
        migrations.AddField(
            model_name='subject',
            name='semester',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                choices=[(i, f'Semester {i}') for i in range(1, 9)],
                help_text='Kis semester ka subject hai (auto-enroll ke liye)',
            ),
        ),
        migrations.RunPython(tag_existing_subjects, migrations.RunPython.noop),
    ]
