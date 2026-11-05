# =========================================================
# ALERT SEVERITY
# =========================================================


def calculate_alert_severity(alert_data):
    """
    Calculate alert severity based on
    non-educational usage duration.

    Severity levels:
        Low    -> less than 60 seconds
        Medium -> 60 to 180 seconds
        High   -> more than 180 seconds
    """

    if not isinstance(alert_data, dict):
        return "Low"

    duration = alert_data.get("duration", 0)

    try:
        duration = float(duration)
    except (TypeError, ValueError):
        duration = 0

    if duration < 60:
        return "Low"

    elif duration <= 180:
        return "Medium"

    else:
        return "High"

# =========================================================
# FOCUSFRAME - ALERT DETECTION LOGIC
# =========================================================

from firebase_admin import db


def is_non_educational_usage(usage):
    """
    Check whether a phone usage record represents
    non-educational app usage.

    Returns:
        True  -> Alert condition detected
        False -> No alert condition
    """

    if not isinstance(usage, dict):
        return False

    category = str(
        usage.get("category", "")
    ).strip().lower()

    non_educational_categories = [
        "non-educational",
        "non educational",
        "noneducational"
    ]

    return category in non_educational_categories


def detect_alert_condition(usage):
    """
    Analyze one phone usage record and determine
    whether it should generate an alert.

    This function only detects the condition.
    It does NOT store anything in Firebase yet.
    """

    if not isinstance(usage, dict):
        return None

    if not is_non_educational_usage(usage):
        return None

    alert_data = {
        "student_id": usage.get(
            "student_id",
            ""
        ),
        "app_name": usage.get(
            "app_name",
            ""
        ),
        "package_name": usage.get(
            "package_name",
            ""
        ),
        "category": usage.get(
            "category",
            ""
        ),
        "confidence": usage.get(
            "confidence",
            0
        ),
        "duration": usage.get(
            "duration",
            0
        ),
        "timestamp": usage.get(
            "timestamp",
            ""
        ),
    }

    return alert_data


def detect_alerts(phone_usage_records):
    """
    Check multiple phone usage records and return
    the records that require an alert.

    This is the main T1 detection function.
    """

    alerts = []

    if not phone_usage_records:
        return alerts

    for usage in phone_usage_records:

        alert = detect_alert_condition(usage)

        if alert is not None:
            alerts.append(alert)

    return alerts


# =========================================================
# STORE ALERT IN FIREBASE
# =========================================================

def store_alert(session_id, alert_data):
    """
    Store a detected phone usage alert in Firebase.

    Firebase structure:

    alerts
        └── session_id
              └── generated_alert_id
                    ├── session_id
                    ├── student_id
                    ├── student_name
                    ├── student_email
                    ├── app_name
                    ├── package_name
                    ├── category
                    ├── confidence
                    ├── duration
                    ├── severity
                    ├── timestamp
                    └── source_usage_id
    """

    if not session_id:
        return None

    if not isinstance(alert_data, dict):
        return None

    stored_alert = {
        "session_id": session_id,

        "student_id": alert_data.get(
            "student_id",
            ""
        ),

        "student_name": alert_data.get(
            "student_name",
            ""
        ),

        "student_email": alert_data.get(
            "student_email",
            ""
            ),
            "device_name": alert_data.get(
                "device_name",
                ""
                ),
                "app_name": alert_data.get(
                    "app_name",
                    ""
                ),

        "package_name": alert_data.get(
            "package_name",
            ""
        ),

        "category": alert_data.get(
            "category",
            ""
        ),

        "confidence": alert_data.get(
            "confidence",
            0
        ),

        "duration": alert_data.get(
            "duration",
            0
        ),

        "severity": alert_data.get(
            "severity",
            calculate_alert_severity(
                alert_data
            )
        ),

        "timestamp": alert_data.get(
            "timestamp",
            ""
        ),

        # Used to prevent the same phone-usage
        # record from creating duplicate alerts
        "source_usage_id": alert_data.get(
            "source_usage_id",
            ""
        )
    }

    # Firebase Admin SDK uses db.reference()
    alerts_ref = db.reference(
        f"alerts/{session_id}"
    )

    # Idempotency guard: prevent duplicate alert creation for the same usage event
    source_usage_id = stored_alert.get("source_usage_id")
    event_fingerprint = (
        f"{stored_alert.get('student_id')}_"
        f"{stored_alert.get('app_name')}_"
        f"{stored_alert.get('timestamp')}_"
        f"{stored_alert.get('duration')}"
    )

    try:
        existing_alerts = alerts_ref.get()
        if existing_alerts and isinstance(existing_alerts, dict):
            for alert_key, existing_alert in existing_alerts.items():
                if not isinstance(existing_alert, dict):
                    continue
                # Match by source_usage_id if present
                if source_usage_id and existing_alert.get("source_usage_id") == source_usage_id:
                    return alert_key
                # Match by event fingerprint
                existing_fp = (
                    f"{existing_alert.get('student_id')}_"
                    f"{existing_alert.get('app_name')}_"
                    f"{existing_alert.get('timestamp')}_"
                    f"{existing_alert.get('duration')}"
                )
                if existing_fp == event_fingerprint:
                    return alert_key
    except Exception:
        pass

    # Push creates a unique Firebase alert ID
    try:
        new_alert = alerts_ref.push(
            stored_alert
        )
        return getattr(new_alert, "key", None)
    except Exception:
        return None

# =========================================================
# STUDENT IDENTIFICATION
# =========================================================

def get_registered_student(student_id):
    """
    Get the registered student information from Firebase.
    """

    if not student_id:
        return None

    student_id = str(student_id).strip()

    if not student_id:
        return None

    try:
        student = db.reference(
            f"users/{student_id}"
        ).get()
    except Exception:
        return None

    if not isinstance(student, dict):
        return None

    if student.get("role") != "student":
        return None

    return student


def get_registered_device(student_id):
    """
    Get the registered device information for the student.
    """

    if not student_id:
        return None

    student_id = str(student_id).strip()

    if not student_id:
        return None

    try:
        device = db.reference(
            f"devices/{student_id}"
        ).get()
    except Exception:
        return None

    if not isinstance(device, dict):
        return None

    return device


def identify_alert_student(alert_data, users_data=None, devices_data=None):
    """
    Identify the registered student and device
    associated with the alert.
    """

    if not isinstance(alert_data, dict):
        return None

    student_id = str(
        alert_data.get("student_id", "")
    ).strip()

    if not student_id:
        return None

    # Get registered student
    student = None
    if users_data and isinstance(users_data, dict):
        student = users_data.get(student_id)
        if isinstance(student, dict) and student.get("role") != "student":
            student = None

    if student is None:
        student = get_registered_student(
            student_id
        )

    if student is None:
        return None

    # Get registered device
    device = None
    if devices_data and isinstance(devices_data, dict):
        device = devices_data.get(student_id)
        if not device:
            for dev in devices_data.values():
                if isinstance(dev, dict) and str(dev.get("register_number", "")).strip() == student_id:
                    device = dev
                    break

    if device is None:
        device = get_registered_device(
            student_id
        )

    identified_alert = dict(
        alert_data
    )

    # Student identification - T4
    identified_alert["student_id"] = student_id

    identified_alert["student_name"] = student.get(
        "full_name",
        student.get("name", "")
    )

    identified_alert["student_email"] = student.get(
        "email",
        ""
    )

    # Registered device identification - T4
    identified_alert["device_name"] = (
        device.get("device_name", "")
        if device
        else ""
    )

    return identified_alert