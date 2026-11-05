from django.urls import path
from django.contrib.auth import views as auth_views
from . import views


urlpatterns = [

    # =====================================================
    # HOME
    # =====================================================

    path(
        "",
        views.home,
        name="home"
    ),


    # =====================================================
    # LOGIN
    # =====================================================

    path(
        "login/",
        views.login,
        name="login"
    ),


    # =====================================================
    # REGISTER
    # =====================================================

    path(
        "register/",
        views.register,
        name="register"
    ),


    # =====================================================
    # STUDENT DASHBOARD
    # =====================================================

    path(
        "student/",
        views.student_dashboard,
        name="student_dashboard"
    ),


    # =====================================================
    # TEACHER DASHBOARD
    # =====================================================

    path(
        "teacher/",
        views.teacher_dashboard,
        name="teacher_dashboard"
    ),


    # =====================================================
    # START / STOP MONITORING
    # =====================================================

    path(
        "teacher/start-monitoring/",
        views.start_monitoring,
        name="start_monitoring"
    ),

    path(
        "teacher/stop-monitoring/",
        views.stop_monitoring,
        name="stop_monitoring"
    ),


    # =====================================================
    # ADMIN DASHBOARD
    # =====================================================

    path(
        "admin/",
        views.admin_dashboard,
        name="admin_dashboard"
    ),


    # =====================================================
    # STUDENT LIST
    # =====================================================

    path(
        "admin/students/",
        views.student_list,
        name="student_list"
    ),


    # =====================================================
    # APPROVE TEACHER
    # =====================================================

    path(
        "admin/approve-teacher/<str:teacher_id>/",
        views.approve_teacher,
        name="approve_teacher"
    ),


    # =====================================================
    # REJECT TEACHER
    # =====================================================

    path(
        "admin/reject-teacher/<str:teacher_id>/",
        views.reject_teacher,
        name="reject_teacher"
    ),


    # =====================================================
    # SCAN QR
    # =====================================================

    path(
        "scan-qr/",
        views.scan_qr,
        name="scan_qr"
    ),


    # =====================================================
    # REGISTER DEVICE
    # =====================================================

    path(
        "register-device/",
        views.register_device,
        name="register_device"
    ),


    # =====================================================
    # LOGOUT
    # =====================================================

    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),


    # =====================================================
    # STUDENT PROFILE
    # =====================================================

    path(
        "student/profile/",
        views.student_profile,
        name="student_profile"
    ),


    # =====================================================
    # FIREBASE TEST
    # =====================================================

    path(
        "firebase-test/",
        views.firebase_test,
        name="firebase_test"
    ),


    # =====================================================
    # PHONE USAGE API
    # =====================================================

    path(
        "api/phone-usage/",
        views.receive_phone_usage,
        name="receive_phone_usage"
    ),


    # =====================================================
    # PASSWORD RESET
    # =====================================================

    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="home/password_reset.html"
        ),
        name="password_reset"
    ),

    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="home/password_reset_done.html"
        ),
        name="password_reset_done"
    ),

    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="home/password_reset_confirm.html"
        ),
        name="password_reset_confirm"
    ),

    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="home/password_reset_complete.html"
        ),
        name="password_reset_complete"
    ),


    # =====================================================
    # REPORTS & ANALYTICS (SPRINT 5)
    # =====================================================

    path(
        "teacher/reports/",
        views.reports_analytics,
        name="reports_analytics"
    ),

    path(
        "teacher/reports/export/attendance/",
        views.export_attendance_csv,
        name="export_attendance_csv"
    ),

    path(
        "teacher/reports/export/usage/",
        views.export_usage_csv,
        name="export_usage_csv"
    ),

    path(
        "teacher/reports/export/focus/",
        views.export_focus_csv,
        name="export_focus_csv"
    ),

]