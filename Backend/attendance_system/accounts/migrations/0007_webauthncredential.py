"""
accounts/migrations/0007_webauthn_credential.py

Creates two tables for WebAuthn passkey support:

  webauthn_credentials  — stores each student's registered public key credential.
                           OneToOneField ensures one passkey per student.

  webauthn_challenges   — short-lived challenge storage used during the
                           register/begin -> register/complete round-trip,
                           and the auth/begin -> auth/complete round-trip.
                           Deleted after successful verification.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_alter_student_student_id'),
    ]

    operations = [
        # Table 1: permanent credential storage
        migrations.CreateModel(
            name='WebAuthnCredential',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('credential_id', models.TextField(unique=True)),
                ('public_key',    models.TextField()),
                ('sign_count',    models.PositiveIntegerField(default=0)),
                ('device_label',  models.CharField(blank=True, max_length=200)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('student',       models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='webauthn_credential',
                    to='accounts.student',
                )),
            ],
            options={
                'db_table': 'webauthn_credentials',
            },
        ),

        # Table 2: ephemeral challenge storage (register + auth round-trips)
        migrations.CreateModel(
            name='WebAuthnChallenge',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('challenge',  models.TextField()),
                ('purpose',    models.CharField(
                    choices=[('register', 'Register'), ('auth', 'Auth')],
                    max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('student',    models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='webauthn_challenges',
                    to='accounts.student',
                )),
            ],
            options={
                'db_table': 'webauthn_challenges',
            },
        ),

        # Enforce one pending challenge per student per purpose
        migrations.AlterUniqueTogether(
            name='webauthnchallenge',
            unique_together={('student', 'purpose')},
        ),
    ]