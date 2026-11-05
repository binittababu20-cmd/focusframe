from django.contrib import admin
from .models import TeacherRequest, Attendance, ClassroomSession, StudentDevice


# =========================================================
# TEACHER REQUEST
# =========================================================

@admin.register(TeacherRequest)
class TeacherRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "teacher_id", "department", "email", "status")
    list_filter = ("status",)
    search_fields = ("name", "teacher_id", "email")


# =========================================================
# ATTENDANCE
# =========================================================

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "classroom", "date", "time", "status")
    list_filter = ("status", "classroom")
    search_fields = ("student__username", "classroom")


# =========================================================
# CLASSROOM SESSION
# =========================================================

@admin.register(ClassroomSession)
class ClassroomSessionAdmin(admin.ModelAdmin):
    list_display = ("classroom", "teacher", "session_time", "active", "created_at")
    list_filter = ("active",)
    search_fields = ("classroom", "teacher__username")


# =========================================================
# STUDENT DEVICE
# =========================================================

@admin.register(StudentDevice)
class StudentDeviceAdmin(admin.ModelAdmin):
    list_display = ("student_name", "register_number", "device_name", "imei_number", "android_version", "registered_at")
    search_fields = ("student_name", "register_number", "imei_number")
