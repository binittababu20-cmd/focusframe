import base64
import io
import json
import os
import re
import secrets
from datetime import datetime

import qrcode


from home.alert_utils import calculate_alert_severity
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as auth_login, logout
import csv
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from .firebase_config import db
from .alert_utils import (
    detect_alert_condition,
    identify_alert_student,
    store_alert,
    calculate_alert_severity
)
# =========================================================
# FIREBASE HELPER FUNCTIONS
# =========================================================

def firebase_get(path):
    try:
        ref = db.reference(path)
        data = ref.get()
        if data is None:
            return {}
        return data
    except Exception as e:
        print(f"[FIREBASE GET WARNING] {path}: {e}")
        return {}


def firebase_set(path, data):
    try:
        ref = db.reference(path)
        ref.set(data)
    except Exception as e:
        print(f"[FIREBASE SET WARNING] {path}: {e}")


def firebase_push(path, data):
    try:
        ref = db.reference(path)
        return ref.push(data)
    except Exception as e:
        print(f"[FIREBASE PUSH WARNING] {path}: {e}")
        return None


def firebase_update(path, data):
    try:
        ref = db.reference(path)
        ref.update(data)
    except Exception as e:
        print(f"[FIREBASE UPDATE WARNING] {path}: {e}")


# =========================================================
# QR CODE HELPER
# Returns a base64-encoded PNG string suitable for
# embedding directly in an <img src="data:..."> tag.
# The encoded data is the session_id so that scan_qr()
# can look it up in Firebase and validate it is active.
# =========================================================

def generate_qr_b64(data: str) -> str:
    """
    Generate a QR code image for `data` and return it
    as a base64-encoded PNG string.
    """
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


# =========================================================
# ROLE ENFORCEMENT HELPERS
# =========================================================

def _is_admin(request):
    """
    Return True if the logged-in user is the administrator.
    Admin is identified by the reserved username "user" or
    Django superuser flag.
    """
    return (
        request.user.is_authenticated
        and (
            request.user.username.lower() == "user"
            or request.user.is_superuser
        )
    )


def _is_teacher(request):
    """
    Return True if the logged-in user has an approved
    teacher record in Firebase.
    """
    if not request.user.is_authenticated:
        return False

    # Fast path: trust the session role set at login
    if request.session.get("role") == "teacher":
        return True

    # Fast path: if session explicitly says student or admin, they are not a teacher
    if request.session.get("role") in ["student", "admin"]:
        return False

    # Fallback: check Firebase directly
    try:
        teacher_requests = firebase_get("teacher_requests")
        if not teacher_requests:
            return False

        username = request.user.username.strip().lower()

        for teacher_id, data in teacher_requests.items():
            if not isinstance(data, dict):
                continue
            status = str(data.get("status", "")).strip().lower()
            if status == "approved" and str(teacher_id).strip().lower() == username:
                return True

    except Exception:
        pass

    return False


def _require_admin(request):
    """
    Return an HttpResponse redirect if the user is NOT admin,
    otherwise return None (meaning access is granted).
    """
    if not request.user.is_authenticated:
        return redirect("login")

    if not _is_admin(request):
        messages.error(
            request,
            "Access denied. Administrator login required."
        )
        return redirect("home")

    return None


def _require_teacher(request):
    """
    Return a redirect if the user is NOT an approved teacher,
    otherwise return None.
    """
    if not request.user.is_authenticated:
        return redirect("login")

    if not _is_teacher(request):
        messages.error(
            request,
            "Access denied. Approved teacher login required."
        )
        return redirect("home")

    return None


def _is_student(request):
    """
    Return True if the logged-in user is a student.
    Administrators and approved teachers are never students.
    """
    if not request.user.is_authenticated:
        return False

    # Role exclusion: admin cannot be a student
    if _is_admin(request):
        return False

    # Fast path: explicit session role set at login
    session_role = request.session.get("role")
    if session_role == "student":
        return True
    if session_role in ["teacher", "admin"]:
        return False

    # Fallback when session role is not explicitly set:
    if _is_teacher(request):
        return False

    # Fallback: if Firebase user record specifies a non-student role, respect it
    try:
        username = request.user.username.strip()
        student_data = firebase_get(f"users/{username}")
        if isinstance(student_data, dict):
            role = str(student_data.get("role", "")).strip().lower()
            if role and role != "student":
                return False
    except Exception:
        pass

    return True


def _require_student(request, action="access this page"):
    """
    Return a redirect if the user is NOT an authenticated student,
    otherwise return None.
    Teachers and administrators receive an informative message directing
    them to sign in with a student account.
    """
    if not request.user.is_authenticated:
        return redirect("login")

    if not _is_student(request):
        if _is_teacher(request):
            role_label = "teacher"
            redirect_target = "teacher_dashboard"
        elif _is_admin(request):
            role_label = "an administrator"
            redirect_target = "admin_dashboard"
        else:
            role_label = "a non-student"
            redirect_target = "login"

        messages.error(
            request,
            f"Access denied. You are currently logged in as {role_label} ({request.user.username}). "
            f"Please log in with a student account to {action}."
        )
        return redirect(redirect_target)

    return None


# =========================================================
# HOME
# =========================================================

def home(request):
    return render(request, "home/home.html")

# =========================================================
# LOGIN
# =========================================================
@csrf_exempt
def login(request):

    if request.method == "POST":

        role = request.POST.get(
            "role",
            "student"
        ).lower().strip()

        username = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

        if not username or not password:

            messages.error(
                request,
                "Please enter username/email and password."
            )

            return render(
                request,
                "home/login.html",
                {"role": role}
            )

        # -------------------------------------------------
        # AUTHENTICATE USING USERNAME
        # -------------------------------------------------

        user = authenticate(
            request,
            username=username,
            password=password
        )

        # -------------------------------------------------
        # AUTHENTICATE USING EMAIL
        # -------------------------------------------------

        if user is None:

            try:

                users_by_email = User.objects.filter(
                    email__iexact=username
                )

                if users_by_email.count() == 1:

                    email_user = users_by_email.first()

                    user = authenticate(
                        request,
                        username=email_user.username,
                        password=password
                    )

            except Exception:

                user = None

        # -------------------------------------------------
        # INVALID LOGIN
        # -------------------------------------------------

        if user is None:

            messages.error(
                request,
                "Invalid username/email or password."
            )

            return render(
                request,
                "home/login.html",
                {"role": role}
            )

        # =================================================
        # DETERMINE ACTUAL ACCOUNT ROLE
        # =================================================

        actual_role = None

        # -------------------------------------------------
        # ADMIN
        # -------------------------------------------------

        if user.username.lower() == "user":

            actual_role = "admin"

        # -------------------------------------------------
        # TEACHER
        # -------------------------------------------------

        if actual_role is None:

            try:

                teacher_requests = firebase_get(
                    "teacher_requests"
                )

                if teacher_requests:

                    for teacher_id, teacher_data in teacher_requests.items():

                        if not isinstance(
                            teacher_data,
                            dict
                        ):
                            continue

                        status = str(
                            teacher_data.get(
                                "status",
                                ""
                            )
                        ).strip().lower()

                        # Teacher must be approved
                        if status != "approved":
                            continue

                        # Firebase key is the Teacher ID
                        firebase_teacher_id = str(
                            teacher_id
                        ).strip().lower()

                        # Django username is also Teacher ID
                        django_teacher_id = str(
                            user.username
                        ).strip().lower()

                        if firebase_teacher_id == django_teacher_id:

                            actual_role = "teacher"
                            break

            except Exception:

                actual_role = None

        # -------------------------------------------------
        # STUDENT
        # -------------------------------------------------

        if actual_role is None:

            try:

                student_data = firebase_get(
                    f"users/{user.username}"
                )

                if isinstance(
                    student_data,
                    dict
                ):

                    firebase_role = str(
                        student_data.get(
                            "role",
                            ""
                        )
                    ).strip().lower()

                    if firebase_role == "student":

                        actual_role = "student"

            except Exception:

                actual_role = None

        # =================================================
        # ROLE COULD NOT BE FOUND
        # =================================================

        if actual_role is None:

            messages.error(
                request,
                "Unable to verify your account role. Please contact the administrator."
            )

            return render(
                request,
                "home/login.html",
                {"role": role}
            )

        # =================================================
        # CHECK SELECTED ROLE
        # =================================================

        if role != actual_role:

            role_names = {
                "student": "Student",
                "teacher": "Teacher",
                "admin": "Admin"
            }

            actual_role_name = role_names.get(
                actual_role,
                actual_role.capitalize()
            )

            messages.error(
                request,
                f"This account belongs to the {actual_role_name} role. "
                f"Please select {actual_role_name} Login."
            )

            return render(
                request,
                "home/login.html",
                {"role": role}
            )

        # =================================================
        # LOGIN SUCCESS
        # =================================================

        auth_login(
            request,
            user
        )

        # Store VERIFIED role
        request.session["role"] = actual_role

        if actual_role == "student":
            request.session["student_id"] = user.username
            if isinstance(student_data, dict):
                fb_sid = (
                    student_data.get("student_id")
                    or student_data.get("register_number")
                    or student_data.get("register_no")
                )
                if fb_sid:
                    request.session["student_id"] = str(fb_sid).strip()

        # =================================================
        # REDIRECT
        # =================================================

        if actual_role == "teacher":

            return redirect(
                "teacher_dashboard"
            )

        elif actual_role == "admin":

            return redirect(
                "admin_dashboard"
            )

        elif actual_role == "student":

            return redirect(
                "student_dashboard"
            )

        # Safety fallback

        logout(request)

        messages.error(
            request,
            "Unable to determine the correct dashboard."
        )

        return render(
            request,
            "home/login.html",
            {"role": role}
        )

    # =================================================
    # GET REQUEST
    # =================================================

    role = request.GET.get(
        "role",
        "student"
    ).strip().lower()

    if role not in ["student", "teacher", "admin"]:
        role = "student"

    return render(
        request,
        "home/login.html",
        {"role": role}
    )
