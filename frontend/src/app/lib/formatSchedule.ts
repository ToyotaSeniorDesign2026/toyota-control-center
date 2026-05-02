import cronstrue from "cronstrue";

export function formatSchedule(schedule: string | null | undefined): string {
  if (!schedule?.trim()) return "";
  try {
    return cronstrue.toString(schedule.trim(), { use24HourTimeFormat: false });
  } catch {
    return schedule.trim();
  }
}
