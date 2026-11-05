import sys
import json
from datetime import datetime

sys.path.insert(0, ".")
from home.firebase_config import db

print("=== FIREBASE READ-ONLY AUDIT ===")
nodes = ["phone_usage", "classroom_sessions", "users", "attendance", "devices", "alerts", "alert_history"]
counts = {}
for n in nodes:
    try:
        ref = db.reference(n)
        val = ref.get()
        counts[n] = len(val) if isinstance(val, dict) else (0 if val is None else 1)
    except Exception as e:
        counts[n] = f"Error: {e}"

print("Node top-level key counts:", counts)

pu_ref = db.reference("phone_usage")
pu = pu_ref.get() or {}

cs_ref = db.reference("classroom_sessions")
cs = cs_ref.get() or {}

print(f"\nTotal sessions in phone_usage: {len(pu)}")
print(f"Total sessions in classroom_sessions: {len(cs)}")

total_records = 0
records_per_session = {}
students = set()
categories = {}
field_presence = {}
records_list = []

for sess_id, recs in pu.items():
    if isinstance(recs, dict):
        records_per_session[sess_id] = len(recs)
        total_records += len(recs)
        for rid, r in recs.items():
            if isinstance(r, dict):
                r["_session_id"] = sess_id
                r["_record_id"] = rid
                records_list.append(r)
                if "student_id" in r:
                    students.add(str(r["student_id"]).strip())
                cat = str(r.get("category", "missing")).strip()
                categories[cat] = categories.get(cat, 0) + 1
                for k in r.keys():
                    field_presence[k] = field_presence.get(k, 0) + 1

print(f"Total phone_usage records: {total_records}")
print(f"Distinct student IDs in phone_usage: {len(students)}")
print("Records per session:", records_per_session)
print("Category distribution:", categories)
print("Field presence across records:", field_presence)

print("\nClassroom sessions details:")
for cid, cval in cs.items():
    if isinstance(cval, dict):
        print(f"  Session {cid}: active={cval.get('active')}, start={cval.get('start_time')}, teacher={cval.get('teacher_username', 'unknown')}")

# Check for duplicate records
seen = set()
duplicates = []
for r in records_list:
    key = (r.get("student_id"), r.get("app_name"), r.get("timestamp"), r.get("duration"))
    if key in seen:
        duplicates.append(r)
    else:
        seen.add(key)

print(f"\nDuplicate records detected (same student+app+timestamp+duration): {len(duplicates)}")

# Check timestamps & duration types/ranges
durations = [r.get("duration") for r in records_list if "duration" in r]
timestamps = [r.get("timestamp") for r in records_list if "timestamp" in r]
print(f"Total duration entries: {len(durations)}, sample durations: {durations[:10]}")
print(f"Total timestamp entries: {len(timestamps)}, sample timestamps: {timestamps[:5]}")

# Check if ground truth labels exist
labels_found = {}
for r in records_list:
    for k in r:
        if any(term in k.lower() for term in ["focus", "ground", "true", "label", "target"]):
            labels_found[k] = labels_found.get(k, 0) + 1
print("Focus/label-related fields in phone_usage records:", labels_found)