# =========================================================
# REGISTER
# =========================================================

@csrf_exempt
def register(request):

    # -----------------------------------------------------
    # GET ROLE
    # -----------------------------------------------------

    role = request.GET.get(
        "role",
        "student"
    ).strip().lower()

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    if request.method == "POST":

        role = request.POST.get(
            "role",
            "student"
        ).strip().lower()

        full_name = request.POST.get(
            "fullName",
            ""
        ).strip()

        email = request.POST.get(
            "regEmail",
            ""
        ).strip().lower()

        password = request.POST.get(
            "password",
            ""
        ).strip()

        confirm_password = request.POST.get(
            "confirmPassword",
            ""
        ).strip()

        student_id = request.POST.get(
            "studentId",
            ""
        ).strip()

        employee_id = request.POST.get(
            "employeeId",
            ""
        ).strip()

        department = request.POST.get(
            "department",
            ""
        ).strip()

        # =================================================
        # ROLE VALIDATION
        # =================================================

        if role not in ["student", "teacher"]:

            return render(
                request,
                "home/register.html",
                {
                    "role": "student",
                    "error": "Invalid registration role."
                }
            )

        # =================================================
        # REQUIRED FIELD VALIDATION
        # =================================================

        if not full_name:

            return render(
                request,
                "home/register.html",
                {
                    "role": role,
                    "error": "Please enter your full name."
                }
            )

        if not email:

            return render(
                request,
                "home/register.html",
                {
                    "role": role,
                    "error": "Please enter your email address."
                }
            )

        if not password:

            return render(
                request,
                "home/register.html",
                {
                    "role": role,
                    "error": "Please enter a password."
                }
            )

        if not confirm_password:
            return render(
                request,
                "home/register.html",
                {
                    "role": role,
                    "error": "Please confirm your password."
                }
            )

        if password != confirm_password:
            return render(
            request,
                    "home/register.html",
            {
                "role": role,
                "error": "Passwords do not match."
            }
    )

        # =================================================
        # FULL NAME VALIDATION
        # =================================================

        if not re.fullmatch(
            r"[A-Za-z]+(?:[ '-][A-Za-z]+)*",
            full_name
        ):

            return render(
                request,
                "home/register.html",
                {
                    "role": role,
                    "error":
                    "Full Name must contain letters and spaces only."
                }
            )

        # =================================================
        # FULL NAME LENGTH
        # =================================================

        if len(full_name) < 2 or len(full_name) > 100:

            return render(
                request,
                "home/register.html",
                {
                    "role": role,
                    "error":
                    "Full Name must be between 2 and 100 characters."
                }
            )

        # =================================================
        # EMAIL VALIDATION
        # =================================================

        try:

            validate_email(email)

        except ValidationError:

            return render(
                request,
                "home/register.html",
                {
                    "role": role,
                    "error":
                    "Please enter a valid email address."
                }
            )

        # =================================================
        # PASSWORD VALIDATION
        # =================================================

        if len(password) < 8:

            return render(
                request,
                "home/register.html",
                {
                    "role": role,
                    "error":
                    "Password must contain at least 8 characters."
                }
            )

        # =================================================
        # TEACHER REGISTRATION
        # =================================================

        if role == "teacher":

            # -------------------------------------------------
            # REQUIRED TEACHER FIELDS
            # -------------------------------------------------

            if not employee_id:

                return render(
                    request,
                    "home/register.html",
                    {
                        "role": role,
                        "error":
                        "Please enter your Teacher ID."
                    }
                )

            if not department:

                return render(
                    request,
                    "home/register.html",
                    {
                        "role": role,
                        "error":
                        "Please enter your Department."
                    }
                )

            # -------------------------------------------------
            # TEACHER ID VALIDATION
            # -------------------------------------------------

            if not re.fullmatch(
                r"[A-Za-z0-9_-]+",
                employee_id
            ):

                return render(
                    request,
                    "home/register.html",
                    {
                        "role": role,
                        "error":
                        "Teacher ID can contain only letters, numbers, hyphens and underscores."
                    }
                )

            # -------------------------------------------------
            # DEPARTMENT VALIDATION
            # -------------------------------------------------

            if not re.fullmatch(
                r"[A-Za-z]+(?:[ &'-][A-Za-z]+)*",
                department
            ):

                return render(
                    request,
                    "home/register.html",
                    {
                        "role": role,
                        "error":
                        "Please enter a valid department name."
                    }
                )

            # -------------------------------------------------
            # CHECK EXISTING TEACHER REQUEST
            # -------------------------------------------------

            existing_teacher = firebase_get(
                f"teacher_requests/{employee_id}"
            )

            if existing_teacher:

                return render(
                    request,
                    "home/register.html",
                    {
                        "role": role,
                        "error":
                        "This Teacher ID already has a registration request."
                    }
                )

            # -------------------------------------------------
            # CHECK TEACHER EMAIL IN FIREBASE
            # -------------------------------------------------

            all_teacher_requests = firebase_get(
                "teacher_requests"
            )

            if all_teacher_requests:

                for teacher in all_teacher_requests.values():

                    if not isinstance(teacher, dict):
                        continue

                    existing_email = teacher.get(
                        "email",
                        ""
                    ).strip().lower()

                    if existing_email == email:

                        return render(
                            request,
                            "home/register.html",
                            {
                                "role": role,
                                "error":
                                "A teacher request with this email already exists."
                            }
                        )

            # -------------------------------------------------
            # CHECK DJANGO EMAIL
            # -------------------------------------------------

            if User.objects.filter(
                email__iexact=email
            ).exists():

                return render(
                    request,
                    "home/register.html",
                    {
                        "role": role,
                        "error":
                        "An account with this email already exists."
                    }
                )

            # -------------------------------------------------
            # SAVE TEACHER REQUEST
            # Password is NOT stored in Firebase — admin sets
            # the teacher's password when approving the request.
            # -------------------------------------------------

            teacher_data = {
                "teacher_id": employee_id,
                "name": full_name,
                "email": email,
                "department": department,
                "password": "",   # never store plaintext — cleared at point of entry
                "status": "Pending",
                "registered_at": datetime.now().isoformat()
            }

            firebase_set(
                f"teacher_requests/{employee_id}",
                teacher_data
            )

            messages.success(
                request,
                "Teacher registration submitted for admin approval."
            )
            return redirect("login")

        # =================================================
        # STUDENT REGISTRATION
        # =================================================

        if role == "student":

            # -------------------------------------------------
            # STUDENT ID REQUIRED
            # -------------------------------------------------

            if not student_id:

                return render(
                    request,
                    "home/register.html",
                    {
                        "role": role,
                        "error":
                        "Please enter your Student ID."
                    }
                )

            # -------------------------------------------------
            # STUDENT ID VALIDATION
            # -------------------------------------------------

            if not re.fullmatch(
                r"[A-Za-z0-9_-]+",
                student_id
            ):

                return render(
                    request,
                    "home/register.html",
                    {
                        "role": role,
                        "error":
                        "Student ID can contain only letters, numbers, hyphens and underscores."
                    }
                )

            # -------------------------------------------------
            # CHECK FIREBASE
            # -------------------------------------------------

            existing_student = firebase_get(
                f"users/{student_id}"
            )

            if existing_student:

                return render(
                    request,
                    "home/register.html",
                    {
                        "role": role,
                        "error":
                        "This Student ID is already registered."
                    }
                )

            # -------------------------------------------------
            # CHECK DJANGO USERNAME
            # -------------------------------------------------

            if User.objects.filter(
                username=student_id
            ).exists():

                return render(
                    request,
                    "home/register.html",
                    {
                        "role": role,
                        "error":
                        "This Student ID is already registered."
                    }
                )

            # -------------------------------------------------
            # CHECK EMAIL
            # -------------------------------------------------

            if User.objects.filter(
                email__iexact=email
            ).exists():

                return render(
                    request,
                    "home/register.html",
                    {
                        "role": role,
                        "error":
                        "An account with this email already exists."
                    }
                )

            # -------------------------------------------------
            # CREATE DJANGO ACCOUNT
            # -------------------------------------------------

            User.objects.create_user(

                username=student_id,

                email=email,

                password=password,

                first_name=full_name

            )

            # -------------------------------------------------
            # SAVE STUDENT TO FIREBASE
            # -------------------------------------------------

            student_data = {

                "full_name": full_name,

                "student_id": student_id,

                "email": email,

                "role": "student",

                "created_at":
                datetime.now().isoformat()

            }

            firebase_set(
                f"users/{student_id}",
                student_data
            )

            messages.success(
                request,
                "Student account created successfully! You can now sign in."
            )
            return redirect("login")

    # =========================================================
    # SHOW REGISTRATION PAGE
    # =========================================================

    return render(
        request,
        "home/register.html",
        {
            "role": role
        }
    )


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@login_required(login_url="login")
def student_dashboard(request):

    # ── Role guard: only authenticated students can access student dashboard ─
    guard = _require_student(request, action="access the student dashboard")
    if guard is not None:
        return guard
    # ─────────────────────────────────────────────────────────────────────────

    student_id = request.user.username

    student = firebase_get(
        f"users/{student_id}"
    )

    device = firebase_get(
        f"devices/{student_id}"
    )

    if not device:
        device = None

    all_attendance = firebase_get(
        "attendance"
    )

    attendance_records = []

    if all_attendance:

        for key, record in all_attendance.items():

            if not isinstance(record, dict):
                continue

            if record.get("student_id") == student_id:

                record["id"] = key
                attendance_records.append(record)

    total_sessions = len(attendance_records)

    present_sessions = len(
        [
            a for a in attendance_records
            if a.get("status") == "Present"
        ]
    )

    if total_sessions > 0:

        overall_attendance_percentage = int(
            (present_sessions / total_sessions) * 100
        )

    else:

        overall_attendance_percentage = None

    latest_attendance = None

    if attendance_records:

        attendance_records.sort(
            key=lambda x: (
                x.get("date", ""),
                x.get("time", "")
            ),
            reverse=True
        )

        latest_attendance = attendance_records[0]

    # ---------------------------------------------------------
    # ACTIVE SESSION CHECK
    # Query Firebase directly for any currently active session.
    # Students do not have a server-side monitoring_active flag —
    # the teacher controls sessions, so we check Firebase truth.
    # ---------------------------------------------------------
    monitoring_active = False
    active_session_id = ""
    active_class = "No active session"
    session_time = "Not started"

    all_sessions = firebase_get("classroom_sessions")
    if all_sessions and isinstance(all_sessions, dict):
        newest_sid = None
        newest_created = ""
        for sid, sess in all_sessions.items():
            if isinstance(sess, dict) and sess.get("active") is True:
                created = str(sess.get("created_at", ""))
                if newest_sid is None or created > newest_created:
                    newest_sid = sid
                    newest_created = created
                    active_class = sess.get("classroom", "Classroom")
                    session_time = sess.get("session_time", "")
        if newest_sid:
            monitoring_active = True
            active_session_id = newest_sid

    # ---------------------------------------------------------
    # CURRENT SESSION ATTENDANCE CHECK
    # Determine whether the student has scanned the QR code
    # for the currently active session.
    # ---------------------------------------------------------
    current_session_attendance = None
    current_session_present = False

    if monitoring_active and active_session_id:
        for record in attendance_records:
            rec_sid = str(record.get("session_id", "")).strip()
            if rec_sid == str(active_session_id).strip() and record.get("status") == "Present":
                current_session_attendance = record
                current_session_present = True
                break

    if monitoring_active:
        if current_session_present:
            current_attendance_status = "Present"
            attendance_percentage = 100
        else:
            current_attendance_status = "Not Marked"
            # Do not display 100% as the current session attendance
            attendance_percentage = None
    else:
        current_attendance_status = "No Active Session"
        attendance_percentage = overall_attendance_percentage

    recent_activities = []

    # ---------------------------------------------------------
    # FOCUS SCORE
    # Collect phone-usage records for this student across
    # all sessions they have attended.
    # Only computed from real Firebase data — never invented.
    # ---------------------------------------------------------
    focus_score = None
    focus_level = "No Data"
    edu_seconds = 0.0
    non_edu_seconds = 0.0
    total_usage_records = 0

    # Gather session IDs from the student's attendance records.
    attended_session_ids = set()
    for rec in attendance_records:
        sid = rec.get("session_id", "")
        if sid:
            attended_session_ids.add(sid)

    if attended_session_ids:
        for sid in attended_session_ids:
            session_usage = firebase_get(
                f"phone_usage/{sid}"
            )
            if not session_usage or not isinstance(session_usage, dict):
                continue

            for push_key, usage in session_usage.items():
                if not isinstance(usage, dict):
                    continue

                # Only count this student's own usage
                if usage.get("student_id") != student_id:
                    continue

                total_usage_records += 1

                try:
                    duration = float(usage.get("duration", 0))
                except (TypeError, ValueError):
                    duration = 0.0

                if duration < 0:
                    duration = 0.0

                category = str(
                    usage.get("category", "")
                ).strip().lower()

                if category == "educational":
                    edu_seconds += duration
                elif category in (
                    "non-educational",
                    "non educational",
                    "noneducational",
                ):
                    non_edu_seconds += duration

    # Compute score only when real usage data exists
    if total_usage_records > 0:
        total_active = edu_seconds + non_edu_seconds
        if total_active > 0:
            raw = (edu_seconds / total_active) * 100
        else:
            # Only neutral/unknown usage recorded → treat as focused
            raw = 100.0

        focus_score = round(max(0.0, min(100.0, raw)), 1)

        if focus_score >= 80:
            focus_level = "Highly Focused"
        elif focus_score >= 60:
            focus_level = "Moderately Focused"
        else:
            focus_level = "Low Focus"

    if latest_attendance:

        recent_activities.append({

            "icon": "📷",

            "title":
            "Marked Attendance via QR",

            "description":
            f"Classroom: {latest_attendance.get('classroom', 'Classroom')}",

            "time":
            f"{latest_attendance.get('date', '')} "
            f"{latest_attendance.get('time', '')}"

        })

    if device:

        recent_activities.append({

            "icon": "📱",

            "title":
            "Registered Mobile Device",

            "description":
            f"Device: {device.get('device_name', 'Phone')}",

            "time": "Active"

        })

    if not recent_activities:

        recent_activities.append({

            "icon": "👋",

            "title":
            "Welcome to FocusFrame",

            "description":
            "Scan session QR code to mark attendance.",

            "time": "Just now"

        })

    context = {

        "student": student,

        # When a session is active and student has not scanned,
        # attendance_percentage is None (preventing 100% display).
        "attendance_percentage":
        attendance_percentage,

        # Overall historical attendance percentage is preserved.
        "overall_attendance_percentage":
        overall_attendance_percentage,

        "total_sessions":
        total_sessions,

        "present_sessions":
        present_sessions,

        "latest_attendance":
        latest_attendance,

        "current_session_attendance":
        current_session_attendance,

        "current_session_present":
        current_session_present,

        "current_attendance_status":
        current_attendance_status,

        "attendance_status":
        current_attendance_status,

        "active_session_id":
        active_session_id,

        "user_device":
        device,

        "monitoring_active":
        monitoring_active,

        "active_class":
        active_class,

        "session_time":
        session_time,

        "recent_activities":
        recent_activities,

        # Focus score computed from real phone-usage data.
        # None when no usage records exist for this student.
        "focus_score":
        focus_score,

        "focus_level":
        focus_level,

        "edu_seconds":
        edu_seconds,

        "non_edu_seconds":
        non_edu_seconds,

        "total_usage_records":
        total_usage_records,

        "active_view":
        request.GET.get("view", "all"),

    }

    return render(
        request,
        "home/student_dashboard.html",
        context
    )

