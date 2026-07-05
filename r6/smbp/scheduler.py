"""SMBP reminder scheduler — pure decision engine (#61, phase 2).

Decides WHO is due for a reading reminder on their prescribed cadence, and
builds the SMS reminder payload for the action layer. No cron, no threads, no
Flask, no DB — the deployment concern of *when* to run this lives elsewhere.
The testable, valuable part is "who is behind, and what reminder do they get".

The `SMBPSession` model is deliberately lean (patient_ref, language, days,
started, ...). Fields this engine wants but the row may not carry — cadence,
completed, prescribed, last_reading_at, last_reminded_at, phone — are read via
`getattr` with safe defaults, so this works against a bare session AND against
a session the Flask route has enriched with computed activity (see
scheduler_routes.py). Nothing here logs or returns a phone number.
"""

from datetime import datetime, timedelta, timezone

from r6.smbp.outreach import reminder_action

# Cadence label -> interval between expected readings. Absent/unknown -> daily.
DEFAULT_INTERVAL = timedelta(days=1)
CADENCE_INTERVALS = {
    "daily": timedelta(days=1),
    "qd": timedelta(days=1),
    "twice_daily": timedelta(hours=12),
    "bid": timedelta(hours=12),
    "weekly": timedelta(days=7),
}


def _naive_utc(dt):
    """Coerce a datetime to naive UTC (the model stores naive UTC columns)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def reminder_interval(enrollment):
    """Interval between expected readings for this enrollment.

    Precedence: an explicit numeric `cadence_hours`, then a `cadence` label,
    else the daily default.
    """
    hours = getattr(enrollment, "cadence_hours", None)
    if hours:
        return timedelta(hours=float(hours))
    cadence = getattr(enrollment, "cadence", None)
    if cadence:
        return CADENCE_INTERVALS.get(str(cadence).lower(), DEFAULT_INTERVAL)
    return DEFAULT_INTERVAL


def prescribed_count(enrollment):
    """Prescribed readings. Explicit `prescribed` wins; else days * 2 readings.

    The `days * 2` fallback mirrors r6.smbp.monitoring.adherence (2 readings a
    day over the monitoring window).
    """
    explicit = getattr(enrollment, "prescribed", None)
    if explicit is not None:
        return explicit
    days = getattr(enrollment, "days", 0) or 0
    return days * 2


def completed_count(enrollment):
    return getattr(enrollment, "completed", 0) or 0


def contact_phone(enrollment):
    """The reminder destination number, if the enrollment carries one."""
    return getattr(enrollment, "phone", None) or getattr(enrollment, "contact", None)


def reminder_due(enrollment, now):
    """True if this patient is behind their cadence and can be reminded now.

    Rules:
      - Done: completed >= prescribed -> never remind.
      - Behind: no reading within one interval (measured from the last reading,
        or from enrollment start if none yet).
      - No double-nagging: skip if already reminded within the current interval.
    """
    now = _naive_utc(now)
    interval = reminder_interval(enrollment)

    if completed_count(enrollment) >= prescribed_count(enrollment):
        return False

    last_reading = _naive_utc(getattr(enrollment, "last_reading_at", None))
    started = _naive_utc(getattr(enrollment, "started", None))
    baseline = last_reading or started or datetime.min
    if now - baseline < interval:
        # A reading (or a just-started enrollment) landed inside this interval.
        return False

    last_reminded = _naive_utc(getattr(enrollment, "last_reminded_at", None))
    if last_reminded is not None and now - last_reminded < interval:
        return False

    return True


def due_reminders(enrollments, now):
    """List `{patient_ref, reminder_action_payload}` for every due enrollment.

    The payload carries the phone in `payload.phone` (via outreach.reminder_action);
    the top-level keys are PHI-safe (patient_ref only). Callers that log or
    summarise MUST use the top-level keys, never the payload's phone.
    """
    out = []
    for e in enrollments:
        if not reminder_due(e, now):
            continue
        action = reminder_action(
            e.patient_ref,
            contact_phone(e),
            getattr(e, "language", "en"),
            completed_count(e),
            prescribed_count(e),
        )
        out.append({"patient_ref": e.patient_ref,
                    "reminder_action_payload": action})
    return out
