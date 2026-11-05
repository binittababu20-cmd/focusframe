from django.db import models
from django.contrib.auth.models import User


# =========================================================
# TEACHER REGISTRATION REQUEST
# =========================================================

class TeacherRequest(models.Model):

    name = models.CharField(max_length=100)

    teacher_id = models.CharField(
        max_length=50,
        unique=True
    )

    department = models.CharField(
        max_length=100
    )

    email = models.EmailField()

    # Stores a Django-hashed password
    password = models.CharField(
        max_length=128,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("Pending", "Pending"),
            ("Approved", "Approved"),
            ("Rejected", "Rejected"),
        ],
        default="Pending"
    )

    def __str__(self):
        return f"{self.name} - {self.status}"


# =========================================================
# STUDENT ATTENDANCE
# =========================================================

class Attendance(models.Model):

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    classroom = models.CharField(
        max_length=100
    )

    date = models.DateField(
        auto_now_add=True
    )

    time = models.TimeField(
        auto_now_add=True
    )

    status = models.CharField(
        max_length=20,
        default="Present"
    )

    def __str__(self):
        return (
            f"{self.student.username} - "
            f"{self.classroom} - "
            f"{self.date}"
        )


# =========================================================
# CLASSROOM SESSION
# =========================================================

class ClassroomSession(models.Model):

    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    classroom = models.CharField(
        max_length=100
    )

    session_time = models.CharField(
        max_length=100,
        blank=True
    )

    qr_code = models.CharField(
        max_length=255,
        unique=True
    )

    active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.classroom} - "
            f"{self.teacher.username}"
        )


class StudentDevice(models.Model):
    student_name = models.CharField(max_length=150)
    register_number = models.CharField(max_length=100)
    device_name = models.CharField(max_length=150)
    imei_number = models.CharField(max_length=50)
    android_version = models.CharField(max_length=50)

    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student_name} - {self.device_name}"