# =========================================================
# TEACHER DASHBOARD
# =========================================================

@login_required(login_url="login")
def teacher_dashboard(request):

    # ---------------------------------------------------------
    # TEACHER-ONLY GUARD
    # ---------------------------------------------------------
    guard = _require_teacher(request)
    if guard is not None:
        return guard

    # ---------------------------------------------------------
    # LOAD STUDENTS
    # ---------------------------------------------------------
    users_data = firebase_get("users")

    students = []

    if users_data:
        for key, student in users_data.items():

            if not isinstance(student, dict):
                continue

            if student.get("role") != "student":
                continue

            student["student_id"] = key
            student["device_registered"] = False
            student["device_name"] = ""

            students.append(student)

    # ---------------------------------------------------------
    # LOAD REGISTERED DEVICES
    # ---------------------------------------------------------
    devices_data = firebase_get("devices")

    devices = []

    if devices_data:
        for key, device in devices_data.items():

            if not isinstance(device, dict):
                continue

            device["register_number"] = device.get(
                "register_number",
                key
            )

            devices.append(device)

    # Match devices with students
    for student in students:

        student_id = str(
            student.get("student_id", "")
        ).strip()

        for device in devices:

            register_number = str(
                device.get("register_number", "")
            ).strip()

            if student_id == register_number:

                student["device_registered"] = True

                student["device_name"] = device.get(
                    "device_name",
                    "Registered Device"
                )

                break

    # ---------------------------------------------------------
    # LOAD ATTENDANCE
    # ---------------------------------------------------------
    attendance_data = firebase_get("attendance")

    attendance_records = []

    if attendance_data:

        for key, attendance in attendance_data.items():

            if not isinstance(attendance, dict):
                continue

            attendance["id"] = key

            attendance_records.append(attendance)

    # ---------------------------------------------------------
    # MONITORING SESSION INFORMATION
    # Primary source: Django session (set by start/stop_monitoring).
    # Fallback: scan Firebase for this teacher's active session
    # in case the server restarted and cleared the session.
    # ---------------------------------------------------------
    monitoring_active = request.session.get("monitoring_active", False)
    active_class      = request.session.get("active_class", "")
    session_time      = request.session.get("session_time", "Not started")
    session_id        = request.session.get("session_id", "")

    # Verify/recover from Firebase if session key is missing
    if not session_id or not monitoring_active:
        all_sessions = firebase_get("classroom_sessions")
        if all_sessions and isinstance(all_sessions, dict):
            newest_sid = None
            newest_created = ""
            newest_class = ""
            newest_time = ""
            for fb_sid, sess in all_sessions.items():
                if not isinstance(sess, dict):
                    continue
                if (
                    sess.get("active") is True
                    and sess.get("teacher_id") == request.user.username
                ):
                    created = str(sess.get("created_at", ""))
                    if newest_sid is None or created > newest_created:
                        newest_sid = fb_sid
                        newest_created = created
                        newest_class = sess.get("classroom", "")
                        newest_time = sess.get("session_time", "")
            if newest_sid:
                monitoring_active = True
                session_id = newest_sid
                active_class = newest_class
                session_time = newest_time
                # Restore to Django session so subsequent requests are fast
                request.session["monitoring_active"] = True
                request.session["session_id"] = newest_sid
                request.session["active_class"] = active_class
                request.session["session_time"] = session_time
                request.session.modified = True

    # ---------------------------------------------------------
    # SPRINT 3 - T7
    # KEEP THE LAST COMPLETED SESSION FOR ALERT HISTORY
    # ---------------------------------------------------------
    history_session_id = request.session.get(
        "last_session_id",
        ""
    )

    history_session_time = request.session.get(
        "last_session_time",
        "Not available"
    )

    history_class = request.session.get(
        "last_active_class",
        "No previous session"
    )

    # ---------------------------------------------------------
    # LOAD PHONE USAGE FOR CURRENT SESSION
    # NOTE: Handled by the unified block below (lines ~1501+)
    #       which correctly selects active vs history session.
    # ---------------------------------------------------------

    # ---------------------------------------------------------
    # LOAD PHONE USAGE FOR ACTIVE OR LAST COMPLETED SESSION
    # ---------------------------------------------------------
    phone_usage_records = []

    if monitoring_active and session_id:
        usage_session_id = session_id
    elif not monitoring_active and history_session_id:
        usage_session_id = history_session_id
    else:
        usage_session_id = ""

    if usage_session_id:
        phone_usage_data = firebase_get(
            f"phone_usage/{usage_session_id}"
        )

        if phone_usage_data:
            # Pre-load existing active session alerts to deduplicate without querying Firebase in a loop
            existing_alerts = {}
            seen_alert_sources = set()
            seen_alert_fps = set()
            if monitoring_active and session_id:
                existing_alerts = firebase_get(f"alerts/{session_id}")
                if isinstance(existing_alerts, dict):
                    for e_alert in existing_alerts.values():
                        if isinstance(e_alert, dict):
                            src_id = e_alert.get("source_usage_id")
                            if src_id:
                                seen_alert_sources.add(src_id)
                            fp = f"{e_alert.get('student_id')}_{e_alert.get('app_name')}_{e_alert.get('timestamp')}_{e_alert.get('duration')}"
                            seen_alert_fps.add(fp)

            for key, usage in phone_usage_data.items():
                if not isinstance(usage, dict):
                    continue

                # Skip non-event metadata dictionaries (such as focus_summary) or records missing app_name
                if key == "focus_summary" or not usage.get("app_name"):
                    continue

                # Copy the record so we don't modify Firebase data
                usage = usage.copy()
                usage["id"] = key

                # Fallback ML prediction if not already computed/stored
                if not usage.get("ml_label"):
                    try:
                        from .ai_model import predict_focus_with_best_model
                        category = str(usage.get("category", "")).strip().lower()
                        is_non_edu = category in (
                            "non-educational", "non educational",
                            "noneducational", "gaming", "shopping",
                            "social media", "entertainment"
                        )
                        dur = float(usage.get("duration", 0))
                        ml_res = predict_focus_with_best_model(
                            duration_seconds=dur,
                            non_educational=is_non_edu
                        )
                        usage["ml_prediction"] = ml_res.get("prediction")
                        usage["ml_label"] = ml_res.get("label", "")
                        usage["ml_is_demo"] = ml_res.get("is_demo_model", True)
                    except Exception:
                        pass

                phone_usage_records.append(usage)

                # Create/check alerts ONLY for the active session.
                # Historical records must not create duplicate alerts.
                if monitoring_active and session_id:
                    alert_condition = detect_alert_condition(
                        usage
                    )

                    if alert_condition is not None:
                        identified_alert = identify_alert_student(
                            alert_condition,
                            users_data=users_data,
                            devices_data=devices_data
                        )

                        if identified_alert is not None:
                            event_fp = f"{identified_alert.get('student_id')}_{identified_alert.get('app_name')}_{identified_alert.get('timestamp')}_{identified_alert.get('duration')}"

                            duplicate_alert = (key in seen_alert_sources or event_fp in seen_alert_fps)

                            if not duplicate_alert:
                                identified_alert["severity"] = (
                                    calculate_alert_severity(
                                        identified_alert
                                    )
                                )
                                identified_alert["source_usage_id"] = key

                                store_alert(
                                    session_id,
                                    identified_alert
                                )
                                seen_alert_sources.add(key)
                                seen_alert_fps.add(event_fp)




    # =========================================================
    # LOAD ALERT RECORDS
    # =========================================================

    alert_records = []
    alert_history_records = []

    # Load alerts for the currently active session.
    if monitoring_active and session_id:
        active_alert_data = firebase_get(
            f"alerts/{session_id}"
        )

        if active_alert_data:
            seen_alert_events = set()
            for key, alert in active_alert_data.items():
                if not isinstance(alert, dict):
                    continue

                # Stable event identifier to deduplicate alerts for the same usage event
                source_id = alert.get("source_usage_id")
                event_fp = source_id or f"{alert.get('student_id')}_{alert.get('app_name')}_{alert.get('timestamp')}_{alert.get('duration')}"
                if event_fp in seen_alert_events:
                    continue
                seen_alert_events.add(event_fp)

                alert = alert.copy()
                alert["id"] = key

                if not alert.get("severity"):
                    alert["severity"] = calculate_alert_severity(
                        alert
                    )

                alert_records.append(alert)

    # After monitoring stops, load alerts from the
    # last completed session.
    elif not monitoring_active and history_session_id:
        history_data = firebase_get(
            f"alerts/{history_session_id}"
        )

        if history_data:
            seen_history_events = set()
            for key, alert in history_data.items():
                if not isinstance(alert, dict):
                    continue

                source_id = alert.get("source_usage_id")
                event_fp = source_id or f"{alert.get('student_id')}_{alert.get('app_name')}_{alert.get('timestamp')}_{alert.get('duration')}"
                if event_fp in seen_history_events:
                    continue
                seen_history_events.add(event_fp)

                alert = alert.copy()
                alert["id"] = key

                if not alert.get("severity"):
                    alert["severity"] = calculate_alert_severity(
                        alert
                    )

                alert_history_records.append(alert)

    # ---------------------------------------------------------
    # CALCULATE DEVICE COUNTS
    # ---------------------------------------------------------
    total_students = len(students)

    students_with_devices = 0

    for student in students:

        if student.get("device_registered"):
            students_with_devices += 1

    connected_devices = students_with_devices

    students_without_devices = (
        total_students - students_with_devices
    )

    # ---------------------------------------------------------
    # ATTENDANCE STUDENT IDs
    # ---------------------------------------------------------
    present_student_ids = set()
    enrolled_student_ids = {
        str(s.get("student_id", "")).strip()
        for s in students
        if s.get("student_id")
    }

    for attendance in attendance_records:

        if attendance.get("status") != "Present":
            continue

        # When monitoring is active, only count attendance for the current active session
        if monitoring_active and session_id:
            if attendance.get("session_id") != session_id:
                continue
        elif history_session_id:
            # If monitoring stopped, scope to the last completed session if available
            if attendance.get("session_id") != history_session_id:
                continue
        else:
            continue

        student_id = str(
            attendance.get("student_id", "")
        ).strip()

        # Only count registered students (excludes teacher scans and unregistered test IDs)
        if student_id and student_id in enrolled_student_ids:
            present_student_ids.add(student_id)

    present_students_count = len(
        present_student_ids
    )

    # ---------------------------------------------------------
    # CREATE PER-STUDENT MONITORING DATA
    # ---------------------------------------------------------
    student_monitoring = []

    for student in students:

        student_id = str(
            student.get("student_id", "")
        ).strip()

        student_name = student.get(
            "full_name",
            "Unknown Student"
        )


        email = student.get(
            "email",
            ""
        )

        # -----------------------------------------------------
        # ATTENDANCE
        # -----------------------------------------------------
        is_present = (
            student_id in present_student_ids
        )

        # -----------------------------------------------------
        # GET THIS STUDENT'S PHONE USAGE
        # -----------------------------------------------------
        student_usage = []

        for usage in phone_usage_records:

            usage_student_id = str(
                usage.get("student_id", "")
            ).strip()

            if usage_student_id == student_id:

                student_usage.append(usage)

        # -----------------------------------------------------
        # CALCULATE USAGE DURATIONS
        # -----------------------------------------------------
        total_duration = 0.0
        educational_duration = 0.0
        non_educational_duration = 0.0
        unknown_duration = 0.0

        for usage in student_usage:

            try:
                duration = float(
                    usage.get("duration", 0)
                )
            except (TypeError, ValueError):
                duration = 0.0

            if duration < 0:
                duration = 0.0

            total_duration += duration

            category = str(
                usage.get("category", "")
            ).strip().lower()

            if category == "educational":

                educational_duration += duration

            elif category in [
                "non-educational",
                "non educational",
                "noneducational"
            ]:

                non_educational_duration += duration

            else:

                unknown_duration += duration

        # -----------------------------------------------------
        # CALCULATE INDIVIDUAL FOCUS SCORE
        # -----------------------------------------------------
        if total_duration > 0:

            focus_score = (
                educational_duration
                / total_duration
            ) * 100

            focus_score = round(
                max(0.0, min(100.0, focus_score)),
                1
            )

            if focus_score >= 80:

                focus_level = "Highly Focused"

            elif focus_score >= 60:

                focus_level = "Moderately Focused"

            else:

                focus_level = "Low Focus"

        else:

            focus_score = None
            focus_level = "No Data"

        # -----------------------------------------------------
        # STUDENT MONITORING OBJECT
        # -----------------------------------------------------
        student_monitoring.append({

            "student_id": student_id,

            "student_name": student_name,

            "email": email,

            "device_registered":
                student.get(
                    "device_registered",
                    False
                ),

            "device_name":
                student.get(
                    "device_name",
                    ""
                ),

            "attendance":
                "Present"
                if is_present
                else "Absent",

            "is_present":
                is_present,

            "usage_records":
                student_usage,

            "usage_count":
                len(student_usage),

            "total_duration":
                total_duration,

            "educational_duration":
                educational_duration,

            "non_educational_duration":
                non_educational_duration,

            "unknown_duration":
                unknown_duration,

            "focus_score":
                focus_score,

            "focus_level":
                focus_level
        })

    # ---------------------------------------------------------
    # CLASSROOM MONITORING STATISTICS
    # ---------------------------------------------------------
    if monitoring_active:

        present_students = (
            present_students_count
        )

        phone_usage = len(
            phone_usage_records
        )

        # Students with a meaningful focus score
        focused_ids = set()

        for student in student_monitoring:

            score = student.get(
                "focus_score"
            )

            if score is not None and score >= 60:

                focused_ids.add(
                    student.get("student_id")
                )

        focused_students = len(
            focused_ids
        )

    else:

        focused_students = "—"

        phone_usage = "—"

        present_students = "—"

    # ---------------------------------------------------------
    # QR CODE
    # Generate a base64-encoded QR image whose payload is
    # the live session_id. The template embeds it as a
    # data-URI so no external CDN is needed.
    # When monitoring is inactive, no QR image is needed.
    # ---------------------------------------------------------
    qr_image_b64 = ""

    if monitoring_active and session_id:
        try:
            qr_image_b64 = generate_qr_b64(session_id)
        except Exception:
            qr_image_b64 = ""

    # ---------------------------------------------------------
    # CONTEXT
    # ---------------------------------------------------------
    context = {

        "students":
            students,

        "devices":
            devices,

        "attendance_records":
            attendance_records,

        "phone_usage_records":
            phone_usage_records,
        "alert_records":
            alert_records,

        # Sprint 3 - T7
        "alert_history_records":
            alert_history_records,

        "history_session_id":
            history_session_id,

        "history_session_time":
            history_session_time,

        "history_class":
            history_class,

        # NEW:
        # Per-student attendance,
        # phone usage and focus score
        "student_monitoring":
            student_monitoring,

        "session_id":
            session_id,

        "total_students":
            total_students,

        "connected_devices":
            connected_devices,

        "students_with_devices":
            students_with_devices,

        "students_without_devices":
            students_without_devices,

        "monitoring_active":
            monitoring_active,

        "active_class":
            active_class,

        
        "session_time":
            session_time,

        "focused_students":
            focused_students,

        "phone_usage":
            phone_usage,

        "present_students":
            present_students,

        "qr_image_b64":
            qr_image_b64,

        "active_view":
            request.GET.get("view", "all")
    }

    # RENDER TEACHER DASHBOARD
    # ---------------------------------------------------------
    return render(
        request,
        "home/teacher_dashboard.html",
        context
    )


