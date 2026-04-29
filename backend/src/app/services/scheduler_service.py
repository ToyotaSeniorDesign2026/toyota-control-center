from __future__ import annotations

"""Lightweight job scheduler for runtime jobs.

Schedules are stored on ``Job.config["schedule"]`` as either natural
language used by the UI/chat ("daily at 7:30 PM") or simple cron
("30 19 * * *"). The scheduler stores its own cursor in the same JSON config
so the existing schema can support scheduled execution without a migration.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import now_iso
from app.models.job import Job
from app.models.run import Run
from app.models.user import User
from app.schemas.run import RunCreate
from app.services.audit_service import write_audit
from app.services.run_service import create_run_and_maybe_execute


@dataclass(frozen=True)
class ScheduleOccurrence:
    due_at: datetime
    fire_key: str


def _timezone(name: str | None = None) -> ZoneInfo:
    try:
        return ZoneInfo(name or settings.job_scheduler_timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _parse_time(raw: str) -> time | None:
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", raw, flags=re.IGNORECASE)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    meridiem = (match.group(3) or "").lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def _parse_cron_daily(schedule: str) -> time | None:
    parts = schedule.split()
    if len(parts) != 5:
        return None
    minute, hour, day_of_month, month, day_of_week = parts
    if day_of_month != "*" or month != "*" or day_of_week != "*":
        return None
    if not minute.isdigit() or not hour.isdigit():
        return None
    hour_number = int(hour)
    minute_number = int(minute)
    if hour_number > 23 or minute_number > 59:
        return None
    return time(hour=hour_number, minute=minute_number)


def next_daily_occurrence(schedule: str, now: datetime | None = None, timezone_name: str | None = None) -> ScheduleOccurrence | None:
    tz = _timezone(timezone_name)
    current = (now or datetime.now(timezone.utc)).astimezone(tz)
    scheduled_time = _parse_cron_daily(schedule) or _parse_time(schedule)
    if scheduled_time is None:
        return None

    occurrence = current.replace(
        hour=scheduled_time.hour,
        minute=scheduled_time.minute,
        second=0,
        microsecond=0,
    )
    if occurrence > current:
        occurrence -= timedelta(days=1)

    return ScheduleOccurrence(
        due_at=occurrence.astimezone(timezone.utc),
        fire_key=occurrence.strftime("%Y-%m-%dT%H:%M"),
    )


def _scheduled_jobs(db: Session) -> list[Job]:
    rows = (
        db.query(Job)
        .filter(Job.kind == "runtime")
        .filter(Job.status.in_(["healthy", "ready", "active"]))
        .all()
    )
    return [job for job in rows if isinstance(job.config, dict) and job.config.get("schedule")]


def _recent_duplicate_exists(db: Session, job_id: str, fire_key: str) -> bool:
    runs = (
        db.query(Run)
        .filter(Run.job_id == job_id)
        .filter(Run.trigger_source == "schedule")
        .order_by(Run.created_at.desc())
        .limit(50)
        .all()
    )
    for run in runs:
        submitted = run.submitted_config_json or {}
        if (submitted.get("params") or {}).get("schedule_fire_key") == fire_key:
            return True
    return False


def _run_payload_for_job(job: Job, fire_key: str) -> RunCreate:
    config = job.config or {}
    is_github_write = job.type == "sql" and str(job.connector or "").lower() == "github"
    params: dict = {}
    if config.get("query"):
        params["query"] = config["query"]
    if config.get("connection_id"):
        params["connection_id"] = config["connection_id"]
    if is_github_write:
        for key in ("github_token", "repo", "path", "file_path", "ref", "branch"):
            if config.get(key):
                params[key] = config[key]
    params["schedule_fire_key"] = fire_key
    params["created_via"] = "scheduler"
    return RunCreate(
        job_id=job.id,
        action="run",
        target_environment=job.environment or "dev",
        params=params,
    )


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def run_due_scheduled_jobs(db: Session, now: datetime | None = None) -> list[dict]:
    current = now or datetime.now(timezone.utc)
    fired: list[dict] = []

    for job in _scheduled_jobs(db):
        config = dict(job.config or {})
        occurrence = next_daily_occurrence(
            str(config.get("schedule") or ""),
            now=current,
            timezone_name=str(config.get("timezone") or settings.job_scheduler_timezone),
        )
        if not occurrence or occurrence.due_at > current:
            continue
        schedule_active_at = _parse_iso_datetime(str(config.get("schedule_updated_at") or "")) or _parse_iso_datetime(job.created_at)
        if schedule_active_at and occurrence.due_at < schedule_active_at:
            continue
        if config.get("schedule_last_fire_key") == occurrence.fire_key:
            continue
        if _recent_duplicate_exists(db, job.id, occurrence.fire_key):
            config["schedule_last_fire_key"] = occurrence.fire_key
            job.config = config
            job.updated_at = now_iso()
            db.add(job)
            db.commit()
            continue

        owner = db.get(User, job.owner_id)
        if not owner or not owner.is_active:
            continue

        run = create_run_and_maybe_execute(
            db,
            owner,
            _run_payload_for_job(job, occurrence.fire_key),
            trigger_source="schedule",
        )
        config["schedule_last_fire_key"] = occurrence.fire_key
        config["schedule_last_run_at"] = now_iso()
        job.config = config
        job.updated_at = now_iso()
        db.add(job)
        db.commit()
        write_audit(db, owner, "SCHEDULED_RUN_CREATED", {"job_id": job.id, "run_id": run["id"]})
        fired.append({"job_id": job.id, "run_id": run["id"], "fire_key": occurrence.fire_key})

    return fired
