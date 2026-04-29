import type { ResourceRecord } from "./controlCenterApi";

export interface ScheduledOccurrence {
  id: string;
  resourceId: string;
  jobName: string;
  jobType: string;
  scheduledTime: Date;
}

function parseScheduleTime(schedule: string) {
  const cronParts = schedule.trim().split(/\s+/);
  if (cronParts.length === 5 && cronParts[2] === "*" && cronParts[3] === "*" && cronParts[4] === "*") {
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

function isDailySchedule(schedule: string) {
  const normalized = schedule.toLowerCase();
  const cronParts = schedule.trim().split(/\s+/);
  return (
    normalized.includes("daily") ||
    normalized.includes("every day") ||
    normalized.includes("everyday") ||
    (cronParts.length === 5 && cronParts[2] === "*" && cronParts[3] === "*" && cronParts[4] === "*")
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

export function createScheduledRunProjections(resources: ResourceRecord[], now = new Date(), daysAhead = 30): ScheduledOccurrence[] {
  const occurrences: ScheduledOccurrence[] = [];

  resources.forEach((resource) => {
    const schedule = typeof resource.config?.schedule === "string" ? resource.config.schedule.trim() : "";
    if (!schedule || !isDailySchedule(schedule)) return;

    const parsedTime = parseScheduleTime(schedule);
    if (!parsedTime) return;

    const first = new Date(now);
    first.setHours(parsedTime.hour, parsedTime.minute, 0, 0);
    if (first <= now) {
      first.setDate(first.getDate() + 1);
    }

    for (let index = 0; index < daysAhead; index += 1) {
      const scheduledTime = new Date(first);
      scheduledTime.setDate(first.getDate() + index);
      occurrences.push({
        id: `schedule-${resource.id}-${dateKey(scheduledTime)}`,
        resourceId: resource.id,
        jobName: resource.name,
        jobType: resource.type.toUpperCase(),
        scheduledTime,
      });
    }
  });

  return occurrences.sort((a, b) => a.scheduledTime.getTime() - b.scheduledTime.getTime());
}