# =========================================================
# START MONITORING
# =========================================================

@csrf_exempt
@login_required(login_url="login")
def start_monitoring(request):

    # ── Role guard ──────────────────────────────────────────
    guard = _require_teacher(request)
    if guard:
        return guard
    # ────────────────────────────────────────────────────────

    print("[START MONITORING] View called")


    if request.method != "POST":
        return redirect("teacher_dashboard")

    # Read classroom name submitted from the form; fall back to default
    classroom = request.POST.get("classroom_name", "").strip() or "CS-402 Mobile Computing"

    session_time = datetime.now().strftime(
        "%d %b %Y, %I:%M %p"
    )

    session_data = {

        "teacher_id": request.user.username,

        "teacher_name": request.user.first_name,

        "classroom": classroom,

        "session_time": session_time,

        # qr_code field updated below once we have the session_id
        "qr_code": "",

        "active": True,

        "created_at": datetime.now().isoformat()

    }

    # Close any existing active sessions for this teacher to prevent session collision
    existing_sessions = firebase_get("classroom_sessions")
    if existing_sessions and isinstance(existing_sessions, dict):
        for old_sid, old_sess in existing_sessions.items():
            if (
                isinstance(old_sess, dict)
                and old_sess.get("active") is True
                and old_sess.get("teacher_id") == request.user.username
            ):
                firebase_update(
                    f"classroom_sessions/{old_sid}",
                    {"active": False, "stopped_at": datetime.now().isoformat()}
                )

    # Create Firebase classroom session
    new_session = firebase_push(
        "classroom_sessions",
        session_data
    )

    # Get generated Firebase session ID with fallback
    session_id = getattr(new_session, "key", None)
    if not session_id:
        import uuid
        session_id = f"SESS_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        session_data["qr_code"] = session_id
        firebase_set(f"classroom_sessions/{session_id}", session_data)
    else:
        # Store the real session_id as the QR payload so that
        # scan_qr() can validate it against Firebase.
        firebase_update(
            f"classroom_sessions/{session_id}",
            {"qr_code": session_id}
        )

    # Create empty phone usage node
    firebase_set(
        f"phone_usage/{session_id}",
        {}
    )

    # Save monitoring information
    request.session["monitoring_active"] = True
    request.session["active_class"] = classroom
    request.session["session_time"] = session_time
    request.session["session_id"] = session_id
    # Reset previous session history so it does not blend into the new active session
    request.session.pop("last_session_id", None)
    request.session.pop("last_session_time", None)
    request.session.pop("last_active_class", None)
    request.session.modified = True

    messages.success(
        request,
        "Classroom monitoring started successfully."
    )

    return redirect("teacher_dashboard")


