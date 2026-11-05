# FocusFrame — Dataset Labeling Guide

**Version:** 1.0.0  
**Applies to:** `session_label_template_*.csv`  
**Last Updated:** 2026-10-26

---

## 1. Purpose

The `session_label_template_*.csv` files contain one row per student-session (student x classroom session).
Reviewers must assign a `focus_label` to each row **before** these sessions can be used for supervised ML training.

The goal is to produce **honest, independently verified** ground-truth labels so the AI model can eventually be retrained on real classroom data instead of synthetic examples.

> **Never fabricate or infer labels without corroborating evidence. When in doubt, mark as `uncertain`.**

---

## 2. Label Values

| Label | Meaning | When to Use |
|---|---|---|
| `focused` | Student was actively engaged with educational material during the session | Educational app usage is dominant (>60%), corroborated by instructor observation or attendance records |
| `potentially_distracted` | Student spent significant time on non-educational apps or showed fragmented attention | Non-educational usage >40%, or >5 app switches in short time with no educational content |
| `uncertain` | Insufficient evidence to reliably label | Short session (<5 min), missing timestamps, or contradictory signals |

---

## 3. How to Use the Template CSV

### 3.1 Open the file
Open `session_label_template_*.csv` in Excel, LibreOffice Calc, or any CSV editor.
Do not sort or delete rows.

### 3.2 Columns to fill in

| Column | What to Enter |
|---|---|
| `focus_label` | One of: `focused`, `potentially_distracted`, `uncertain` |
| `review_status` | Change from `pending` to `reviewed` when done; use `disputed` for contested labels |
| `reviewer_id` | Your pseudonymous reviewer code (e.g., `reviewer_A`) - do not use real name |
| `review_evidence` | A brief, factual note explaining the label (see examples below) |
| `reviewer_notes` | Any additional observations, flags, or follow-up questions |

### 3.3 Columns to NOT modify
Do not alter: `session_id`, `session_id_hash`, `student_id_hash`, `session_start_iso`, `session_end_iso`, or any computed numeric columns.

---

## 4. Evidence Guidelines

Reviewers should consult at least one of the following corroborating sources before assigning a label:

1. **Instructor observation notes** - Did the teacher notice the student was attentive or distracted?
2. **Attendance data** - Was the student physically present for the full session?
3. **App usage ratios** - Use `educational_ratio` and `non_educational_ratio` columns as a signal, not the sole determinant.
4. **App switch frequency** - High `app_switch_count` with low `unique_apps_count` may indicate compulsive checking.
5. **Session duration** - Very short sessions (<3 min) are unreliable; label as `uncertain`.

---

## 5. Labeling Examples

### Example A - `focused`
```
educational_ratio: 0.78, non_educational_ratio: 0.12
app_switch_count: 6, top_apps_summary: Google Classroom (12); YouTube EDU (3)
Evidence: Instructor noted student answered questions; attendance confirmed present.
-> focus_label: focused
```

### Example B - `potentially_distracted`
```
educational_ratio: 0.05, non_educational_ratio: 0.85
app_switch_count: 22, top_apps_summary: WhatsApp (10); Instagram (8); Snapchat (4)
Evidence: High non-educational ratio with frequent social media switches.
-> focus_label: potentially_distracted
```

### Example C - `uncertain`
```
session_span_seconds: 87, total_usage_seconds: 45
Evidence: Session too short (<2 min); insufficient usage data.
-> focus_label: uncertain
```

---

## 6. Quality Requirements

- **Inter-rater agreement:** Have a second reviewer independently label at least 20% of sessions.
- **Minimum labelled sessions for training:** At least 50 labelled sessions with a balanced class distribution (ideally no more than 3:1 ratio between majority and minority class) before retraining should be attempted.
- **No fabrication:** Do not assign a label based on category ratios alone without corroborating evidence if the session is borderline.

---

## 7. Privacy and Security

- This CSV contains pseudonymized data only. Do not add real student names, emails, or other PII in any column.
- Reviewer IDs should be pseudonymous codes assigned by the study coordinator.
- Completed label files should be stored in the `data/focus_training/` directory and not committed to any public repository.

---

## 8. After Labeling

1. Save the completed CSV as `session_label_template_YYYYMMDD_HHMMSS_labeled.csv` (appending `_labeled` to the filename).
2. Run `validate_dataset.py` to check label coverage, class balance, and schema compliance.
3. When 50+ sessions are labeled and validation passes, notify the ML lead to re-run `train_focus_model.py` with the real dataset.
