import type { JobRecord } from "./controlCenterApi";

export interface ScheduledOccurrence {
  id: string;
  jobId: string;
  jobName: string;
  jobType: string;
  scheduledTime: Date;
}

function parseScheduleTime(schedule: string): { hour: number; minute: number } | null {
  // Cron "minute hour * * *"
  const cronParts = schedule.trim().split(/\s+/);
  if (cronParts.length === 5 && cronParts[2] === "*" && cronParts[3] === "*") {
    const minute = Number.parseInt(cronParts[0], 10);
    const hour = Number.parseInt(cronParts[1], 10);
    if (Number.isInteger(hour) && Number.isInteger(minute) && hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59) {
      return { hour, minute };
    }
  }

  const match = schedule.match(/\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b/i);
  if (!match) return null;

  let hour = Number.parseInt(match[1], 10);
  const minute = Number.parseInt(match[2] ?? "0", 10);
  const meridiem = match[3]?.toLowerCase();
  if (meridiem === "pm" && hour !== 12) hour += 12;
  if (meridiem === "am" && hour === 12) hour = 0;
  if (hour > 23 || minute > 59) return null;
  return { hour, minute };
}

// Returns 0-6 (Sunday=0) or null
function parseDayOfWeek(schedule: string): number | null {
  const normalized = schedule.toLowerCase();
  const days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
  for (let i = 0; i < days.length; i++) {
    if (normalized.includes(days[i])) return i;
  }
  const short = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  for (let i = 0; i < short.length; i++) {
    if (new RegExp(`\\b${short[i]}\\b`).test(normalized)) return i;
  }
  return null;
}

// Returns an end date parsed from phrases like "until May 8th", "through May 8", "by May 8"
function parseEndDate(schedule: string): Date | null {
  const match = schedule.match(
    /\b(?:until|through|by|ending|end)\s+([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\b/i,
  );
  if (!match) return null;

  const monthNames = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
  ];
  const monthIndex = monthNames.indexOf(match[1].toLowerCase());
  if (monthIndex === -1) return null;

  const day = Number.parseInt(match[2], 10);
  const now = new Date();
  let year = now.getFullYear();
  const endDate = new Date(year, monthIndex, day, 23, 59, 59);
  // If the date has already passed this year, assume next year
  if (endDate < now) endDate.setFullYear(year + 1);
  return endDate;
}

function isDailySchedule(schedule: string): boolean {
  const normalized = schedule.toLowerCase();
  const cronParts = schedule.trim().split(/\s+/);
  return (
    normalized.includes("daily") ||
    normalized.includes("every day") ||
    normalized.includes("everyday") ||
    (cronParts.length === 5 && cronParts[2] === "*" && cronParts[3] === "*" && cronParts[4] === "*")
  );
}

function isWeekdayRangeSchedule(schedule: string): boolean {
  // Cron "minute hour * * N-M" where N-M is a day-of-week range like 1-5
  const cronParts = schedule.trim().split(/\s+/);
  if (cronParts.length === 5 && cronParts[2] === "*" && cronParts[3] === "*") {
    return /^\d-\d$/.test(cronParts[4]);
  }
  return (
    /every\s+weekday/i.test(schedule) ||
    /monday\s*(through|to|-)\s*friday/i.test(schedule)
  );
}

function isWeeklySchedule(schedule: string): boolean {
  const normalized = schedule.toLowerCase();
  // Cron "minute hour * * day_of_week"
  const cronParts = schedule.trim().split(/\s+/);
  if (cronParts.length === 5 && cronParts[2] === "*" && cronParts[3] === "*" && /^[0-6]$/.test(cronParts[4])) {
    return true;
  }
  return (
    normalized.includes("weekly") ||
    /every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)\b/i.test(schedule)
  );
}