# =========================================================
# STOP MONITORING
# =========================================================

@csrf_exempt
@login_required(login_url="login")
def stop_monitoring(request):

    # ── Role guard ──────────────────────────────────────────
    guard = _require_teacher(request)
    if guard:
        return guard
    # ────────────────────────────────────────────────────────

    if request.method != "POST":
        return redirect("teacher_dashboard")

    session_id = request.session.get("session_id")
    teacher_id = request.user.username

    # ---------------------------------------------------------
    # STOP ALL ACTIVE SESSIONS CREATED BY THIS TEACHER
    # ---------------------------------------------------------

    classroom_sessions = firebase_get("classroom_sessions")
    stopped_session_id = session_id

    if classroom_sessions and isinstance(classroom_sessions, dict):

        for firebase_session_id, session_data in classroom_sessions.items():

            if not isinstance(session_data, dict):
                continue

            # Only stop sessions belonging to the logged-in teacher
            if session_data.get("teacher_id") != teacher_id:
                continue

            if session_data.get("active") is True:
                stopped_session_id = stopped_session_id or firebase_session_id
                firebase_update(
                    f"classroom_sessions/{firebase_session_id}",
                    {
                        "active": False,
                        "stopped_at": datetime.now().isoformat()
                    }
                )

    # ---------------------------------------------------------
    # PRESERVE CURRENT SESSION FOR ALERT HISTORY
    # ---------------------------------------------------------
    effective_session = session_id or stopped_session_id
    if effective_session:

        request.session["last_session_id"] = effective_session

        request.session["last_session_time"] = request.session.get(
            "session_time",
            "Not available"
        )

        request.session["last_active_class"] = request.session.get(
            "active_class",
            "No previous session"
        )

    # ---------------------------------------------------------
    # CLEAR CURRENT MONITORING STATE
    # ---------------------------------------------------------

    request.session["monitoring_active"] = False
    request.session["active_class"] = "No active class"
    request.session["session_time"] = "Not started"
    request.session.pop("session_id", None)
    request.session.modified = True

    messages.success(
        request,
        "Classroom monitoring stopped."
    )

    return redirect("teacher_dashboard")

   


# =========================================================
# RECEIVE PHONE USAGE DATA
# =========================================================
@csrf_exempt
def receive_phone_usage(request):

    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Only POST method allowed."
            },
            status=405
        )

    try:

        data = json.loads(request.body)

        session_id = data.get("session_id")
        student_id = data.get("student_id")
        app_name = data.get("app_name")
        package_name = data.get("package_name")
        category = data.get("category")
        confidence = data.get("confidence")
        duration = data.get("duration", 0)

        if not all([
            session_id,
            student_id,
            app_name,
            package_name,
            category
        ]):

            return JsonResponse(
                {
                    "success": False,
                    "message": "Missing required fields."
                },
                status=400
            )

        # -----------------------------------------------------
        # VALIDATE SESSION — reject stale or unknown sessions
        # -----------------------------------------------------
        session_record = firebase_get(
            f"classroom_sessions/{session_id}"
        )

        if not session_record or not isinstance(session_record, dict):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Unknown session_id. Usage data rejected."
                },
                status=400
            )

        if not session_record.get("active", False):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Session is no longer active. Usage data rejected."
                },
                status=400
            )

        usage_data = {
            "student_id": student_id,
            "app_name": app_name,
            "package_name": package_name,
            "category": category,
            "confidence": confidence,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }

        # -----------------------------------------------------
        # ML MODEL PREDICTION (demo model — labeled clearly)
        # -----------------------------------------------------

        try:
            from .ai_model import predict_focus_with_best_model
            is_non_edu = str(category).lower() in (
                "non-educational", "non educational",
                "noneducational", "gaming", "shopping",
                "social media", "entertainment"
            )
            ml_result = predict_focus_with_best_model(
                duration_seconds=float(duration),
                non_educational=is_non_edu
            )
            usage_data["ml_prediction"] = ml_result.get("prediction")
            usage_data["ml_label"]      = ml_result.get("label", "")
            usage_data["ml_is_demo"]    = ml_result.get("is_demo_model", True)
        except Exception:
            # Model is optional — skip silently if missing or broken
            pass

        # -----------------------------------------------------
        # STORE PHONE USAGE
        # -----------------------------------------------------

        usage_ref = firebase_push(
            f"phone_usage/{session_id}",
            usage_data
        )

        usage_id = usage_ref.key

        # -----------------------------------------------------
        # ALERT DETECTION
        # -----------------------------------------------------

        alert_data = detect_alert_condition(
            usage_data
        )

        if alert_data is not None:

            # Identify registered student and device
            alert_data = identify_alert_student(
                alert_data
            )

        if alert_data is not None:
            # Calculate severity
            alert_data["severity"] = (
                calculate_alert_severity(
                    alert_data
                )
            )

            # Link alert to phone usage record
            alert_data["source_usage_id"] = usage_id

            # Store alert
            store_alert(
                session_id,
                alert_data
            )

        return JsonResponse(
            {
                "success": True,
                "message": "Phone usage stored successfully."
            }
        )

    except Exception as e:

        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=500
        )
# =========================================================
# ADMIN DASHBOARD
# =========================================================

