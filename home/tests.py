# -*- coding: utf-8 -*-
"""
FocusFrame — Automated Django Test Suite
Uses unittest.mock to isolate Firebase calls so all view logic
can be tested without a real Firebase connection.

Run: python manage.py test home --verbosity=2
"""
import json
from unittest.mock import patch, MagicMock, call
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages


# ---------------------------------------------------------------------------
# Shared Firebase mock data
# ---------------------------------------------------------------------------

FAKE_SESSION_ID = "FAKESESSION001"
FAKE_STUDENT_ID = "STU001"
FAKE_TEACHER_ID = "TCH001"

ACTIVE_SESSION = {
    "teacher_id": FAKE_TEACHER_ID,
    "classroom": "CS-402 Test Class",
    "session_time": "22 Oct 2026, 09:00 AM",
    "active": True,
    "qr_code": FAKE_SESSION_ID,
    "created_at": "2026-10-22T09:00:00",
}

INACTIVE_SESSION = dict(ACTIVE_SESSION, active=False, stopped_at="2026-10-22T10:00:00")

FAKE_USER_DATA = {
    FAKE_STUDENT_ID: {
        "full_name": "Test Student",
        "student_id": FAKE_STUDENT_ID,
        "email": "student@test.com",
        "role": "student",
        "created_at": "2026-10-22T08:00:00",
    }
}

FAKE_TEACHER_REQUEST_PENDING = {
    FAKE_TEACHER_ID: {
        "teacher_id": FAKE_TEACHER_ID,
        "name": "Test Teacher",
        "email": "teacher@test.com",
        "department": "CS",
        "password": "",
        "status": "Pending",
        "registered_at": "2026-10-22T08:00:00",
    }
}

FAKE_TEACHER_REQUEST_APPROVED = {
    FAKE_TEACHER_ID: dict(
        FAKE_TEACHER_REQUEST_PENDING[FAKE_TEACHER_ID],
        status="Approved",
    )
}


def make_push_mock(key=FAKE_SESSION_ID):
    """Return a mock whose .key attribute is the given key."""
    m = MagicMock()
    m.key = key
    return m


# ===========================================================================
# 1. URL RESOLUTION
# ===========================================================================

class URLResolutionTests(TestCase):
    """All named URLs must resolve without errors."""

    URLS = [
        ("home", []),
        ("login", []),
        ("register", []),
        ("logout", []),
        ("student_dashboard", []),
        ("teacher_dashboard", []),
        ("start_monitoring", []),
        ("stop_monitoring", []),
        ("scan_qr", []),
        ("receive_phone_usage", []),
        ("admin_dashboard", []),
        ("approve_teacher", ["test_id"]),
        ("reject_teacher", ["test_id"]),
        ("reports_analytics", []),
        ("export_attendance_csv", []),
        ("export_usage_csv", []),
        ("export_focus_csv", []),
        ("register_device", []),
        ("student_profile", []),
        ("password_reset", []),
        ("password_reset_done", []),
        ("password_reset_complete", []),
    ]

    def test_all_urls_resolve(self):
        for name, args in self.URLS:
            with self.subTest(url=name):
                url = reverse(name, args=args)
                self.assertTrue(url.startswith("/"), msg=f"{name} resolved to {url}")


# ===========================================================================
# 2. HOME & UNAUTHENTICATED ACCESS
# ===========================================================================

class UnauthenticatedAccessTests(TestCase):

    def setUp(self):
        self.client = Client()

    def test_home_page_loads(self):
        resp = self.client.get(reverse("home"))
        self.assertIn(resp.status_code, [200, 301, 302])

    def test_login_page_loads(self):
        resp = self.client.get(reverse("login"))
        self.assertEqual(resp.status_code, 200)

    def test_register_page_loads(self):
        resp = self.client.get(reverse("register"))
        self.assertEqual(resp.status_code, 200)

    def test_student_dashboard_requires_login(self):
        resp = self.client.get(reverse("student_dashboard"))
        self.assertRedirects(resp, f"/login/?next={reverse('student_dashboard')}",
                             fetch_redirect_response=False)

    def test_teacher_dashboard_requires_login(self):
        resp = self.client.get(reverse("teacher_dashboard"))
        self.assertRedirects(resp, f"/login/?next={reverse('teacher_dashboard')}",
                             fetch_redirect_response=False)

    def test_admin_dashboard_requires_login(self):
        resp = self.client.get(reverse("admin_dashboard"))
        self.assertRedirects(resp, f"/login/?next={reverse('admin_dashboard')}",
                             fetch_redirect_response=False)

    def test_scan_qr_requires_login(self):
        resp = self.client.get(reverse("scan_qr"))
        self.assertRedirects(resp, f"/login/?next={reverse('scan_qr')}",
                             fetch_redirect_response=False)


# ===========================================================================
# 2B. NAVBAR & AUTHENTICATION STATE NAVIGATION
# ===========================================================================

class NavbarNavigationTests(TestCase):
    """
    Verify homepage navigation links and authentication states:
    - Logged out: FocusFrame logo, Home, Features, About, Sign In, Get Started. No dashboard, no logout.
    - Logged in teacher: Teacher Dashboard (teacher123), Logout. No Sign In, no Get Started.
    - Logged in student: Student Dashboard (student123), Logout. No Sign In, no Get Started.
    - Logged in admin: Admin Dashboard (user), Logout. No Sign In, no Get Started.
    """

    def setUp(self):
        self.client = Client()
        self.teacher_user = User.objects.create_user(username="teacher123", password="Password123!")
        self.student_user = User.objects.create_user(username="student123", password="Password123!")
        self.admin_user = User.objects.create_user(username="user", password="Password123!", is_superuser=True)

    def test_logged_out_homepage_navigation(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("FocusFrame", content)
        self.assertIn("Focus Intelligence", content)
        self.assertIn("Home", content)
        self.assertIn("Features", content)
        self.assertIn("About", content)
        self.assertIn("Sign In", content)
        self.assertIn("Get Started", content)
        self.assertNotIn("Teacher Dashboard", content)
        self.assertNotIn("Student Dashboard", content)
        self.assertNotIn("Logout", content)

    def test_logged_in_teacher_homepage_navigation(self):
        self.client.force_login(self.teacher_user)
        session = self.client.session
        session["role"] = "teacher"
        session.save()

        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("Teacher Dashboard (teacher123)", content)
        self.assertIn("Logout", content)
        self.assertNotIn("Sign In", content)
        self.assertNotIn("Get Started", content)

    def test_logged_in_student_homepage_navigation(self):
        self.client.force_login(self.student_user)
        session = self.client.session
        session["role"] = "student"
        session.save()

        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("Student Dashboard (student123)", content)
        self.assertIn("Logout", content)
        self.assertNotIn("Sign In", content)
        self.assertNotIn("Get Started", content)

    def test_logged_in_admin_homepage_navigation(self):
        self.client.force_login(self.admin_user)
        session = self.client.session
        session["role"] = "admin"
        session.save()

        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("Admin Dashboard (user)", content)
        self.assertIn("Logout", content)
        self.assertNotIn("Sign In", content)
        self.assertNotIn("Get Started", content)


# ===========================================================================
# 3. STUDENT REGISTRATION (Workflow 1 — Part A)
# ===========================================================================

class StudentRegistrationTests(TestCase):

    def setUp(self):
        self.client = Client()

    @patch("home.views.firebase_get", return_value=None)
    @patch("home.views.firebase_set", return_value=None)
    def test_student_registration_success_redirects_to_login(self, mock_set, mock_get):
        """
        WF1: Successful student registration must use POST-Redirect-Get
        and send the student to the login page.
        """
        resp = self.client.post(reverse("register"), {
            "role": "student",
            "fullName": "Test Student",
            "regEmail": "newstudent@test.com",
            "password": "TestPass123!",
            "confirmPassword": "TestPass123!",
            "studentId": "STU_NEW_001",
        })
        self.assertEqual(resp.status_code, 302,
                         msg="Registration should redirect (PRG pattern)")
        self.assertRedirects(resp, reverse("login"),
                             fetch_redirect_response=False)

        # Django user created
        self.assertTrue(User.objects.filter(username="STU_NEW_001").exists())

        # Firebase set called with correct path
        called_paths = [str(c[0][0]) for c in mock_set.call_args_list]
        self.assertTrue(
            any("users/STU_NEW_001" in p for p in called_paths),
            msg=f"firebase_set should write to users/STU_NEW_001. Calls: {called_paths}"
        )

    @patch("home.views.firebase_get", return_value=None)
    def test_student_registration_password_mismatch(self, mock_get):
        resp = self.client.post(reverse("register"), {
            "role": "student",
            "fullName": "Bad Student",
            "regEmail": "bad@test.com",
            "password": "pass1",
            "confirmPassword": "pass2",
            "studentId": "STU_BAD",
        })
        # Should re-render with error, no redirect
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="STU_BAD").exists())

    @patch("home.views.firebase_get")
    def test_student_registration_duplicate_id_rejected(self, mock_get):
        """Duplicate student_id already in Firebase → error, no new user."""
        mock_get.return_value = {"full_name": "Existing", "role": "student"}
        resp = self.client.post(reverse("register"), {
            "role": "student",
            "fullName": "Dup Student",
            "regEmail": "dup@test.com",
            "password": "TestPass123!",
            "confirmPassword": "TestPass123!",
            "studentId": "STU_DUP",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="STU_DUP").exists())


# ===========================================================================
# 4. LOGIN / LOGOUT (Workflow 1 — Part B)
# ===========================================================================

class StudentLoginLogoutTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username=FAKE_STUDENT_ID,
            password="TestPass123!",
            first_name="Test Student",
            email="student@test.com",
        )

    @patch("home.views.firebase_get")
    def test_student_login_success(self, mock_fb):
        """WF1: Valid student login → redirected to student_dashboard."""
        mock_fb.return_value = {
            "role": "student",
            "full_name": "Test Student",
        }
        resp = self.client.post(reverse("login"), {
            "role": "student",
            "username": FAKE_STUDENT_ID,
            "password": "TestPass123!",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("student_dashboard"),
                             fetch_redirect_response=False)
        # Session should be authenticated
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.student.pk)

    def test_student_login_wrong_password(self):
        resp = self.client.post(reverse("login"), {
            "role": "student",
            "username": FAKE_STUDENT_ID,
            "password": "wrongpassword",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    @patch("home.views.firebase_get")
    def test_logout_clears_session(self, mock_fb):
        """WF1: Logout must clear auth session."""
        mock_fb.return_value = {"role": "student"}
        self.client.post(reverse("login"), {
            "role": "student",
            "username": FAKE_STUDENT_ID,
            "password": "TestPass123!",
        })
        self.assertIn("_auth_user_id", self.client.session)

        resp = self.client.post(reverse("logout"))
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    @patch("home.views.firebase_get")
    def test_student_login_then_logout_then_login_again(self, mock_fb):
        """WF1: Full cycle — login, logout, login again."""
        mock_fb.return_value = {"role": "student", "full_name": "Test Student"}

        self.client.post(reverse("login"), {
            "role": "student",
            "username": FAKE_STUDENT_ID,
            "password": "TestPass123!",
        })
        self.assertIn("_auth_user_id", self.client.session)

        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

        resp = self.client.post(reverse("login"), {
            "role": "student",
            "username": FAKE_STUDENT_ID,
            "password": "TestPass123!",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_get_respects_role_query_parameter(self):
        """GET /login/?role=teacher should render with role 'teacher'."""
        resp = self.client.get(reverse("login") + "?role=teacher")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["role"], "teacher")

    def test_logout_view_respects_next_query_parameter(self):
        """GET /logout/?next=/login/?role=student should redirect to next url."""
        resp = self.client.get(reverse("logout") + "?next=/login/?role=student")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/login/?role=student")


# ===========================================================================
# 5. ROLE ENFORCEMENT (Workflows 2, 3, 4)
# ===========================================================================

class RoleEnforcementTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username="role_student", password="pass123",
        )
        self.admin = User.objects.create_superuser(
            username="role_admin", password="adminpass123",
        )

    # ---- Student cannot reach teacher views ----

    @patch("home.views.firebase_get", return_value=None)
    def test_student_cannot_access_teacher_dashboard(self, mock_fb):
        """WF4: Student blocked from teacher_dashboard."""
        mock_fb.return_value = {"role": "student"}
        self.client.login(username="role_student", password="pass123")
        resp = self.client.get(reverse("teacher_dashboard"))
        # Must redirect away (not 200)
        self.assertNotEqual(resp.status_code, 200,
                            msg="Student must not see teacher_dashboard")

    @patch("home.views.firebase_get", return_value=None)
    def test_student_cannot_start_monitoring(self, mock_fb):
        """WF4: Student cannot start a monitoring session."""
        mock_fb.return_value = {"role": "student"}
        self.client.login(username="role_student", password="pass123")
        resp = self.client.post(reverse("start_monitoring"), {
            "classroom_name": "Hacked Classroom",
        })
        self.assertNotEqual(resp.status_code, 200)
        # Firebase push must not be called
        # (verified implicitly: view returns redirect before push)

    # ---- Student cannot reach admin views ----

    @patch("home.views.firebase_get", return_value=None)
    def test_student_cannot_access_admin_dashboard(self, mock_fb):
        """WF3: Student blocked from admin_dashboard."""
        self.client.login(username="role_student", password="pass123")
        resp = self.client.get(reverse("admin_dashboard"))
        self.assertNotEqual(resp.status_code, 200)

    # ---- Admin can access admin dashboard ----

    @patch("home.views.firebase_get")
    def test_admin_can_access_admin_dashboard(self, mock_fb):
        """WF3: Superuser can load admin_dashboard."""
        mock_fb.return_value = {}
        self.client.login(username="role_admin", password="adminpass123")
        resp = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(resp.status_code, 200)

    # ---- Admin cannot accidentally access teacher dashboard ----

    @patch("home.views.firebase_get", return_value=None)
    def test_admin_blocked_from_teacher_dashboard(self, mock_fb):
        """WF3: Admin (not an approved teacher) blocked from teacher_dashboard."""
        self.client.login(username="role_admin", password="adminpass123")
        resp = self.client.get(reverse("teacher_dashboard"))
        self.assertNotEqual(resp.status_code, 200,
                            msg="Admin who is not an approved teacher must not see teacher_dashboard")

    # ---- Teacher blocked from student views ----

    @patch("home.views.firebase_get")
    def test_teacher_blocked_from_student_dashboard(self, mock_fb):
        """Teacher cannot access student_dashboard; redirected to teacher_dashboard."""
        teacher = User.objects.create_user(username="guard_teacher", password="teachpass123")
        self.client.login(username="guard_teacher", password="teachpass123")
        session = self.client.session
        session["role"] = "teacher"
        session.save()

        resp = self.client.get(reverse("student_dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("teacher_dashboard"), fetch_redirect_response=False)

    @patch("home.views.firebase_get")
    def test_teacher_blocked_from_scan_qr(self, mock_fb):
        """Teacher cannot access scan_qr; redirected to teacher_dashboard."""
        teacher = User.objects.create_user(username="guard_teacher2", password="teachpass123")
        self.client.login(username="guard_teacher2", password="teachpass123")
        session = self.client.session
        session["role"] = "teacher"
        session.save()

        resp = self.client.get(reverse("scan_qr"))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("teacher_dashboard"), fetch_redirect_response=False)

    @patch("home.views.firebase_get")
    def test_teacher_blocked_from_student_profile(self, mock_fb):
        """Teacher cannot access student_profile; redirected to teacher_dashboard."""
        teacher = User.objects.create_user(username="guard_teacher3", password="teachpass123")
        self.client.login(username="guard_teacher3", password="teachpass123")
        session = self.client.session
        session["role"] = "teacher"
        session.save()

        resp = self.client.get(reverse("student_profile"))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("teacher_dashboard"), fetch_redirect_response=False)

    @patch("home.views.firebase_get")
    def test_teacher_blocked_from_register_device(self, mock_fb):
        """Teacher cannot access register_device; redirected to teacher_dashboard with error message."""
        teacher = User.objects.create_user(username="guard_teacher4", password="teachpass123")
        self.client.login(username="guard_teacher4", password="teachpass123")
        session = self.client.session
        session["role"] = "teacher"
        session.save()

        resp = self.client.get(reverse("register_device"))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("teacher_dashboard"), fetch_redirect_response=False)

    # ---- Admin blocked from student views ----

    @patch("home.views.firebase_get", return_value=None)
    def test_admin_blocked_from_student_dashboard(self, mock_fb):
        """Admin cannot access student_dashboard; redirected to admin_dashboard."""
        self.client.login(username="role_admin", password="adminpass123")
        session = self.client.session
        session["role"] = "admin"
        session.save()

        resp = self.client.get(reverse("student_dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("admin_dashboard"), fetch_redirect_response=False)

    # ---- Student access to student views ----

    @patch("home.views.firebase_get", return_value=None)
    def test_student_can_access_student_dashboard(self, mock_fb):
        """Student can access student_dashboard."""
        self.client.login(username="role_student", password="pass123")
        session = self.client.session
        session["role"] = "student"
        session.save()

        resp = self.client.get(reverse("student_dashboard"))
        self.assertEqual(resp.status_code, 200)

    @patch("home.views.firebase_get", return_value=None)
    def test_student_can_access_register_device(self, mock_fb):
        """Student can access register_device without being redirected to teacher dashboard."""
        self.client.login(username="role_student", password="pass123")
        session = self.client.session
        session["role"] = "student"
        session.save()

        resp = self.client.get(reverse("register_device"))
        self.assertEqual(resp.status_code, 200)


# ===========================================================================
# 6. TEACHER REGISTRATION + APPROVAL (Workflow 2)
# ===========================================================================

class TeacherRegistrationApprovalTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="approver_admin", password="adminpass123",
        )

    @patch("home.views.firebase_get", return_value=None)
    @patch("home.views.firebase_set", return_value=None)
    def test_teacher_registration_does_not_store_plaintext_password(
        self, mock_set, mock_get
    ):
        """
        WF2+WF3: Teacher registration must NOT store plaintext password in Firebase.
        Stored password field must be empty string.
        """
        self.client.post(reverse("register"), {
            "role": "teacher",
            "fullName": "New Teacher",
            "regEmail": "newteacher@test.com",
            "password": "SecretPass999!",
            "confirmPassword": "SecretPass999!",
            "employeeId": "TCH_NEW",
            "department": "CS",
        })
        stored_data = None
        for c in mock_set.call_args_list:
            path = c[0][0]
            data = c[0][1]
            if "teacher_requests" in str(path):
                stored_data = data
                break

        self.assertIsNotNone(stored_data, "firebase_set for teacher_requests not called")
        self.assertEqual(
            stored_data.get("password", "NOTFOUND"),
            "",
            msg=f"Plaintext password must not be stored. Got: {stored_data.get('password')}"
        )
        # Redirect to login (PRG)
        # Note: view is tested separately; here we verify Firebase data only

    @patch("home.views.firebase_get")
    @patch("home.views.firebase_set", return_value=None)
    @patch("home.views.firebase_update", return_value=None)
    def test_approve_teacher_creates_django_user_with_random_password(
        self, mock_update, mock_set, mock_get
    ):
        """
        WF2: Approving a teacher creates a Django user with a random
        temp password — not an empty password.
        """
        # firebase_get returns the Pending teacher request
        mock_get.return_value = {
            "teacher_id": "TCH_APPROVE",
            "name": "Approvable Teacher",
            "email": "approvable@test.com",
            "department": "CS",
            "password": "",   # as stored after our fix
            "status": "Pending",
        }
        self.client.login(username="approver_admin", password="adminpass123")
        resp = self.client.post(
            reverse("approve_teacher", args=["TCH_APPROVE"])
        )
        self.assertEqual(resp.status_code, 302)

        user = User.objects.filter(username="TCH_APPROVE").first()
        self.assertIsNotNone(user, "Django user for teacher must be created on approval")
        self.assertTrue(
            user.has_usable_password(),
            "Approved teacher must have a usable (non-empty) password"
        )

        # Check that the success message contains a temporary password
        messages_list = list(get_messages(resp.wsgi_request))
        msg_text = " ".join(str(m) for m in messages_list)
        self.assertIn("password", msg_text.lower(),
                      msg="Success message must include the temporary password")

    @patch("home.views.firebase_get")
    @patch("home.views.firebase_set", return_value=None)
    @patch("home.views.firebase_update", return_value=None)
    def test_approve_teacher_duplicate_does_not_overwrite_password(
        self, mock_update, mock_set, mock_get
    ):
        """
        WF3: If teacher Django user already exists, re-approving must not
        change the password.
        """
        # Create existing teacher user
        existing = User.objects.create_user(
            username="TCH_EXISTING",
            password="OriginalPassword!",
            email="existing@test.com",
        )
        original_hash = existing.password

        mock_get.return_value = {
            "teacher_id": "TCH_EXISTING",
            "name": "Existing Teacher",
            "email": "existing@test.com",
            "department": "CS",
            "password": "",
            "status": "Pending",
        }
        self.client.login(username="approver_admin", password="adminpass123")
        self.client.post(reverse("approve_teacher", args=["TCH_EXISTING"]))

        existing.refresh_from_db()
        self.assertEqual(
            existing.password, original_hash,
            msg="Re-approval must not change an existing teacher's password"
        )

    @patch("home.views.firebase_get", return_value=None)
    def test_approve_teacher_blocked_for_non_admin(self, mock_fb):
        """WF3: Non-admin cannot approve a teacher."""
        student = User.objects.create_user(username="bad_approver", password="pass")
        self.client.login(username="bad_approver", password="pass")
        resp = self.client.post(reverse("approve_teacher", args=["TCH_ANY"]))
        self.assertNotEqual(resp.status_code, 200)
        # Teacher must not be created
        self.assertFalse(User.objects.filter(username="TCH_ANY").exists())

    @patch("home.views.firebase_get")
    @patch("home.views.firebase_update", return_value=None)
    def test_reject_teacher_blocked_for_non_admin(self, mock_update, mock_fb):
        """WF3: Non-admin cannot reject a teacher."""
        mock_fb.return_value = {"status": "Pending"}
        student = User.objects.create_user(username="bad_rejecter", password="pass")
        self.client.login(username="bad_rejecter", password="pass")
        resp = self.client.post(reverse("reject_teacher", args=["TCH_ANY"]))
        self.assertNotEqual(resp.status_code, 200)


# ===========================================================================
# 7. QR ATTENDANCE WORKFLOW (Workflow 5)
# ===========================================================================

class QRAttendanceTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username=FAKE_STUDENT_ID,
            password="pass123",
        )
        self.client.login(username=FAKE_STUDENT_ID, password="pass123")

    @patch("home.views.firebase_push")
    @patch("home.views.firebase_get")
    def test_scan_qr_active_session_marks_attendance(self, mock_get, mock_push):
        """
        WF5: Scanning valid active session → attendance stored in Firebase.
        """
        def fb_get_side_effect(path):
            if path == f"classroom_sessions/{FAKE_SESSION_ID}":
                return ACTIVE_SESSION
            if path == "attendance":
                return {}  # No existing attendance
            return None

        mock_get.side_effect = fb_get_side_effect
        mock_push.return_value = make_push_mock("ATT001")

        resp = self.client.post(reverse("scan_qr"), {
            "classroom": FAKE_SESSION_ID,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("student_dashboard"),
                             fetch_redirect_response=False)

        # Firebase push called for attendance
        push_calls = [str(c[0][0]) for c in mock_push.call_args_list]
        self.assertTrue(
            any("attendance" in p for p in push_calls),
            msg=f"firebase_push must write to attendance. Calls: {push_calls}"
        )
        # Attendance data includes correct session_id
        att_data = None
        for c in mock_push.call_args_list:
            if "attendance" in str(c[0][0]):
                att_data = c[0][1]
        self.assertIsNotNone(att_data)
        self.assertEqual(att_data.get("session_id"), FAKE_SESSION_ID)
        self.assertEqual(att_data.get("student_id"), FAKE_STUDENT_ID)
        self.assertEqual(att_data.get("status"), "Present")

    @patch("home.views.firebase_get")
    def test_scan_qr_inactive_session_rejected(self, mock_get):
        """WF5: Scanning an inactive/stopped session → error, no attendance."""
        def fb_get_side_effect(path):
            if path == f"classroom_sessions/{FAKE_SESSION_ID}":
                return INACTIVE_SESSION
            return None

        mock_get.side_effect = fb_get_side_effect

        resp = self.client.post(reverse("scan_qr"), {
            "classroom": FAKE_SESSION_ID,
        })
        # Should redirect back to scan_qr with error message, not student_dashboard
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("scan_qr"),
                             fetch_redirect_response=False)

    @patch("home.views.firebase_get")
    def test_scan_qr_nonexistent_session_rejected(self, mock_get):
        """WF5: Scanning a QR that doesn't exist in Firebase → error."""
        mock_get.return_value = None
        resp = self.client.post(reverse("scan_qr"), {
            "classroom": "BOGUS_SESSION_ID",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("scan_qr"),
                             fetch_redirect_response=False)

    @patch("home.views.firebase_push")
    @patch("home.views.firebase_get")
    def test_scan_qr_duplicate_attendance_rejected(self, mock_get, mock_push):
        """WF5: Same student cannot mark attendance twice for same session."""
        existing_attendance = {
            "ATT_EXISTING": {
                "student_id": FAKE_STUDENT_ID,
                "session_id": FAKE_SESSION_ID,
                "status": "Present",
            }
        }

        def fb_get_side_effect(path):
            if path == f"classroom_sessions/{FAKE_SESSION_ID}":
                return ACTIVE_SESSION
            if path == "attendance":
                return existing_attendance
            return None

        mock_get.side_effect = fb_get_side_effect

        resp = self.client.post(reverse("scan_qr"), {
            "classroom": FAKE_SESSION_ID,
        })
        # Should redirect back to scan_qr with duplicate error
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("scan_qr"),
                             fetch_redirect_response=False)
        # firebase_push must NOT be called
        mock_push.assert_not_called()


# ===========================================================================
# 8. START / STOP MONITORING (Workflow 5 — teacher side)
# ===========================================================================

class MonitoringSessionTests(TestCase):

    def setUp(self):
        self.client = Client()
        # Approved teacher in Django + Firebase
        self.teacher = User.objects.create_user(
            username=FAKE_TEACHER_ID,
            password="teacherpass",
        )
        # Give teacher the session role so _is_teacher passes
        session = self.client.session
        session["role"] = "teacher"
        session.save()
        self.client.login(username=FAKE_TEACHER_ID, password="teacherpass")
        # Override session role after login
        s = self.client.session
        s["role"] = "teacher"
        s.save()

    @patch("home.views.firebase_set", return_value=None)
    @patch("home.views.firebase_update", return_value=None)
    @patch("home.views.firebase_push")
    @patch("home.views.firebase_get", return_value=None)
    def test_start_monitoring_creates_firebase_session(
        self, mock_get, mock_push, mock_update, mock_set
    ):
        """WF5: start_monitoring creates a Firebase classroom session."""
        mock_push.return_value = make_push_mock(FAKE_SESSION_ID)

        resp = self.client.post(reverse("start_monitoring"), {
            "classroom_name": "CS-402 Mobile Computing",
        })
        self.assertEqual(resp.status_code, 302)

        push_calls = [str(c[0][0]) for c in mock_push.call_args_list]
        self.assertTrue(
            any("classroom_sessions" in p for p in push_calls),
            msg=f"firebase_push must create classroom_sessions entry. Calls: {push_calls}"
        )

        # session_id stored in Django session
        self.assertEqual(self.client.session.get("session_id"), FAKE_SESSION_ID)
        self.assertTrue(self.client.session.get("monitoring_active"))

    @patch("home.views.firebase_get")
    @patch("home.views.firebase_update", return_value=None)
    def test_stop_monitoring_only_stops_this_teachers_sessions(
        self, mock_update, mock_get
    ):
        """
        WF5: stop_monitoring must set active=False only for sessions
        owned by the logged-in teacher.
        """
        other_session = dict(ACTIVE_SESSION, teacher_id="OTHER_TEACHER")
        sessions = {
            FAKE_SESSION_ID: ACTIVE_SESSION,
            "OTHER_SID": other_session,
        }
        mock_get.return_value = sessions

        s = self.client.session
        s["monitoring_active"] = True
        s["session_id"] = FAKE_SESSION_ID
        s.save()

        resp = self.client.post(reverse("stop_monitoring"))
        self.assertEqual(resp.status_code, 302)

        # Only this teacher's session should be stopped
        update_calls = mock_update.call_args_list
        stopped_paths = [str(c[0][0]) for c in update_calls]
        self.assertTrue(
            any(FAKE_SESSION_ID in p for p in stopped_paths),
            msg="Must stop this teacher's session"
        )
        other_stopped = any("OTHER_SID" in p for p in stopped_paths)
        self.assertFalse(other_stopped, msg="Must NOT stop other teacher's session")

    @patch("home.views.firebase_get", return_value=None)
    def test_student_cannot_start_monitoring(self, mock_fb):
        """WF4: A student (not a teacher) cannot start monitoring."""
        student = User.objects.create_user(username="stu_bad", password="pass")
        c = Client()
        c.login(username="stu_bad", password="pass")
        resp = c.post(reverse("start_monitoring"), {"classroom_name": "Hack"})
        self.assertNotEqual(resp.status_code, 200)


# ===========================================================================
# 9. RECEIVE PHONE USAGE — Session Validation (Workflow 6, 7)
# ===========================================================================

class ReceivePhoneUsageTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse("receive_phone_usage")

    @patch("home.views.detect_alert_condition", return_value=None)
    @patch("home.views.firebase_push")
    @patch("home.views.firebase_get")
    def test_valid_usage_stored(self, mock_get, mock_push, mock_alert):
        """WF6: Valid usage for active session is stored in Firebase."""
        mock_get.return_value = ACTIVE_SESSION  # session is active
        mock_push.return_value = make_push_mock("USAGE001")

        payload = {
            "session_id": FAKE_SESSION_ID,
            "student_id": FAKE_STUDENT_ID,
            "app_name": "WhatsApp",
            "package_name": "com.whatsapp",
            "category": "non-educational",
            "confidence": 0.95,
            "duration": 120,
        }
        resp = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get("success"))

        push_paths = [str(c[0][0]) for c in mock_push.call_args_list]
        self.assertTrue(
            any(f"phone_usage/{FAKE_SESSION_ID}" in p for p in push_paths),
            msg=f"Usage must be stored under phone_usage/session. Calls: {push_paths}"
        )

    @patch("home.views.firebase_get", return_value=None)
    def test_unknown_session_id_rejected(self, mock_get):
        """WF7: Usage for non-existent session_id must return 400."""
        payload = {
            "session_id": "BOGUS_SESSION",
            "student_id": FAKE_STUDENT_ID,
            "app_name": "TestApp",
            "package_name": "com.test",
            "category": "non-educational",
            "confidence": 0.9,
            "duration": 60,
        }
        resp = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertFalse(data.get("success"))

    @patch("home.views.firebase_get")
    def test_inactive_session_rejected(self, mock_get):
        """WF7: Usage for a stopped/inactive session must return 400."""
        mock_get.return_value = INACTIVE_SESSION
        payload = {
            "session_id": FAKE_SESSION_ID,
            "student_id": FAKE_STUDENT_ID,
            "app_name": "Instagram",
            "package_name": "com.instagram.android",
            "category": "non-educational",
            "confidence": 0.9,
            "duration": 200,
        }
        resp = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_missing_fields_rejected(self):
        """WF6: Missing required fields must return 400."""
        resp = self.client.post(
            self.url,
            data=json.dumps({"session_id": FAKE_SESSION_ID}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_non_json_body_rejected(self):
        """WF6: Non-JSON body must return 500 (or 400)."""
        resp = self.client.post(
            self.url,
            data="not json",
            content_type="text/plain",
        )
        self.assertIn(resp.status_code, [400, 500])


# ===========================================================================
# 10. ALERT DETECTION (Workflow 8)
# ===========================================================================

class AlertDetectionTests(TestCase):
    """Test the alert_utils functions directly — no Firebase needed."""

    def test_calculate_severity_low(self):
        from home.alert_utils import calculate_alert_severity
        self.assertEqual(calculate_alert_severity({"duration": 30}), "Low")

    def test_calculate_severity_medium(self):
        from home.alert_utils import calculate_alert_severity
        self.assertEqual(calculate_alert_severity({"duration": 120}), "Medium")

    def test_calculate_severity_high(self):
        from home.alert_utils import calculate_alert_severity
        self.assertEqual(calculate_alert_severity({"duration": 300}), "High")

    def test_calculate_severity_bad_input(self):
        from home.alert_utils import calculate_alert_severity
        self.assertEqual(calculate_alert_severity({"duration": "bad"}), "Low")
        self.assertEqual(calculate_alert_severity({}), "Low")
        self.assertEqual(calculate_alert_severity(None), "Low")

    def test_detect_alert_non_educational(self):
        from home.alert_utils import detect_alert_condition
        usage = {
            "student_id": FAKE_STUDENT_ID,
            "app_name": "Instagram",
            "package_name": "com.instagram.android",
            "category": "non-educational",
            "duration": 120,
        }
        result = detect_alert_condition(usage)
        self.assertIsNotNone(result, "Non-educational usage should trigger alert condition")

    def test_detect_alert_educational_no_alert(self):
        from home.alert_utils import detect_alert_condition
        usage = {
            "student_id": FAKE_STUDENT_ID,
            "app_name": "Khan Academy",
            "package_name": "org.khanacademy.android",
            "category": "educational",
            "duration": 300,
        }
        result = detect_alert_condition(usage)
        self.assertIsNone(result, "Educational usage must NOT trigger an alert")


# ===========================================================================
# 11. QR CODE GENERATION (Workflow 5)
# ===========================================================================

class QRCodeGenerationTests(TestCase):

    def test_generate_qr_b64_returns_valid_png(self):
        import base64
        from home.views import generate_qr_b64
        result = generate_qr_b64("TEST_SESSION_12345")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)
        decoded = base64.b64decode(result)
        self.assertEqual(decoded[:4], b'\x89PNG',
                         msg="QR output must be a valid PNG")

    def test_generate_qr_b64_different_ids_differ(self):
        from home.views import generate_qr_b64
        qr1 = generate_qr_b64("SESSION_A")
        qr2 = generate_qr_b64("SESSION_B")
        self.assertNotEqual(qr1, qr2,
                            msg="Different session IDs must produce different QR codes")


# ===========================================================================
# 12. FOCUS SCORE CALCULATION
# ===========================================================================

class FocusScoreTests(TestCase):

    def _compute_score(self, edu, non_edu):
        total = edu + non_edu
        if total == 0:
            return None
        return round(max(0.0, min(100.0, (edu / total) * 100)), 1)

    def test_fully_focused(self):
        self.assertEqual(self._compute_score(100, 0), 100.0)

    def test_no_focus(self):
        self.assertEqual(self._compute_score(0, 100), 0.0)

    def test_mixed(self):
        score = self._compute_score(75, 25)
        self.assertEqual(score, 75.0)

    def test_no_data(self):
        self.assertIsNone(self._compute_score(0, 0))


# ===========================================================================
# 13. DEVICE REGISTRATION (Workflow 9)
# ===========================================================================

class DeviceRegistrationTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username=FAKE_STUDENT_ID,
            password="pass123",
            first_name="Test Student",
        )
        self.client.login(username=FAKE_STUDENT_ID, password="pass123")

    @patch("home.views.firebase_set", return_value=None)
    @patch("home.views.firebase_get", return_value=None)
    def test_register_device_creates_pairing_code(self, mock_get, mock_set):
        """WF9: Device registration generates and stores a pairing_code."""
        resp = self.client.post(reverse("register_device"), {
            "student_name": "Test Student",
            "register_number": FAKE_STUDENT_ID,
            "device_name": "Pixel 7",
            "imei_number": "123456789012345",
            "android_version": "14",
        })
        # Must redirect after registration
        self.assertEqual(resp.status_code, 302)

        # firebase_set must have been called with pairing_code
        set_calls = mock_set.call_args_list
        device_data = None
        for c in set_calls:
            if "devices" in str(c[0][0]):
                device_data = c[0][1]
                break
        self.assertIsNotNone(device_data, "Device data must be written to Firebase")
        self.assertIn("pairing_code", device_data,
                      msg="Device record must include pairing_code")
        self.assertTrue(len(str(device_data["pairing_code"])) >= 6,
                        msg="Pairing code must be at least 6 characters")

    @patch("home.views.firebase_set", return_value=None)
    @patch("home.views.firebase_get", return_value=None)
    def test_register_device_accepts_uppercase_register_number(self, mock_get, mock_set):
        """Case-insensitivity: Submitting UPPERCASE student ID matching lowercase username must succeed."""
        resp = self.client.post(reverse("register_device"), {
            "student_name": "Test Student",
            "register_number": FAKE_STUDENT_ID.upper(),
            "device_name": "Samsung Galaxy",
            "imei_number": "987654321098765",
            "android_version": "15",
        })
        self.assertEqual(resp.status_code, 302)
        mock_set.assert_called()

    @patch("home.views.firebase_set", return_value=None)
    @patch("home.views.firebase_get", return_value=None)
    def test_register_device_accepts_whitespace_around_register_number(self, mock_get, mock_set):
        """Whitespace handling: Leading/trailing whitespace should be stripped and accepted."""
        resp = self.client.post(reverse("register_device"), {
            "student_name": "Test Student",
            "register_number": f"  {FAKE_STUDENT_ID}  ",
            "device_name": "OnePlus 12",
            "imei_number": "111222333444555",
            "android_version": "14",
        })
        self.assertEqual(resp.status_code, 302)
        mock_set.assert_called()

    @patch("home.views.firebase_set", return_value=None)
    @patch("home.views.firebase_get", return_value=None)
    def test_register_device_rejects_mismatched_student_id(self, mock_get, mock_set):
        """Ownership validation: Student cannot register a device using another student's ID."""
        resp = self.client.post(reverse("register_device"), {
            "student_name": "Attacker",
            "register_number": "other_student_999",
            "device_name": "Hacked Device",
            "imei_number": "999999999999999",
            "android_version": "14",
        })
        # Must re-render the form with error, not redirect
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Register number must match your logged-in Student ID.")
        mock_set.assert_not_called()

    @patch("home.views.firebase_set", return_value=None)
    @patch("home.views.firebase_get", return_value={"device_name": "Existing Phone"})
    def test_register_device_rejects_already_registered_device(self, mock_get, mock_set):
        """Duplicate prevention: Cannot register a second device if one is already registered."""
        resp = self.client.post(reverse("register_device"), {
            "student_name": "Test Student",
            "register_number": FAKE_STUDENT_ID,
            "device_name": "Second Device",
            "imei_number": "123456789012345",
            "android_version": "14",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "A device is already registered for this student ID.")
        mock_set.assert_not_called()

    @patch("home.views.firebase_get", return_value=None)
    def test_register_device_get_provides_prefilled_context(self, mock_get):
        """Form UX: GET request must provide student_name and student_id in context."""
        resp = self.client.get(reverse("register_device"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("student_id", resp.context)
        self.assertEqual(resp.context["student_id"], FAKE_STUDENT_ID)

    @patch("home.views.firebase_get")
    def test_teacher_blocked_from_device_registration(self, mock_get):
        """Role guard: An approved teacher cannot register devices; redirected with clear message."""
        mock_get.return_value = {
            "test_teacher": {"status": "approved", "role": "teacher"}
        }
        teacher = User.objects.create_user(username="test_teacher", password="teachpass123")
        self.client.login(username="test_teacher", password="teachpass123")
        session = self.client.session
        session["role"] = "teacher"
        session.save()

        resp = self.client.get(reverse("register_device"))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("teacher_dashboard"), fetch_redirect_response=False)
        msgs = [str(m) for m in resp.wsgi_request._messages]
        self.assertTrue(any("Access denied" in m and "teacher" in m for m in msgs),
                        msg=f"Expected teacher access denied message, got: {msgs}")

    @patch("home.views.firebase_get", return_value=None)
    def test_admin_blocked_from_device_registration(self, mock_get):
        """Role guard: Administrator cannot register devices; redirected with clear message."""
        admin = User.objects.create_superuser(username="admin_user", password="adminpass123")
        self.client.login(username="admin_user", password="adminpass123")
        session = self.client.session
        session["role"] = "admin"
        session.save()

        resp = self.client.get(reverse("register_device"))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("admin_dashboard"), fetch_redirect_response=False)
        msgs = [str(m) for m in resp.wsgi_request._messages]
        self.assertTrue(any("Access denied" in m and "administrator" in m for m in msgs),
                        msg=f"Expected admin access denied message, got: {msgs}")


# ===========================================================================
# 14. PASSWORD RESET AVAILABILITY (Workflow 9)
# ===========================================================================

class PasswordResetTests(TestCase):

    def test_password_reset_page_loads(self):
        resp = self.client.get(reverse("password_reset"))
        self.assertEqual(resp.status_code, 200)

    def test_password_reset_done_page_loads(self):
        resp = self.client.get(reverse("password_reset_done"))
        self.assertEqual(resp.status_code, 200)

    def test_password_reset_complete_page_loads(self):
        resp = self.client.get(reverse("password_reset_complete"))
        self.assertEqual(resp.status_code, 200)

    def test_email_backend_is_console(self):
        """
        WF9: Confirm email backend is console-only (dev mode).
        Password reset emails will appear in the server console, not delivered.
        """
        from django.conf import settings
        backend_name = str(settings.EMAIL_BACKEND).lower()
        self.assertTrue(
            "console" in backend_name or "locmem" in backend_name,
            msg=f"EMAIL_BACKEND must be console (or locmem during tests). Got: {backend_name}"
        )


# ===========================================================================
# 15. AI / ML STATUS (Workflow 10)
# ===========================================================================

class AIMLStatusTests(TestCase):

    def test_model_file_exists(self):
        import pathlib
        from django.conf import settings
        p = pathlib.Path(settings.BASE_DIR) / "focus_model_demo.joblib"
        if not p.exists():
            p = pathlib.Path(r"D:\Binitta\mobile_monitoring\focus_model_demo.joblib")
        self.assertTrue(p.exists(), "Model file focus_model_demo.joblib must exist")

    def test_ai_model_module_imports_safely_without_sklearn(self):
        """
        WF10: ai_model.py must never crash at import time even when
        scikit-learn / pandas are missing.
        """
        import importlib
        try:
            import home.ai_model as ai_mod
            importlib.reload(ai_mod)   # force re-import
            # If we get here without exception, import is safe
        except ImportError as e:
            self.fail(f"ai_model.py crashed on import: {e}")

    def test_predict_focus_raises_runtime_error_without_sklearn(self):
        """
        WF10: Without sklearn, predict_focus must raise RuntimeError
        (so callers can catch it), NOT crash the process.
        """
        try:
            import sklearn
            self.skipTest("sklearn is installed — skipping missing-deps test")
        except ImportError:
            pass

        from home.ai_model import predict_focus
        with self.assertRaises(RuntimeError,
                               msg="predict_focus must raise RuntimeError when deps missing"):
            predict_focus(120, True)

    def test_receive_phone_usage_works_without_ml(self):
        """
        WF10: receive_phone_usage must still return 200 even when ML is unavailable.
        """
        with patch("home.views.firebase_get", return_value=ACTIVE_SESSION), \
             patch("home.views.detect_alert_condition", return_value=None), \
             patch("home.views.firebase_push", return_value=make_push_mock()):
            payload = {
                "session_id": FAKE_SESSION_ID,
                "student_id": FAKE_STUDENT_ID,
                "app_name": "TestApp",
                "package_name": "com.test.app",
                "category": "non-educational",
                "confidence": 0.8,
                "duration": 90,
            }
            resp = self.client.post(
                reverse("receive_phone_usage"),
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 200,
                             msg="API must work even without ML dependencies")


# ===========================================================================
# 16. SPRINT 5 - REPORTS & ANALYTICS TESTS (T1 - T7)
# ===========================================================================

class Sprint5ReportsTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username=FAKE_TEACHER_ID,
            password="TestPassword123!",
            email="teacher@test.com"
        )
        self.client.login(username=FAKE_TEACHER_ID, password="TestPassword123!")
        session = self.client.session
        session["role"] = "teacher"
        session.save()

    @patch("home.views.firebase_get")
    def test_reports_analytics_page_renders(self, mock_fb):
        """T1 & T6: Reports & analytics dashboard page loads with status 200."""
        def fake_get(path):
            if path == "classroom_sessions":
                return {FAKE_SESSION_ID: ACTIVE_SESSION}
            if path == "phone_usage":
                return {
                    FAKE_SESSION_ID: {
                        "usage_1": {
                            "student_id": FAKE_STUDENT_ID,
                            "app_name": "Google Docs",
                            "category": "Educational",
                            "duration": 120,
                            "timestamp": 1792085935642
                        }
                    }
                }
            if path == "attendance":
                return {
                    "att_1": {
                        "student_id": FAKE_STUDENT_ID,
                        "student_name": "Test Student",
                        "classroom": "CS-402 Test Class",
                        "date": "2026-10-22",
                        "time": "09:05:00",
                        "status": "Present"
                    }
                }
            return {}

        mock_fb.side_effect = fake_get

        resp = self.client.get(reverse("reports_analytics"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Reports &amp; Analytics")
        self.assertIn("attendance_records", resp.context)
        self.assertIn("usage_records", resp.context)
        self.assertIn("student_focus_reports", resp.context)

    @patch("home.views.firebase_get")
    def test_export_attendance_csv(self, mock_fb):
        """T2 & T7: Export Attendance Report CSV returns valid CSV."""
        mock_fb.return_value = {
            "att_1": {
                "student_id": FAKE_STUDENT_ID,
                "student_name": "Test Student",
                "classroom": "CS-402",
                "session_id": FAKE_SESSION_ID,
                "date": "2026-10-22",
                "time": "09:05:00",
                "status": "Present"
            }
        }
        resp = self.client.get(reverse("export_attendance_csv"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("attachment; filename=\"focusframe_attendance_report.csv\"", resp["Content-Disposition"])
        content = resp.content.decode("utf-8")
        self.assertIn("Student ID,Student Name,Classroom", content)
        self.assertIn(FAKE_STUDENT_ID, content)

    @patch("home.views.firebase_get")
    def test_export_usage_csv(self, mock_fb):
        """T3 & T7: Export Phone Usage Report CSV returns valid CSV."""
        def fake_get(path):
            if path == "phone_usage":
                return {
                    FAKE_SESSION_ID: {
                        "u1": {
                            "student_id": FAKE_STUDENT_ID,
                            "app_name": "Calculator",
                            "package_name": "com.calc",
                            "category": "Educational",
                            "duration": 60,
                            "timestamp": 1792085935642
                        }
                    }
                }
            return {}
        mock_fb.side_effect = fake_get

        resp = self.client.get(reverse("export_usage_csv"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("focusframe_phone_usage_report.csv", resp["Content-Disposition"])
        content = resp.content.decode("utf-8")
        self.assertIn("Student ID,Classroom,Session ID,App Name", content)
        self.assertIn("Calculator", content)

    @patch("home.views.firebase_get")
    def test_export_focus_csv(self, mock_fb):
        """T4 & T7: Export Student Focus Scores CSV returns valid CSV."""
        def fake_get(path):
            if path == "phone_usage":
                return {
                    FAKE_SESSION_ID: {
                        "u1": {
                            "student_id": FAKE_STUDENT_ID,
                            "app_name": "Calculator",
                            "package_name": "com.calc",
                            "category": "Educational",
                            "duration": 100,
                            "timestamp": 1792085935642
                        }
                    }
                }
            return {}
        mock_fb.side_effect = fake_get

        resp = self.client.get(reverse("export_focus_csv"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("focusframe_focus_scores_report.csv", resp["Content-Disposition"])
        content = resp.content.decode("utf-8")
        self.assertIn("Focus Score (%),Focus Level", content)
        self.assertIn("Focused", content)


# ===========================================================================
# 16. TEACHER DASHBOARD REGRESSION TESTS
# ===========================================================================

class TeacherDashboardRegressionTests(TestCase):
    """
    Regression tests for confirmed Teacher Dashboard fixes:
      1. Attendance count scoped to active session and registered students.
      2. Incomplete phone usage records (e.g. focus_summary) excluded.
      3. Focus score rendered consistently with one decimal place (3.6%) in both tables.
    """

    def setUp(self):
        self.client = Client()
        self.teacher_user = User.objects.create_user(
            username="dash_teacher_1",
            password="teachpass123",
            first_name="Teacher",
            last_name="One"
        )
        self.client.login(username="dash_teacher_1", password="teachpass123")
        session = self.client.session
        session["role"] = "teacher"
        session["monitoring_active"] = True
        session["session_id"] = "SESS_ACTIVE_001"
        session["active_class"] = "CS-402 Mobile Computing"
        session["session_time"] = "09:00 AM"
        session.save()

    @patch("home.views.firebase_get")
    def test_attendance_count_scoped_to_active_session_and_registered_students(self, mock_fb):
        """
        Attendance must only count registered students checked into the active session.
        Historical sessions, teacher scans, and unregistered test accounts must be excluded.
        """
        def fake_get(path):
            if path == "users":
                return {
                    "reg_student_1": {"role": "student", "full_name": "Registered Student 1", "email": "s1@test.com"},
                    "reg_student_2": {"role": "student", "full_name": "Registered Student 2", "email": "s2@test.com"},
                    "dash_teacher_1": {"role": "teacher", "full_name": "Teacher One", "email": "t1@test.com"}
                }
            elif path == "devices":
                return {}
            elif path == "attendance":
                return {
                    # 1. Registered student in active session -> MUST COUNT
                    "att_valid": {
                        "student_id": "reg_student_1",
                        "session_id": "SESS_ACTIVE_001",
                        "status": "Present"
                    },
                    # 2. Registered student in past/different session -> MUST NOT COUNT
                    "att_historical": {
                        "student_id": "reg_student_2",
                        "session_id": "SESS_OLD_999",
                        "status": "Present"
                    },
                    # 3. Unregistered student ID in active session -> MUST NOT COUNT
                    "att_unregistered": {
                        "student_id": "ghost_student_3",
                        "session_id": "SESS_ACTIVE_001",
                        "status": "Present"
                    },
                    # 4. Teacher self-scan in active session -> MUST NOT COUNT
                    "att_teacher": {
                        "student_id": "dash_teacher_1",
                        "session_id": "SESS_ACTIVE_001",
                        "status": "Present"
                    },
                    # 5. Absent record in active session -> MUST NOT COUNT
                    "att_absent": {
                        "student_id": "reg_student_1",
                        "session_id": "SESS_ACTIVE_001",
                        "status": "Absent"
                    }
                }
            elif path == "classroom_sessions":
                return {
                    "SESS_ACTIVE_001": {
                        "teacher_id": "dash_teacher_1",
                        "active": True,
                        "classroom": "CS-402 Mobile Computing",
                        "session_time": "09:00 AM"
                    }
                }
            elif path == "phone_usage/SESS_ACTIVE_001":
                return {}
            elif path == "alerts/SESS_ACTIVE_001":
                return {}
            return {}

        mock_fb.side_effect = fake_get

        resp = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(resp.status_code, 200)

        # Context checks:
        # Enrolled students = 2
        self.assertEqual(resp.context["total_students"], 2)
        # Present students must be 1 (only reg_student_1 in SESS_ACTIVE_001)
        self.assertEqual(resp.context["present_students"], 1)

        monitoring_data = {s["student_id"]: s for s in resp.context["student_monitoring"]}
        self.assertTrue(monitoring_data["reg_student_1"]["is_present"])
        self.assertFalse(monitoring_data["reg_student_2"]["is_present"])

    @patch("home.views.firebase_get")
    def test_phone_usage_excludes_focus_summary_and_missing_app_name(self, mock_fb):
        """
        Phone usage table must retain valid app usage records and exclude non-event
        metadata dictionaries like focus_summary or records missing app_name.
        """
        def fake_get(path):
            if path == "users":
                return {
                    "reg_student_1": {"role": "student", "full_name": "Student 1", "email": "s1@test.com"}
                }
            elif path == "devices":
                return {}
            elif path == "attendance":
                return {}
            elif path == "classroom_sessions":
                return {
                    "SESS_ACTIVE_001": {
                        "teacher_id": "dash_teacher_1",
                        "active": True,
                        "classroom": "CS-402 Mobile Computing",
                        "session_time": "09:00 AM"
                    }
                }
            elif path == "phone_usage/SESS_ACTIVE_001":
                return {
                    "event_1": {
                        "student_id": "reg_student_1",
                        "app_name": "Google Docs",
                        "package_name": "com.google.android.apps.docs",
                        "category": "Educational",
                        "duration": 45,
                        "timestamp": 1793000000000
                    },
                    "event_2": {
                        "student_id": "reg_student_1",
                        "app_name": "Instagram",
                        "package_name": "com.instagram.android",
                        "category": "Non-Educational",
                        "duration": 120,
                        "timestamp": 1793000010000
                    },
                    "focus_summary": {
                        "reg_student_1": {
                            "educational_minutes": 1,
                            "non_educational_minutes": 2,
                            "focus_score": 33
                        }
                    },
                    "empty_app_event": {
                        "student_id": "reg_student_1",
                        "duration": 10,
                        "timestamp": 1793000020000
                    }
                }
            elif path == "alerts/SESS_ACTIVE_001":
                return {}
            return {}

        mock_fb.side_effect = fake_get

        resp = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(resp.status_code, 200)

        usage_records = resp.context["phone_usage_records"]
        # Exactly two valid app events
        self.assertEqual(len(usage_records), 2)
        record_ids = [r.get("id") for r in usage_records]
        self.assertIn("event_1", record_ids)
        self.assertIn("event_2", record_ids)
        self.assertNotIn("focus_summary", record_ids)
        self.assertNotIn("empty_app_event", record_ids)
        for r in usage_records:
            self.assertTrue(bool(r.get("app_name")))

    @patch("home.views.firebase_get")
    def test_focus_score_renders_consistently_with_one_decimal_in_both_tables(self, mock_fb):
        """
        A focus score of 3.6 must display as '3.6%' in both the Live Monitoring table
        and the Focus Score Analysis table, rather than rounding to '4%' in one table.
        """
        def fake_get(path):
            if path == "users":
                return {
                    "binitta_id": {"role": "student", "full_name": "Binitta", "email": "binitta@test.com"}
                }
            elif path == "devices":
                return {}
            elif path == "attendance":
                return {
                    "att_1": {"student_id": "binitta_id", "session_id": "SESS_ACTIVE_001", "status": "Present"}
                }
            elif path == "classroom_sessions":
                return {
                    "SESS_ACTIVE_001": {
                        "teacher_id": "dash_teacher_1",
                        "active": True,
                        "classroom": "CS-402 Mobile Computing",
                        "session_time": "09:00 AM"
                    }
                }
            elif path == "phone_usage/SESS_ACTIVE_001":
                # 12 sec Educational out of 333 sec total -> exactly 3.6%
                return {
                    "ev1": {
                        "student_id": "binitta_id",
                        "app_name": "Sheets",
                        "category": "Educational",
                        "duration": 12,
                        "timestamp": 1793000000000
                    },
                    "ev2": {
                        "student_id": "binitta_id",
                        "app_name": "Instagram",
                        "category": "Non-Educational",
                        "duration": 321,
                        "timestamp": 1793000010000
                    }
                }
            elif path == "alerts/SESS_ACTIVE_001":
                return {}
            return {}

        mock_fb.side_effect = fake_get

        resp = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(resp.status_code, 200)

        # In context, student focus score must be 3.6
        student_data = resp.context["student_monitoring"][0]
        self.assertEqual(student_data["focus_score"], 3.6)

        html = resp.content.decode("utf-8")
        # Must display 3.6%
        self.assertIn("3.6%", html)
        # Must not display 4% as the badge text
        self.assertNotIn(">4%<", html)
        self.assertNotIn("> 4%<", html)

    @patch("home.views.firebase_get")
    def test_active_session_zero_attendance_when_no_records_for_active_session(self, mock_fb):
        """
        When students are enrolled but have not checked into the current active session,
        present_students must be 0 and is_present must be False for all students.
        """
        def fake_get(path):
            if path == "users":
                return {
                    "stu_1": {"role": "student", "full_name": "Student One", "email": "s1@test.com"},
                    "stu_2": {"role": "student", "full_name": "Student Two", "email": "s2@test.com"},
                }
            elif path == "devices":
                return {}
            elif path == "attendance":
                # Historical records for other sessions only
                return {
                    "att_old_1": {"student_id": "stu_1", "session_id": "OLD_SESS_A", "status": "Present"},
                    "att_old_2": {"student_id": "stu_2", "session_id": "OLD_SESS_B", "status": "Present"},
                }
            elif path == "classroom_sessions":
                return {
                    "SESS_ACTIVE_001": {
                        "teacher_id": "dash_teacher_1",
                        "active": True,
                        "classroom": "CS-402 Mobile Computing",
                        "session_time": "09:00 AM"
                    }
                }
            return {}

        mock_fb.side_effect = fake_get

        resp = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(resp.status_code, 200)

        # Enrolled = 2, Present in this session = 0
        self.assertEqual(resp.context["total_students"], 2)
        self.assertEqual(resp.context["present_students"], 0)
        for s in resp.context["student_monitoring"]:
            self.assertFalse(s["is_present"])

    @patch("home.views.firebase_push")
    @patch("home.views.firebase_get")
    def test_scan_qr_stores_correct_session_id_and_registered_student_id(self, mock_get, mock_push):
        """
        A successful QR scan stores the active session_id, student_id, and status=Present.
        """
        student_user = User.objects.create_user(username="role_student", password="pass123")
        self.client.login(username="role_student", password="pass123")
        session = self.client.session
        session["role"] = "student"
        session.save()

        def fake_get(path):
            if path == "classroom_sessions/SESS_ACTIVE_001":
                return {
                    "classroom": "CS-402 Mobile Computing",
                    "active": True,
                    "teacher_id": "dash_teacher_1"
                }
            elif path == "attendance":
                return {}
            return {}

        mock_get.side_effect = fake_get

        resp = self.client.post(
            reverse("scan_qr"),
            {"classroom": "SESS_ACTIVE_001"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])

        # Check what was pushed to attendance
        mock_push.assert_called_once()
        push_path, push_data = mock_push.call_args[0]
        self.assertEqual(push_path, "attendance")
        self.assertEqual(push_data["student_id"], "role_student")
        self.assertEqual(push_data["session_id"], "SESS_ACTIVE_001")
        self.assertEqual(push_data["status"], "Present")

    @patch("home.views.firebase_get")
    def test_duplicate_alerts_deduplicated_preserving_distinct_events(self, mock_fb):
        """
        Duplicate alert entries for the same event (e.g. Instagram 26s) must be deduplicated
        while distinct legitimate alerts (e.g. Instagram 307s) are preserved.
        """
        def fake_get(path):
            if path == "users":
                return {
                    "25mca032": {"role": "student", "full_name": "Binitta", "email": "binitta@test.com"}
                }
            elif path == "devices":
                return {}
            elif path == "attendance":
                return {}
            elif path == "classroom_sessions":
                return {
                    "SESS_ACTIVE_001": {
                        "teacher_id": "dash_teacher_1",
                        "active": True,
                        "classroom": "CS-402 Mobile Computing",
                        "session_time": "09:00 AM"
                    }
                }
            elif path == "phone_usage/SESS_ACTIVE_001":
                return {}
            elif path == "alerts/SESS_ACTIVE_001":
                return {
                    "alt_1": {
                        "student_id": "25mca032",
                        "app_name": "Instagram",
                        "duration": 26,
                        "timestamp": 1793038711430,
                        "source_usage_id": "-P4tQrpkw0iOeJHJmD3n",
                        "severity": "Medium"
                    },
                    # Duplicate entry for same event
                    "alt_2": {
                        "student_id": "25mca032",
                        "app_name": "Instagram",
                        "duration": 26,
                        "timestamp": 1793038711430,
                        "source_usage_id": "-P4tQrpkw0iOeJHJmD3n",
                        "severity": "Medium"
                    },
                    # Distinct legitimate event
                    "alt_3": {
                        "student_id": "25mca032",
                        "app_name": "Instagram",
                        "duration": 307,
                        "timestamp": 1793038359691,
                        "source_usage_id": "-P4tPWxcx2SlwapLceOD",
                        "severity": "High"
                    }
                }
            return {}

        mock_fb.side_effect = fake_get

        resp = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(resp.status_code, 200)

        alert_records = resp.context["alert_records"]
        # Exactly 2 unique alerts (duplicate alt_2 stripped)
        self.assertEqual(len(alert_records), 2)
        durations = [a["duration"] for a in alert_records]
        self.assertEqual(durations.count(26), 1)
        self.assertEqual(durations.count(307), 1)

    @patch("home.alert_utils.db.reference")
    def test_store_alert_is_idempotent(self, mock_db_ref):
        """
        Calling store_alert twice with the same event data returns the existing key
        and does not push a duplicate to Firebase.
        """
        from home.alert_utils import store_alert

        mock_ref = MagicMock()
        # First call: no existing alerts
        mock_ref.get.return_value = {
            "existing_alert_1": {
                "source_usage_id": "usage_event_abc",
                "student_id": "stu_1",
                "app_name": "Instagram",
                "timestamp": "1793000000",
                "duration": 26
            }
        }
        mock_db_ref.return_value = mock_ref

        # Second call with same source_usage_id
        res = store_alert("SESS_ACTIVE_001", {
            "source_usage_id": "usage_event_abc",
            "student_id": "stu_1",
            "app_name": "Instagram",
            "timestamp": "1793000000",
            "duration": 26
        })
        self.assertEqual(res, "existing_alert_1")
        # Ensure push was not called again
        mock_ref.push.assert_not_called()

    @patch("home.views.firebase_get")
    def test_ml_prediction_clarity_for_short_non_educational_event(self, mock_fb):
        """
        Verifies that a 12-second non-educational event renders with honest demo model badge
        and explanatory guidance distinguishing event-level thresholds from session focus scores.
        """
        def fake_get(path):
            if path == "users":
                return {
                    "25mca032": {"role": "student", "full_name": "Binitta", "email": "binitta@test.com"}
                }
            elif path == "devices":
                return {}
            elif path == "attendance":
                return {}
            elif path == "classroom_sessions":
                return {
                    "SESS_ACTIVE_001": {
                        "teacher_id": "dash_teacher_1",
                        "active": True,
                        "classroom": "CS-402 Mobile Computing",
                        "session_time": "09:00 AM"
                    }
                }
            elif path == "phone_usage/SESS_ACTIVE_001":
                return {
                    "ev1": {
                        "student_id": "25mca032",
                        "app_name": "Instagram",
                        "package_name": "com.instagram.android",
                        "category": "Non-Educational",
                        "duration": 12,
                        "timestamp": 1793038571144
                    }
                }
            elif path == "alerts/SESS_ACTIVE_001":
                return {}
            return {}

        mock_fb.side_effect = fake_get

        resp = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(resp.status_code, 200)

        html = resp.content.decode("utf-8")
        # Demonstrates honest demo model labeling with event threshold
        self.assertIn("Demo Model (Event Threshold)", html)
        # Demonstrates explanation banner
        self.assertIn("Understanding Event ML Predictions vs. Session Focus Scores", html)


# ===========================================================================
# 20. MULTI-SESSION ISOLATION & QR ATTENDANCE TESTS
# ===========================================================================

class MultiSessionIsolationAndAttendanceTests(TestCase):
    """
    Automated verification of all per-session QR attendance and data isolation requirements:
    1. Teacher starts Session 1 and students scan its QR code.
    2. The same teacher stops Session 1 and starts Session 2 with a new unique session ID.
    3. Students who attended Session 1 must scan the new QR code to become present in Session 2.
    4. A student who does not scan Session 2 must not automatically be marked present.
    5. Scanning the same QR code repeatedly must not create duplicate attendance records.
    6. Session 1 attendance and usage data remain unchanged after Session 2 starts.
    7. Phone-usage events from Session 2 are not stored under Session 1 (and stale events rejected).
    8. Refreshing the teacher dashboard does not create duplicate sessions, attendance records, or alerts.
    9. Starting and stopping monitoring continues to work correctly.
    """

    def setUp(self):
        super().setUp()
        self.teacher_user = User.objects.create_user(
            username="teacher_multi",
            first_name="Multi",
            last_name="Teacher",
            password="testpassword123"
        )
        self.student_alice = User.objects.create_user(
            username="alice_student",
            first_name="Alice",
            last_name="Student",
            password="testpassword123"
        )
        self.student_bob = User.objects.create_user(
            username="bob_student",
            first_name="Bob",
            last_name="Student",
            password="testpassword123"
        )

        self.db_state = {
            "users": {
                "alice_student": {
                    "role": "student",
                    "full_name": "Alice Student",
                    "email": "alice@test.com"
                },
                "bob_student": {
                    "role": "student",
                    "full_name": "Bob Student",
                    "email": "bob@test.com"
                },
                "teacher_multi": {
                    "role": "teacher",
                    "full_name": "Multi Teacher",
                    "email": "teacher@test.com"
                }
            },
            "teacher_requests": {
                "teacher_multi": {
                    "teacher_id": "teacher_multi",
                    "status": "Approved"
                }
            },
            "devices": {
                "alice_student": {
                    "register_number": "alice_student",
                    "device_name": "Alice Phone"
                },
                "bob_student": {
                    "register_number": "bob_student",
                    "device_name": "Bob Phone"
                }
            },
            "classroom_sessions": {},
            "attendance": {},
            "phone_usage": {},
            "alerts": {},
        }
        self.push_counter = 0

    def _login_teacher(self):
        self.client.force_login(self.teacher_user)
        s = self.client.session
        s["role"] = "teacher"
        s.save()

    def _login_student(self, student_user):
        self.client.force_login(student_user)
        s = self.client.session
        s["role"] = "student"
        s.save()

    def _stateful_get(self, path):
        import copy
        parts = path.strip("/").split("/")
        curr = self.db_state
        for p in parts:
            if not isinstance(curr, dict) or p not in curr:
                return {}
            curr = curr[p]
        return copy.deepcopy(curr)

    def _stateful_set(self, path, data):
        import copy
        parts = path.strip("/").split("/")
        curr = self.db_state
        for p in parts[:-1]:
            if p not in curr or not isinstance(curr[p], dict):
                curr[p] = {}
            curr = curr[p]
        curr[parts[-1]] = copy.deepcopy(data)

    def _stateful_update(self, path, data):
        parts = path.strip("/").split("/")
        curr = self.db_state
        for p in parts:
            if p not in curr or not isinstance(curr[p], dict):
                curr[p] = {}
            curr = curr[p]
        curr.update(data)

    def _stateful_push(self, path, data):
        import copy
        self.push_counter += 1
        key = f"PUSH_{self.push_counter:04d}"
        parts = path.strip("/").split("/")
        curr = self.db_state
        for p in parts:
            if p not in curr or not isinstance(curr[p], dict):
                curr[p] = {}
            curr = curr[p]
        curr[key] = copy.deepcopy(data)
        mock_ref = MagicMock()
        mock_ref.key = key
        return mock_ref

    def _stateful_store_alert(self, session_id, alert_data):
        import copy
        if session_id not in self.db_state["alerts"]:
            self.db_state["alerts"][session_id] = {}
        src_id = alert_data.get("source_usage_id")
        for k, v in self.db_state["alerts"][session_id].items():
            if src_id and v.get("source_usage_id") == src_id:
                return k
        key = f"ALERT_{len(self.db_state['alerts'][session_id]) + 1}"
        self.db_state["alerts"][session_id][key] = copy.deepcopy(alert_data)
        return key

    @patch("home.views.store_alert")
    @patch("home.views.firebase_get")
    @patch("home.views.firebase_set")
    @patch("home.views.firebase_push")
    @patch("home.views.firebase_update")
    def test_scenario_1_teacher_starts_session1_and_student_scans_qr(self, m_upd, m_push, m_set, m_get, m_store_alert):
        """Scenario 1: Teacher starts Session 1 with unique ID and QR, Alice scans and is marked present."""
        m_get.side_effect = self._stateful_get
        m_set.side_effect = self._stateful_set
        m_push.side_effect = self._stateful_push
        m_upd.side_effect = self._stateful_update
        m_store_alert.side_effect = self._stateful_store_alert

        # Teacher starts Session 1
        self._login_teacher()
        resp = self.client.post(reverse("start_monitoring"), {"classroom_name": "CS-402 Session 1"})
        self.assertEqual(resp.status_code, 302)
        sess_1_id = self.client.session.get("session_id")
        self.assertTrue(sess_1_id)
        self.assertTrue(self.db_state["classroom_sessions"][sess_1_id]["active"])
        self.assertEqual(self.db_state["classroom_sessions"][sess_1_id]["qr_code"], sess_1_id)

        # Teacher dashboard displays QR code for Session 1
        resp_dash = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(resp_dash.status_code, 200)
        self.assertEqual(resp_dash.context["session_id"], sess_1_id)
        self.assertTrue(bool(resp_dash.context["qr_image_b64"]))
        self.assertEqual(resp_dash.context["present_students"], 0)

        # Alice logs in and scans Session 1 QR
        self._login_student(self.student_alice)
        scan_resp = self.client.post(reverse("scan_qr"), {"classroom": sess_1_id})
        self.assertEqual(scan_resp.status_code, 302)

        # Verify attendance record exists in Firebase with correct session_id
        att_records = self.db_state["attendance"]
        self.assertEqual(len(att_records), 1)
        att_val = list(att_records.values())[0]
        self.assertEqual(att_val["student_id"], "alice_student")
        self.assertEqual(att_val["session_id"], sess_1_id)
        self.assertEqual(att_val["status"], "Present")

        # In teacher dashboard, Alice is Present and Bob is Absent
        self._login_teacher()
        # Restore active session_id in teacher's session
        s = self.client.session
        s["session_id"] = sess_1_id
        s["monitoring_active"] = True
        s.save()

        resp_dash2 = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(resp_dash2.status_code, 200)
        st_map = {s["student_id"]: s for s in resp_dash2.context["student_monitoring"]}
        self.assertTrue(st_map["alice_student"]["is_present"])
        self.assertEqual(st_map["alice_student"]["attendance"], "Present")
        self.assertFalse(st_map["bob_student"]["is_present"])
        self.assertEqual(st_map["bob_student"]["attendance"], "Absent")
        self.assertEqual(resp_dash2.context["present_students"], 1)

    @patch("home.views.store_alert")
    @patch("home.views.firebase_get")
    @patch("home.views.firebase_set")
    @patch("home.views.firebase_push")
    @patch("home.views.firebase_update")
    def test_scenario_2_to_4_multi_session_attendance_requires_new_qr_scan(self, m_upd, m_push, m_set, m_get, m_store_alert):
        """
        Scenarios 2, 3, 4:
        Teacher stops Session 1 and starts Session 2.
        Students from Session 1 are NOT carried forward (Alice is Absent in Session 2 until scanning).
        Student Bob who does not scan remains Absent.
        """
        m_get.side_effect = self._stateful_get
        m_set.side_effect = self._stateful_set
        m_push.side_effect = self._stateful_push
        m_upd.side_effect = self._stateful_update
        m_store_alert.side_effect = self._stateful_store_alert

        # Teacher starts Session 1
        self._login_teacher()
        self.client.post(reverse("start_monitoring"), {"classroom_name": "CS-402 Morning"})
        sess_1_id = self.client.session.get("session_id")

        # Alice scans Session 1
        self._login_student(self.student_alice)
        self.client.post(reverse("scan_qr"), {"classroom": sess_1_id})

        # Teacher stops Session 1
        self._login_teacher()
        s = self.client.session
        s["session_id"] = sess_1_id
        s["monitoring_active"] = True
        s.save()

        stop_resp = self.client.post(reverse("stop_monitoring"))
        self.assertEqual(stop_resp.status_code, 302)
        self.assertFalse(self.db_state["classroom_sessions"][sess_1_id]["active"])
        self.assertTrue(self.db_state["classroom_sessions"][sess_1_id].get("stopped_at"))

        # Teacher starts Session 2
        start2_resp = self.client.post(reverse("start_monitoring"), {"classroom_name": "CS-402 Afternoon"})
        self.assertEqual(start2_resp.status_code, 302)
        sess_2_id = self.client.session.get("session_id")
        self.assertNotEqual(sess_1_id, sess_2_id)
        self.assertTrue(self.db_state["classroom_sessions"][sess_2_id]["active"])

        # Prior session 1 record remains intact in Firebase
        self.assertIn(sess_1_id, self.db_state["classroom_sessions"])
        self.assertFalse(self.db_state["classroom_sessions"][sess_1_id]["active"])

        # Check teacher dashboard immediately after Session 2 starts:
        # Neither Alice nor Bob has scanned Session 2 yet -> BOTH MUST BE ABSENT
        dash_sess2 = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(dash_sess2.status_code, 200)
        st_map = {s["student_id"]: s for s in dash_sess2.context["student_monitoring"]}
        self.assertFalse(st_map["alice_student"]["is_present"], "Attendance from Session 1 must not be carried forward!")
        self.assertEqual(st_map["alice_student"]["attendance"], "Absent")
        self.assertFalse(st_map["bob_student"]["is_present"])
        self.assertEqual(st_map["bob_student"]["attendance"], "Absent")
        self.assertEqual(dash_sess2.context["present_students"], 0)

        # Alice scans Session 2 QR
        self._login_student(self.student_alice)
        scan2_resp = self.client.post(reverse("scan_qr"), {"classroom": sess_2_id})
        self.assertEqual(scan2_resp.status_code, 302)

        # Now Alice is Present in Session 2, but Bob (who never scanned) is still Absent
        self._login_teacher()
        s = self.client.session
        s["session_id"] = sess_2_id
        s["monitoring_active"] = True
        s.save()

        dash_sess2_updated = self.client.get(reverse("teacher_dashboard"))
        st_map2 = {s["student_id"]: s for s in dash_sess2_updated.context["student_monitoring"]}
        self.assertTrue(st_map2["alice_student"]["is_present"])
        self.assertEqual(st_map2["alice_student"]["attendance"], "Present")
        self.assertFalse(st_map2["bob_student"]["is_present"])
        self.assertEqual(st_map2["bob_student"]["attendance"], "Absent")
        self.assertEqual(dash_sess2_updated.context["present_students"], 1)

    @patch("home.views.store_alert")
    @patch("home.views.firebase_get")
    @patch("home.views.firebase_set")
    @patch("home.views.firebase_push")
    @patch("home.views.firebase_update")
    def test_scenario_5_duplicate_qr_scan_rejected(self, m_upd, m_push, m_set, m_get, m_store_alert):
        """Scenario 5: Scanning the same QR code repeatedly must not create duplicate attendance records."""
        m_get.side_effect = self._stateful_get
        m_set.side_effect = self._stateful_set
        m_push.side_effect = self._stateful_push
        m_upd.side_effect = self._stateful_update
        m_store_alert.side_effect = self._stateful_store_alert

        # Teacher starts Session
        self._login_teacher()
        self.client.post(reverse("start_monitoring"), {"classroom_name": "CS-402"})
        sess_id = self.client.session.get("session_id")

        # Alice scans once
        self._login_student(self.student_alice)
        resp1 = self.client.post(reverse("scan_qr"), {"classroom": sess_id}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp1.status_code, 200)
        self.assertTrue(resp1.json()["success"])
        self.assertEqual(len(self.db_state["attendance"]), 1)

        # Alice scans again for the same session
        resp2 = self.client.post(reverse("scan_qr"), {"classroom": sess_id}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp2.status_code, 400)
        self.assertFalse(resp2.json()["success"])
        self.assertIn("already marked attendance", resp2.json()["message"])
        # No extra attendance record added
        self.assertEqual(len(self.db_state["attendance"]), 1)

    @patch("home.views.store_alert")
    @patch("home.views.firebase_get")
    @patch("home.views.firebase_set")
    @patch("home.views.firebase_push")
    @patch("home.views.firebase_update")
    def test_scenario_6_and_7_session_isolation_and_phone_usage(self, m_upd, m_push, m_set, m_get, m_store_alert):
        """
        Scenario 6 & 7:
        Session 1 attendance & usage records remain unchanged after Session 2 starts.
        Phone-usage events from Session 2 are not stored under Session 1.
        Stale/inactive session phone usage is rejected.
        """
        m_get.side_effect = self._stateful_get
        m_set.side_effect = self._stateful_set
        m_push.side_effect = self._stateful_push
        m_upd.side_effect = self._stateful_update
        m_store_alert.side_effect = self._stateful_store_alert

        # Start Session 1
        self._login_teacher()
        self.client.post(reverse("start_monitoring"), {"classroom_name": "CS-402 Session 1"})
        sess_1_id = self.client.session.get("session_id")

        # Alice records usage in Session 1
        usage_s1 = {
            "session_id": sess_1_id,
            "student_id": "alice_student",
            "app_name": "Coursera",
            "package_name": "org.coursera.android",
            "category": "Educational",
            "duration": 180,
            "confidence": 0.95
        }
        res_u1 = self.client.post(
            reverse("receive_phone_usage"),
            data=json.dumps(usage_s1),
            content_type="application/json"
        )
        self.assertEqual(res_u1.status_code, 200)
        self.assertIn(sess_1_id, self.db_state["phone_usage"])
        self.assertEqual(len(self.db_state["phone_usage"][sess_1_id]), 1)

        # Stop Session 1 and Start Session 2
        self.client.post(reverse("stop_monitoring"))
        self.client.post(reverse("start_monitoring"), {"classroom_name": "CS-402 Session 2"})
        sess_2_id = self.client.session.get("session_id")
        self.assertNotEqual(sess_1_id, sess_2_id)

        # Record usage in Session 2
        usage_s2 = {
            "session_id": sess_2_id,
            "student_id": "alice_student",
            "app_name": "Khan Academy",
            "package_name": "org.khanacademy.android",
            "category": "Educational",
            "duration": 240,
            "confidence": 0.98
        }
        res_u2 = self.client.post(
            reverse("receive_phone_usage"),
            data=json.dumps(usage_s2),
            content_type="application/json"
        )
        self.assertEqual(res_u2.status_code, 200)

        # Verify Session 1 usage is completely unchanged
        self.assertEqual(len(self.db_state["phone_usage"][sess_1_id]), 1)
        # Verify Session 2 usage is stored under Session 2 only
        self.assertEqual(len(self.db_state["phone_usage"][sess_2_id]), 1)
        s1_ev = list(self.db_state["phone_usage"][sess_1_id].values())[0]
        s2_ev = list(self.db_state["phone_usage"][sess_2_id].values())[0]
        self.assertEqual(s1_ev["app_name"], "Coursera")
        self.assertEqual(s2_ev["app_name"], "Khan Academy")

        # Attempt to submit phone usage for stopped Session 1 -> MUST BE REJECTED
        res_stale = self.client.post(
            reverse("receive_phone_usage"),
            data=json.dumps(usage_s1),
            content_type="application/json"
        )
        self.assertEqual(res_stale.status_code, 400)
        self.assertIn("no longer active", res_stale.json()["message"])

    @patch("home.views.store_alert")
    @patch("home.views.firebase_get")
    @patch("home.views.firebase_set")
    @patch("home.views.firebase_push")
    @patch("home.views.firebase_update")
    def test_scenario_8_dashboard_refresh_does_not_create_duplicates(self, m_upd, m_push, m_set, m_get, m_store_alert):
        """Scenario 8: Refreshing the teacher dashboard does not create duplicate sessions, attendance, or alerts."""
        m_get.side_effect = self._stateful_get
        m_set.side_effect = self._stateful_set
        m_push.side_effect = self._stateful_push
        m_upd.side_effect = self._stateful_update
        m_store_alert.side_effect = self._stateful_store_alert

        # Start Session
        self._login_teacher()
        self.client.post(reverse("start_monitoring"), {"classroom_name": "CS-402"})
        sess_id = self.client.session.get("session_id")

        # Put a non-educational usage event in phone_usage to trigger an alert
        usage_event = {
            "student_id": "alice_student",
            "app_name": "Instagram",
            "package_name": "com.instagram.android",
            "category": "Non-Educational",
            "duration": 120,
            "timestamp": "2026-10-31T10:00:00"
        }
        self.db_state["phone_usage"][sess_id] = {"ev1": usage_event}

        # Refresh dashboard 3 times
        r1 = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(r2.status_code, 200)
        r3 = self.client.get(reverse("teacher_dashboard"))
        self.assertEqual(r3.status_code, 200)

        # Number of sessions remains 1
        self.assertEqual(len(self.db_state["classroom_sessions"]), 1)
        # Attendance remains 0 (no scans)
        self.assertEqual(len(self.db_state["attendance"]), 0)
        # Alerts for this session remains exactly 1 (not duplicated)
        alerts = self.db_state["alerts"].get(sess_id, {})
        self.assertEqual(len(alerts), 1)

    @patch("home.views.store_alert")
    @patch("home.views.firebase_get")
    @patch("home.views.firebase_set")
    @patch("home.views.firebase_push")
    @patch("home.views.firebase_update")
    def test_scenario_9_starting_and_stopping_monitoring_preserves_workflow_and_guards(self, m_upd, m_push, m_set, m_get, m_store_alert):
        """Scenario 9: Starting and stopping monitoring workflow, permissions, and state transitions."""
        m_get.side_effect = self._stateful_get
        m_set.side_effect = self._stateful_set
        m_push.side_effect = self._stateful_push
        m_upd.side_effect = self._stateful_update
        m_store_alert.side_effect = self._stateful_store_alert

        # Non-teacher (student) cannot start monitoring
        self._login_student(self.student_alice)
        bad_start = self.client.post(reverse("start_monitoring"))
        self.assertIn(bad_start.status_code, [302, 403])
        self.assertEqual(len(self.db_state["classroom_sessions"]), 0)

        # Teacher starts session
        self._login_teacher()
        self.client.post(reverse("start_monitoring"), {"classroom_name": "CS-402"})
        s_id = self.client.session.get("session_id")
        self.assertTrue(s_id)
        self.assertTrue(self.client.session.get("monitoring_active"))

        # Teacher stops session
        self.client.post(reverse("stop_monitoring"))
        self.assertFalse(self.client.session.get("monitoring_active"))
        self.assertFalse(self.db_state["classroom_sessions"][s_id]["active"])
        self.assertEqual(self.client.session.get("last_session_id"), s_id)

    @patch("home.views.store_alert")
    @patch("home.views.firebase_get")
    @patch("home.views.firebase_set")
    @patch("home.views.firebase_push")
    @patch("home.views.firebase_update")
    def test_scenario_reports_and_csv_exports_isolate_by_session(self, m_upd, m_push, m_set, m_get, m_store_alert):
        """Reports and CSV exports retrieve data for the correct session without mixing records."""
        m_get.side_effect = self._stateful_get
        m_set.side_effect = self._stateful_set
        m_push.side_effect = self._stateful_push
        m_upd.side_effect = self._stateful_update
        m_store_alert.side_effect = self._stateful_store_alert

        # Populate historical data for two distinct sessions
        s1_id = "SESSION_HIST_01"
        s2_id = "SESSION_HIST_02"

        self.db_state["classroom_sessions"] = {
            s1_id: {"classroom": "CS-402 Session 1", "active": False, "session_time": "2026-10-30 09:00:00"},
            s2_id: {"classroom": "CS-402 Session 2", "active": False, "session_time": "2026-10-31 09:00:00"}
        }
        self.db_state["attendance"] = {
            "att1": {"student_id": "alice_student", "student_name": "Alice Student", "classroom": "CS-402 Session 1", "session_id": s1_id, "date": "2026-10-30", "time": "09:05:00", "status": "Present"},
            "att2": {"student_id": "bob_student", "student_name": "Bob Student", "classroom": "CS-402 Session 2", "session_id": s2_id, "date": "2026-10-31", "time": "09:05:00", "status": "Present"},
        }
        self.db_state["phone_usage"] = {
            s1_id: {
                "u1": {"student_id": "alice_student", "app_name": "Coursera", "package_name": "org.coursera.android", "category": "Educational", "duration": 300, "timestamp": "2026-10-30T09:10:00"}
            },
            s2_id: {
                "u2": {"student_id": "bob_student", "app_name": "Instagram", "package_name": "com.instagram.android", "category": "Non-Educational", "duration": 180, "timestamp": "2026-10-31T09:15:00"}
            }
        }

        self._login_teacher()

        # 1. Reports overview: each session reports its own distinct attendance count
        rep_resp = self.client.get(reverse("reports_analytics"))
        self.assertEqual(rep_resp.status_code, 200)
        sessions_report = {s["session_id"]: s for s in rep_resp.context["reports"]}
        self.assertEqual(sessions_report[s1_id]["attendance_count"], 1)
        self.assertEqual(sessions_report[s2_id]["attendance_count"], 1)

        # 2. Filter attendance CSV by Session 1
        att_csv_s1 = self.client.get(reverse("export_attendance_csv") + f"?session_id={s1_id}")
        self.assertEqual(att_csv_s1.status_code, 200)
        content_s1 = att_csv_s1.content.decode("utf-8")
        self.assertIn("alice_student", content_s1)
        self.assertNotIn("bob_student", content_s1)
        self.assertIn(s1_id, content_s1)
        self.assertNotIn(s2_id, content_s1)

        # 3. Filter attendance CSV by Session 2
        att_csv_s2 = self.client.get(reverse("export_attendance_csv") + f"?session_id={s2_id}")
        self.assertEqual(att_csv_s2.status_code, 200)
        content_s2 = att_csv_s2.content.decode("utf-8")
        self.assertIn("bob_student", content_s2)
        self.assertNotIn("alice_student", content_s2)
        self.assertIn(s2_id, content_s2)
        self.assertNotIn(s1_id, content_s2)

        # 4. Filter usage CSV by Session 1
        usage_csv_s1 = self.client.get(reverse("export_usage_csv") + f"?session_id={s1_id}")
        self.assertEqual(usage_csv_s1.status_code, 200)
        u_content_s1 = usage_csv_s1.content.decode("utf-8")
        self.assertIn("Coursera", u_content_s1)
        self.assertNotIn("Instagram", u_content_s1)

        # 5. Filter usage CSV by Session 2
        usage_csv_s2 = self.client.get(reverse("export_usage_csv") + f"?session_id={s2_id}")
        self.assertEqual(usage_csv_s2.status_code, 200)
        u_content_s2 = usage_csv_s2.content.decode("utf-8")
        self.assertIn("Instagram", u_content_s2)
        self.assertNotIn("Coursera", u_content_s2)