function dateKey(date: Date) {
  const y = date.getFullYear();
  const m = `${date.getMonth() + 1}`.padStart(2, "0");
  const d = `${date.getDate()}`.padStart(2, "0");
  const h = `${date.getHours()}`.padStart(2, "0");
  const min = `${date.getMinutes()}`.padStart(2, "0");
  return `${y}-${m}-${d}T${h}:${min}`;
}

export function createScheduledRunProjections(
  jobs: JobRecord[],
  now = new Date(),
  daysAhead = 90,
): ScheduledOccurrence[] {
  const occurrences: ScheduledOccurrence[] = [];

  for (const job of jobs) {
    const schedule =
      typeof job.config?.schedule === "string" ? job.config.schedule.trim() : "";
    if (!schedule) continue;

    const parsedTime = parseScheduleTime(schedule);
    if (!parsedTime) continue;

    const endDate = parseEndDate(schedule);
    const cutoff = endDate ?? new Date(now.getTime() + daysAhead * 24 * 60 * 60 * 1000);

    if (isWeekdayRangeSchedule(schedule)) {
      // Parse day-of-week range from cron (e.g. "1-5") or default Mon-Fri
      const cronParts = schedule.trim().split(/\s+/);
      let startDow = 1;
      let endDow = 5;
      if (cronParts.length === 5 && /^\d-\d$/.test(cronParts[4])) {
        [startDow, endDow] = cronParts[4].split("-").map(Number);
      }

      const cursor = new Date(now);
      cursor.setHours(parsedTime.hour, parsedTime.minute, 0, 0);
      if (cursor <= now) cursor.setDate(cursor.getDate() + 1);

      while (cursor <= cutoff) {
        const dow = cursor.getDay();
        if (dow >= startDow && dow <= endDow) {
          const scheduledTime = new Date(cursor);
          occurrences.push({
            id: `schedule-${job.id}-${dateKey(scheduledTime)}`,
            jobId: job.id,
            jobName: job.name,
            jobType: job.type.toUpperCase(),
            scheduledTime,
          });
        }
        cursor.setDate(cursor.getDate() + 1);
      }
    } else if (isDailySchedule(schedule)) {
      const first = new Date(now);
      first.setHours(parsedTime.hour, parsedTime.minute, 0, 0);
      if (first <= now) first.setDate(first.getDate() + 1);

      for (let index = 0; ; index++) {
        const scheduledTime = new Date(first);
        scheduledTime.setDate(first.getDate() + index);
        if (scheduledTime > cutoff) break;
        occurrences.push({
          id: `schedule-${job.id}-${dateKey(scheduledTime)}`,
          jobId: job.id,
          jobName: job.name,
          jobType: job.type.toUpperCase(),
          scheduledTime,
        });
      }
    } else if (isWeeklySchedule(schedule)) {
      // Determine target day-of-week (0=Sun … 6=Sat)
      let targetDow: number | null = null;
      const cronParts = schedule.trim().split(/\s+/);
      if (cronParts.length === 5 && /^[0-6]$/.test(cronParts[4])) {
        targetDow = Number.parseInt(cronParts[4], 10);
      } else {
        targetDow = parseDayOfWeek(schedule);
      }
      if (targetDow === null) continue;

      // Find the first occurrence on or after now
      const first = new Date(now);
      first.setHours(parsedTime.hour, parsedTime.minute, 0, 0);
      const daysUntilTarget = (targetDow - first.getDay() + 7) % 7;
      first.setDate(first.getDate() + (daysUntilTarget === 0 && first <= now ? 7 : daysUntilTarget));

      for (let week = 0; ; week++) {
        const scheduledTime = new Date(first);
        scheduledTime.setDate(first.getDate() + week * 7);
        if (scheduledTime > cutoff) break;
        occurrences.push({
          id: `schedule-${job.id}-${dateKey(scheduledTime)}`,
          jobId: job.id,
          jobName: job.name,
          jobType: job.type.toUpperCase(),
          scheduledTime,
        });
      }
    }
  }

  return occurrences.sort((a, b) => a.scheduledTime.getTime() - b.scheduledTime.getTime());
}