@login_required(login_url="login")
def admin_dashboard(request):

    # ---------------------------------------------------------
    # ADMIN-ONLY GUARD
    # ---------------------------------------------------------
    guard = _require_admin(request)
    if guard is not None:
        return guard

    users_data = firebase_get("users")

    students = []

    if users_data:

        for key, student in users_data.items():

            if not isinstance(student, dict):
                continue

            if student.get("role") == "student":

                student["student_id"] = key
                students.append(student)

    devices_data = firebase_get("devices")

    devices = []

    if devices_data:

        for key, device in devices_data.items():

            if not isinstance(device, dict):
                continue

            device["register_number"] = key
            devices.append(device)

    teacher_requests_data = firebase_get(
        "teacher_requests"
    )

    teacher_requests = []

    if teacher_requests_data:

        for key, teacher in teacher_requests_data.items():

            if not isinstance(teacher, dict):
                continue

            teacher = teacher.copy()
            teacher["teacher_id"] = str(key)
            teacher["id"] = str(key)

            teacher_requests.append(teacher)

    for student in students:

        student["device_registered"] = False
        student["device_name"] = ""

        sid = str(
            student.get("student_id", "")
        ).strip()

        for device in devices:

            register_number = str(
                device.get("register_number", "")
            ).strip()

            if sid == register_number:

                student["device_registered"] = True

                student["device_name"] = device.get(
                    "device_name",
                    "Registered Device"
                )

                break

    total_students = len(students)

    total_devices = len(devices)

    total_teachers = len(
        [
            teacher
            for teacher in teacher_requests
            if teacher.get("status") == "Approved"
        ]
    )

    pending_count = len(
        [
            teacher
            for teacher in teacher_requests
            if teacher.get("status") == "Pending"
        ]
    )

    recent_system_activity = [

        {
            "icon": "👩‍🏫",
            "title": "Teacher Registrations",
            "description":
            f"{pending_count} pending request(s) waiting for approval.",
            "time": "Live"
        },

        {
            "icon": "👥",
            "title": "Student Roster",
            "description":
            f"{total_students} registered student(s).",
            "time": "Live"
        },

        {
            "icon": "📱",
            "title": "Connected Devices",
            "description":
            f"{total_devices} active mobile device(s).",
            "time": "Live"
        }

    ]

    context = {

        "total_students":
        total_students,

        "total_devices":
        total_devices,

        "total_teachers":
        total_teachers,

        "pending_count":
        pending_count,

        "students":
        students,

        "devices":
        devices,

        "teacher_requests":
        teacher_requests,

        "recent_system_activity":
        recent_system_activity

    }

    return render(
        request,
        "home/admin_dashboard.html",
        context
    )


# =========================================================
# STUDENT LIST - ADMIN
# =========================================================

@login_required(login_url="login")
def student_list(request):

    guard = _require_admin(request)
    if guard is not None:
        return guard

    users_data = firebase_get("users")

    devices_data = firebase_get("devices")

    students = []
    devices = []

    if users_data:

        for key, student in users_data.items():

            if not isinstance(student, dict):
                continue

            if student.get("role") == "student":

                student["student_id"] = key
                students.append(student)

    if devices_data:

        for key, device in devices_data.items():

            if not isinstance(device, dict):
                continue

            device["register_number"] = key
            devices.append(device)

    for student in students:

        student["device_registered"] = False
        student["device_name"] = ""

        sid = str(
            student.get("student_id", "")
        ).strip()

        for device in devices:

            if (
                str(
                    device.get(
                        "register_number",
                        ""
                    )
                ).strip()
                == sid
            ):

                student["device_registered"] = True

                student["device_name"] = device.get(
                    "device_name",
                    "Registered Device"
                )

                break

    return render(
        request,
        "home/student_list.html",
        {
            "students": students
        }
    )


# =========================================================
# APPROVE TEACHER
# =========================================================

@csrf_exempt
@login_required(login_url="login")
def approve_teacher(request, teacher_id):

    guard = _require_admin(request)
    if guard is not None:
        return guard

    if request.method != "POST":

        return redirect(
            "admin_dashboard"
        )

    teacher_id = str(teacher_id)

    teacher = firebase_get(
        f"teacher_requests/{teacher_id}"
    )

    if not teacher:

        messages.error(
            request,
            "Teacher request not found."
        )

        return redirect(
            "admin_dashboard"
        )

    teacher["status"] = "Approved"

    teacher["approved_at"] = (
        datetime.now().isoformat()
    )

    firebase_set(
        f"teacher_requests/{teacher_id}",
        teacher
    )

    tid = teacher.get(
        "teacher_id",
        teacher_id
    )

    email = teacher.get(
        "email",
        ""
    )

    name = teacher.get(
        "name",
        ""
    )

    if not User.objects.filter(
        username=tid
    ).exists():

        # Generate a secure temporary password.
        # The admin receives it in the success message and must
        # share it with the teacher securely. Never logged to files.
        import secrets as _secrets
        teacher_password = _secrets.token_urlsafe(10)

        User.objects.create_user(
            username=tid,
            email=email,
            password=teacher_password,
            first_name=name
        )

    else:
        # User already exists (re-approval) — do not change password.
        teacher_password = None

    # ---------------------------------------------------------
    # SECURITY: Remove plaintext password from Firebase now
    # that the Django account is created with a hashed copy.
    # ---------------------------------------------------------
    try:
        firebase_update(
            f"teacher_requests/{teacher_id}",
            {"password": ""}
        )
    except Exception:
        pass  # Do not block approval if this cleanup fails

    if teacher_password:
        messages.success(
            request,
            f"Teacher '{name}' approved. "
            f"Temporary login password: {teacher_password} "
            f"— Share this securely with the teacher. "
            f"They can use the password-reset link to change it."
        )
    else:
        messages.success(
            request,
            f"Teacher '{name}' re-approved. Existing password unchanged."
        )

    return redirect(
        "admin_dashboard"
    )


# =========================================================
# REJECT TEACHER
# =========================================================

@csrf_exempt
@login_required(login_url="login")
def reject_teacher(request, teacher_id):

    guard = _require_admin(request)
    if guard is not None:
        return guard

    if request.method != "POST":

        return redirect(
            "admin_dashboard"
        )

    teacher_id = str(teacher_id)

    teacher = firebase_get(
        f"teacher_requests/{teacher_id}"
    )

    if not teacher:

        messages.error(
            request,
            "Teacher request not found."
        )

        return redirect(
            "admin_dashboard"
        )

    teacher["status"] = "Rejected"

    teacher["rejected_at"] = (
        datetime.now().isoformat()
    )

    firebase_set(
        f"teacher_requests/{teacher_id}",
        teacher
    )

    messages.success(
        request,
        "Teacher request rejected."
    )

    return redirect(
        "admin_dashboard"
    )


# =========================================================
# SCAN QR & RECORD ATTENDANCE
# =========================================================

@csrf_exempt
@login_required(login_url="login")
def scan_qr(request):

    # ── Role guard: only authenticated students can scan attendance QR ──────
    guard = _require_student(request, action="scan attendance QR codes")
    if guard is not None:
        return guard
    # ─────────────────────────────────────────────────────────────────────────

    if request.method == "POST":

        # -------------------------------------------------
        # The QR code payload is now the Firebase session_id.
        # The form field is still named "classroom" to keep
        # the existing template and JS intact.
        # -------------------------------------------------
        scanned_value = request.POST.get(
            "classroom",
            ""
        ).strip()

        student_id = request.user.username

        student_name = (
            request.user.first_name
            or student_id
        )

        # -------------------------------------------------
        # VALIDATE: look up the scanned value as a
        # session_id in Firebase and confirm it is active.
        # -------------------------------------------------
        def _json_error(msg):
            """Return JSON or redirect depending on request type."""
            is_ajax = (
                request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or "application/json" in request.headers.get("Accept", "")
            )
            if is_ajax:
                return JsonResponse({"success": False, "message": msg}, status=400)
            messages.error(request, msg)
            return redirect("scan_qr")

        session_record = firebase_get(
            f"classroom_sessions/{scanned_value}"
        )

        if not session_record or not isinstance(session_record, dict):
            return _json_error(
                "Invalid QR code. No matching session found."
            )

        if not session_record.get("active", False):
            return _json_error(
                "This session has already ended. "
                "Ask your teacher to start a new session."
            )

        # -------------------------------------------------
        # Session is valid — use its stored classroom name
        # -------------------------------------------------
        classroom = session_record.get(
            "classroom",
            "Unknown Classroom"
        )

        # -------------------------------------------------
        # DUPLICATE CHECK: prevent the same student from
        # marking attendance more than once per session.
        # -------------------------------------------------
        existing_attendance = firebase_get("attendance")

        already_marked = False

        if existing_attendance and isinstance(existing_attendance, dict):
            for record in existing_attendance.values():
                if not isinstance(record, dict):
                    continue
                if (
                    str(record.get("student_id", "")).strip() == str(student_id).strip()
                    and str(record.get("session_id", "")).strip() == str(scanned_value).strip()
                ):
                    already_marked = True
                    break

        if already_marked:
            return _json_error(
                "You have already marked attendance for this session."
            )

        # -------------------------------------------------
        # STORE ATTENDANCE
        # -------------------------------------------------
        attendance_data = {

            "student_id":
            student_id,

            "student_name":
            student_name,

            "classroom":
            classroom,

            # Link attendance to the specific session
            "session_id":
            scanned_value,

            "status":
            "Present",

            "date":
            datetime.now().strftime(
                "%Y-%m-%d"
            ),

            "time":
            datetime.now().strftime(
                "%H:%M:%S"
            )

        }

        firebase_push(
            "attendance",
            attendance_data
        )

        is_ajax = (
            request.headers.get(
                "X-Requested-With"
            ) == "XMLHttpRequest"
            or
            "application/json"
            in request.headers.get(
                "Accept",
                ""
            )
        )

        if is_ajax:

            return JsonResponse({

                "success": True,

                "message":
                f"Attendance marked successfully for {classroom}!"

            })

        messages.success(
            request,
            f"Attendance marked successfully for {classroom}!"
        )

        return redirect(
            "student_dashboard"
        )

    return render(
        request,
        "home/scan_qr.html"
    )

# =========================================================
# REGISTER DEVICE
# =========================================================

@csrf_exempt
@login_required(login_url="login")
def register_device(request):

    # ── Role guard: only authenticated students can register devices ─────
    guard = _require_student(request, action="register a device")
    if guard is not None:
        return guard
    # ─────────────────────────────────────────────────────────────────────

    # Canonical student ID from session or user account
    canonical_student_id = (
        request.session.get("student_id")
        or request.user.username.strip()
    )

    if request.method == "POST":

        student_name = request.POST.get(
            "student_name",
            ""
        ).strip()

        register_number = request.POST.get(
            "register_number",
            ""
        ).strip()

        device_name = request.POST.get(
            "device_name",
            ""
        ).strip()

        imei_number = request.POST.get(
            "imei_number",
            ""
        ).strip()

        android_version = request.POST.get(
            "android_version",
            ""
        ).strip()

        # -------------------------------------------------
        # Validate device details
        # -------------------------------------------------

        if not all([
            student_name,
            register_number,
            device_name,
            android_version
        ]):

            messages.error(
                request,
                "Please fill in all device details."
            )

            return render(
                request,
                "home/register_device.html",
                {
                    "student_name": student_name,
                    "student_id": register_number,
                }
            )

        # -------------------------------------------------
        # Make sure the device belongs to logged-in student
        # Checks username, session student_id, and Firebase record
        # case-insensitively with whitespace trimmed.
        # Teachers and Admins can also register devices freely for demos.
        # -------------------------------------------------
        if not _is_teacher(request) and not _is_admin(request):
            logged_in_ids = set()
            if request.user.is_authenticated and request.user.username:
                logged_in_ids.add(request.user.username.strip().lower())

            session_student_id = request.session.get("student_id")
            if session_student_id:
                logged_in_ids.add(str(session_student_id).strip().lower())

            try:
                fb_user = firebase_get(f"users/{request.user.username}")
                if isinstance(fb_user, dict):
                    for key in ["student_id", "register_number", "register_no"]:
                        val = fb_user.get(key)
                        if val:
                            logged_in_ids.add(str(val).strip().lower())
            except Exception:
                pass

            submitted_id = register_number.strip().lower()

            if not submitted_id or submitted_id not in logged_in_ids:

                messages.error(
                    request,
                    "Register number must match your logged-in Student ID."
                )

                return render(
                    request,
                    "home/register_device.html",
                    {
                        "student_name": student_name,
                        "student_id": register_number,
                    }
                )

        canonical_student_id = register_number.strip() if (_is_teacher(request) or _is_admin(request)) else request.user.username.strip()

        # -------------------------------------------------
        # Check whether a device is already registered
        # -------------------------------------------------

        existing_device = firebase_get(
            f"devices/{canonical_student_id}"
        )
        if not existing_device and submitted_id != canonical_student_id.lower():
            existing_device = firebase_get(
                f"devices/{register_number}"
            )

        if existing_device:

            messages.error(
                request,
                "A device is already registered for this student ID."
            )

            return render(
                request,
                "home/register_device.html",
                {
                    "student_name": student_name,
                    "student_id": register_number,
                }
            )

        # -------------------------------------------------
        # Generate unique Android pairing code
        # -------------------------------------------------

        pairing_code = secrets.token_hex(4).upper()

        # Example:
        # A7F39C21

        # -------------------------------------------------
        # Device data
        # -------------------------------------------------

        device_data = {

            "student_name":
            student_name,

            "register_number":
            canonical_student_id,

            "device_name":
            device_name,

            "imei_number":
            imei_number,

            "android_version":
            android_version,

            "pairing_code":
            pairing_code,

            "pairing_status":
            "Not Paired",

            "registered_at":
            datetime.now().isoformat()

        }

        # -------------------------------------------------
        # Save device to Firebase
        # -------------------------------------------------

        firebase_set(
            f"devices/{canonical_student_id}",
            device_data
        )

        # -------------------------------------------------
        # Show pairing code to student
        # -------------------------------------------------

        messages.success(
            request,
            f"Device registered successfully! "
            f"Your Android pairing code is: {pairing_code}"
        )

        return redirect(
            "student_dashboard"
        )

    context = {
        "student_name": (
            request.user.first_name
            or request.user.username
        ),
        "student_id": (
            request.session.get("student_id")
            or request.user.username
        ),
    }

    return render(
        request,
        "home/register_device.html",
        context
    )
# =========================================================
# STUDENT PROFILE
# =========================================================

@login_required(login_url="login")
def student_profile(request):

    # ── Role guard: only authenticated students can view student profile ────
    guard = _require_student(request, action="view your student profile")
    if guard is not None:
        return guard
    # ─────────────────────────────────────────────────────────────────────────

    student_id = request.user.username

    student = firebase_get(
        f"users/{student_id}"
    )

    device = firebase_get(
        f"devices/{student_id}"
    )

    if not device:
        device = None

    return render(
        request,
        "home/student_profile.html",
        {
            "student": student,
            "device": device
        }
    )


# =========================================================
# LOGOUT
# =========================================================

def logout_view(request):

    logout(request)

    request.session.flush()

    next_url = request.GET.get("next")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)

    return redirect(
        "login"
    )


# =========================================================
# FIREBASE TEST
# =========================================================

def firebase_test(request):

    firebase_set(

        "test",

        {
            "connection":
            "Django connected successfully",

            "project":
            "FocusFrame",

            "time":
            datetime.now().isoformat()
        }

    )

    return JsonResponse({

        "success":
        True,

        "message":
        "Firebase connected successfully!"

    })


# =========================================================
# SPRINT 5 - REPORTS & ANALYTICS (T1 - T7)
# =========================================================

def _get_reports_data(request):
    """
    Collect and filter all Sprint 5 report datasets:
    - Session summaries
    - Attendance records (T2)
    - Phone usage logs (T3)
    - Student focus scores (T4)
    - Date and session filtering (T5)
    """
    classroom_sessions = firebase_get("classroom_sessions")
    all_usage = firebase_get("phone_usage")
    all_alerts = firebase_get("alerts")
    all_attendance = firebase_get("attendance")
    all_users = firebase_get("users")

    if not isinstance(classroom_sessions, dict):
        classroom_sessions = {}
    if not isinstance(all_usage, dict):
        all_usage = {}
    if not isinstance(all_alerts, dict):
        all_alerts = {}
    if not isinstance(all_attendance, dict):
        all_attendance = {}
    if not isinstance(all_users, dict):
        all_users = {}

    start_date_str = request.GET.get("start_date", "").strip()
    end_date_str = request.GET.get("end_date", "").strip()
    selected_session = request.GET.get("session_id", "").strip()
    selected_classroom = request.GET.get("classroom", "").strip()

    # 1. Process Sessions
    sessions_list = []
    classrooms_set = set()

    for s_id, s_data in classroom_sessions.items():
        if not isinstance(s_data, dict):
            continue
        c_name = s_data.get("classroom", "Unknown")
        classrooms_set.add(c_name)

        if selected_session and s_id != selected_session:
            continue
        if selected_classroom and c_name != selected_classroom:
            continue

        s_date_str = s_data.get("session_time", "") or s_data.get("created_at", "")
        if start_date_str and s_date_str and s_date_str[:10] < start_date_str:
            continue
        if end_date_str and s_date_str and s_date_str[:10] > end_date_str:
            continue

        usage_records = all_usage.get(s_id, {})
        if not isinstance(usage_records, dict):
            usage_records = {}

        edu_sec = 0.0
        non_edu_sec = 0.0
        unknown_sec = 0.0
        interactions = 0

        for u in usage_records.values():
            if not isinstance(u, dict):
                continue
            try:
                dur = max(0.0, float(u.get("duration", 0)))
            except (TypeError, ValueError):
                dur = 0.0
            cat = str(u.get("category", "")).strip().lower()
            if cat == "educational":
                edu_sec += dur
            elif "non" in cat:
                non_edu_sec += dur
            else:
                unknown_sec += dur
            interactions += 1

        total_sec = edu_sec + non_edu_sec + unknown_sec
        score = round((edu_sec / total_sec) * 100, 1) if total_sec > 0 else None

        alerts_records = all_alerts.get(s_id, {})
        alert_count = sum(1 for a in alerts_records.values() if isinstance(a, dict)) if isinstance(alerts_records, dict) else 0

        att_count = 0
        for att in all_attendance.values():
            if not isinstance(att, dict):
                continue
            att_sid = att.get("session_id")
            if att_sid:
                if att_sid == s_id:
                    att_count += 1
            elif att.get("classroom") == c_name:
                att_count += 1

        sessions_list.append({
            "session_id": s_id,
            "classroom": c_name,
            "session_time": s_data.get("session_time", "Not available"),
            "active": s_data.get("active", False),
            "educational_seconds": round(edu_sec, 1),
            "non_educational_seconds": round(non_edu_sec, 1),
            "total_seconds": round(total_sec, 1),
            "focus_score": score,
            "interaction_count": interactions,
            "alert_count": alert_count,
            "attendance_count": att_count,
        })

    # 2. Process Attendance Records (T2)
    attendance_records = []
    for att_id, att in all_attendance.items():
        if not isinstance(att, dict):
            continue
        c_name = att.get("classroom", "Unknown")
        att_date = att.get("date", "")
        att_session = att.get("session_id", "")

        if selected_classroom and c_name != selected_classroom:
            continue
        if selected_session and att_session != selected_session:
            continue
        if start_date_str and att_date and att_date < start_date_str:
            continue
        if end_date_str and att_date and att_date > end_date_str:
            continue

        attendance_records.append({
            "id": att_id,
            "student_id": att.get("student_id", "N/A"),
            "student_name": att.get("student_name", "N/A"),
            "classroom": c_name,
            "session_id": att_session or "N/A",
            "date": att_date,
            "time": att.get("time", ""),
            "status": att.get("status", "Present"),
        })

    # 3. Process Phone Usage Records (T3)
    usage_list = []
    for s_id, s_records in all_usage.items():
        if not isinstance(s_records, dict):
            continue
        if selected_session and s_id != selected_session:
            continue

        s_obj = classroom_sessions.get(s_id, {})
        c_name = s_obj.get("classroom", "Unknown") if isinstance(s_obj, dict) else "Unknown"
        if selected_classroom and c_name != selected_classroom:
            continue

        for u_id, u in s_records.items():
            if not isinstance(u, dict):
                continue
            ts = u.get("timestamp", "")
            time_formatted = ""
            if isinstance(ts, (int, float)) and ts > 100000000000:
                try:
                    time_formatted = datetime.fromtimestamp(ts / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    time_formatted = str(ts)
            else:
                time_formatted = str(ts)

            if start_date_str and time_formatted and time_formatted[:10] < start_date_str:
                continue
            if end_date_str and time_formatted and time_formatted[:10] > end_date_str:
                continue

            try:
                dur = max(0.0, float(u.get("duration", 0)))
            except (TypeError, ValueError):
                dur = 0.0

            usage_list.append({
                "student_id": u.get("student_id", "Unknown"),
                "session_id": s_id,
                "classroom": c_name,
                "app_name": u.get("app_name", "Unknown"),
                "package_name": u.get("package_name", ""),
                "category": u.get("category", "Unknown"),
                "duration": round(dur, 1),
                "timestamp": time_formatted,
            })

    # 4. Process Student Focus Scores (T4)
    student_stats = {}
    for item in usage_list:
        sid = item["student_id"]
        if sid not in student_stats:
            s_name = sid
            if isinstance(all_users.get(sid), dict):
                s_name = all_users[sid].get("full_name") or sid
            student_stats[sid] = {
                "student_id": sid,
                "student_name": s_name,
                "classroom": item["classroom"],
                "educational_seconds": 0.0,
                "non_educational_seconds": 0.0,
                "total_seconds": 0.0,
                "interaction_count": 0,
            }
        cat = str(item["category"]).strip().lower()
        dur = item["duration"]
        if cat == "educational":
            student_stats[sid]["educational_seconds"] += dur
        elif "non" in cat:
            student_stats[sid]["non_educational_seconds"] += dur
        student_stats[sid]["total_seconds"] += dur
        student_stats[sid]["interaction_count"] += 1

    student_focus_list = []
    for sid, stat in student_stats.items():
        tot = stat["total_seconds"]
        edu = stat["educational_seconds"]
        score = round((edu / tot) * 100, 1) if tot > 0 else 0.0
        if score >= 75:
            level = "Focused"
        elif score >= 50:
            level = "Moderate"
        else:
            level = "Distracted"
        stat["focus_score"] = score
        stat["focus_level"] = level
        stat["educational_seconds"] = round(edu, 1)
        stat["non_educational_seconds"] = round(stat["non_educational_seconds"], 1)
        stat["total_seconds"] = round(tot, 1)
        student_focus_list.append(stat)

    sessions_list.sort(key=lambda x: str(x.get("session_time", "")), reverse=True)
    attendance_records.sort(key=lambda x: (str(x.get("date", "")), str(x.get("time", ""))), reverse=True)
    usage_list.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)
    student_focus_list.sort(key=lambda x: x.get("focus_score", 0), reverse=True)

    return {
        "sessions": sessions_list,
        "attendance": attendance_records,
        "usage": usage_list,
        "student_focus": student_focus_list,
        "classrooms": sorted(list(classrooms_set)),
        "all_sessions_list": [{"id": k, "classroom": v.get("classroom", k)} for k, v in classroom_sessions.items() if isinstance(v, dict)],
        "start_date": start_date_str,
        "end_date": end_date_str,
        "selected_session": selected_session,
        "selected_classroom": selected_classroom,
    }


@login_required(login_url="login")
def reports_analytics(request):
    """
    Sprint 5: Comprehensive Reports & Analytics View (T1, T2, T3, T4, T5, T6).
    """
    guard = _require_teacher(request)
    if guard is not None:
        return guard

    data = _get_reports_data(request)
    active_tab = request.GET.get("tab", "overview")

    total_interactions = sum(s["interaction_count"] for s in data["sessions"])
    total_attendance = len(data["attendance"])
    total_usage_entries = len(data["usage"])
    scores = [s["focus_score"] for s in data["sessions"] if s["focus_score"] is not None]
    avg_focus_score = round(sum(scores) / len(scores), 1) if scores else None

    return render(
        request,
        "home/reports_analytics.html",
        {
            "reports": data["sessions"],
            "attendance_records": data["attendance"],
            "usage_records": data["usage"],
            "student_focus_reports": data["student_focus"],
            "classrooms": data["classrooms"],
            "all_sessions_list": data["all_sessions_list"],
            "start_date": data["start_date"],
            "end_date": data["end_date"],
            "selected_session": data["selected_session"],
            "selected_classroom": data["selected_classroom"],
            "active_tab": active_tab,
            "total_interactions": total_interactions,
            "total_attendance": total_attendance,
            "total_usage_entries": total_usage_entries,
            "avg_focus_score": avg_focus_score,
        },
    )


# =========================================================
# SPRINT 5 - REPORT DOWNLOADS (CSV EXPORT) (T7)
# =========================================================

def _sanitize_csv_cell(value):
    """
    Prevent Excel CSV formula injection and #NAME? formula errors.
    If a string starts with '-', '+', '=', or '@', prefix with a single quote (')
    so Excel renders it cleanly as plain text without executing formulas.
    """
    if value is None:
        return ""
    val_str = str(value).strip()
    if val_str and val_str[0] in ("-", "+", "=", "@"):
        return f"'{val_str}"
    return val_str


def _format_csv_date(date_val):
    """
    Format date string into readable text (e.g. '22 Oct 2026')
    to prevent Excel from displaying '########' column overflow errors.
    """
    if not date_val:
        return "N/A"
    date_str = str(date_val).strip()
    try:
        if len(date_str) >= 10 and "-" in date_str[:10]:
            parts = date_str[:10].split("-")
            dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            return dt.strftime("%d %b %Y")
    except Exception:
        pass
    return f"'{date_str}"


def _format_csv_timestamp(ts_val):
    """
    Format timestamp string for CSV/Excel export.
    Converts 'YYYY-MM-DD HH:MM:SS' into clean text format (e.g. '23 Oct 2026 05:39:48')
    to prevent Excel from treating it as a raw ISO date and collapsing into '########'.
    """
    if not ts_val:
        return "N/A"
    ts_str = str(ts_val).strip()
    try:
        if len(ts_str) >= 19 and "-" in ts_str[:10]:
            clean_ts = ts_str[:19].replace("T", " ")
            dt = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d %b %Y %H:%M:%S")
        elif len(ts_str) >= 10 and "-" in ts_str[:10]:
            clean_date = ts_str[:10]
            parts = clean_date.split("-")
            dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            return dt.strftime("%d %b %Y")
    except Exception:
        pass
    return f"'{ts_str}"


@login_required(login_url="login")
def export_attendance_csv(request):
    """
    Sprint 5 (T7): Export Student Attendance Report as CSV.
    Formatted for Excel compatibility (no #NAME? formula errors, clean date columns).
    """
    guard = _require_teacher(request)
    if guard is not None:
        return guard

    data = _get_reports_data(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="focusframe_attendance_report.csv"'

    writer = csv.writer(response)
    writer.writerow(["Student ID", "Student Name", "Classroom", "Session ID", "Date", "Time", "Status"])
    for row in data["attendance"]:
        writer.writerow([
            _sanitize_csv_cell(row["student_id"]),
            row["student_name"],
            row["classroom"],
            _sanitize_csv_cell(row["session_id"]),
            _format_csv_date(row["date"]),
            row["time"],
            row["status"]
        ])
    return response


@login_required(login_url="login")
def export_usage_csv(request):
    """
    Sprint 5 (T7): Export Phone Usage & Activity Report as CSV.
    """
    guard = _require_teacher(request)
    if guard is not None:
        return guard

    data = _get_reports_data(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="focusframe_phone_usage_report.csv"'

    writer = csv.writer(response)
    writer.writerow(["Student ID", "Classroom", "Session ID", "App Name", "Package Name", "Category", "Duration (Seconds)", "Timestamp"])
    for row in data["usage"]:
        writer.writerow([
            _sanitize_csv_cell(row["student_id"]),
            row["classroom"],
            _sanitize_csv_cell(row["session_id"]),
            row["app_name"],
            row["package_name"],
            row["category"],
            row["duration"],
            _format_csv_timestamp(row["timestamp"])
        ])
    return response


@login_required(login_url="login")
def export_focus_csv(request):
    """
    Sprint 5 (T7): Export Student Focus Scores Report as CSV.
    """
    guard = _require_teacher(request)
    if guard is not None:
        return guard

    data = _get_reports_data(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="focusframe_focus_scores_report.csv"'

    writer = csv.writer(response)
    writer.writerow(["Student ID", "Student Name", "Classroom", "Educational Usage (Sec)", "Non-Educational Usage (Sec)", "Total Usage (Sec)", "Focus Score (%)", "Focus Level"])
    for row in data["student_focus"]:
        writer.writerow([
            _sanitize_csv_cell(row["student_id"]),
            row["student_name"],
            row["classroom"],
            row["educational_seconds"],
            row["non_educational_seconds"],
            row["total_seconds"],
            row["focus_score"],
            row["focus_level"]
        ])
    return response
