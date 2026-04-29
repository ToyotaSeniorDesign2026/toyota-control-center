import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Clock3, History } from "lucide-react";
import { Button } from "../components/ui/button";
import { createScheduledRunProjections } from "../lib/scheduleOccurrences";
import { useJobRuns } from "../contexts/JobRunContext";
import { getCalendarEvents, subscribeToUserDashboardStore, type UserCalendarEvent } from "../lib/userDashboardStore";

type CalendarEvent = {
  id: string;
  jobId?: string;
  title: string;
  date: string; // yyyy-mm-dd
  time: string;
  kind: "past" | "scheduled";
  jobType?: string;
};

const baseCalendarEvents: CalendarEvent[] = [];
const RESOURCE_SCHEDULES_UPDATED_EVENT = "control-center-resource-schedules-updated";

function getMonthStart(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function getInitialCalendarMonth(events: CalendarEvent[]) {
  const now = new Date();
  const upcomingEvent = events
    .filter((event) => event.kind === "scheduled")
    .map((event) => new Date(`${event.date}T${event.time}:00`))
    .filter((eventDate) => !Number.isNaN(eventDate.getTime()))
    .sort((a, b) => a.getTime() - b.getTime())
    .find((eventDate) => eventDate >= now);

  return upcomingEvent
    ? new Date(upcomingEvent.getFullYear(), upcomingEvent.getMonth(), 1)
    : new Date(now.getFullYear(), now.getMonth(), 1);
}

function getMonthLabel(date: Date) {
  return date.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

function toDateKey(date: Date) {
  const y = date.getFullYear();
  const m = `${date.getMonth() + 1}`.padStart(2, "0");
  const d = `${date.getDate()}`.padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function CalendarContent() {
  const { resources, runs, refresh } = useJobRuns();
  const [currentMonth, setCurrentMonth] = useState(() => getInitialCalendarMonth(baseCalendarEvents));
  const [eventFilter, setEventFilter] = useState<"all" | "past" | "scheduled">("all");
  const [createdJobEvents, setCreatedJobEvents] = useState<UserCalendarEvent[]>(() => getCalendarEvents());
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);

  const resourceScheduleEvents = useMemo<CalendarEvent[]>(
    () =>
      createScheduledRunProjections(resources).map((occurrence) => ({
        id: occurrence.id,
        jobId: occurrence.resourceId,
        title: occurrence.jobName,
        date: toDateKey(occurrence.scheduledTime),
        time: occurrence.scheduledTime.toTimeString().slice(0, 5),
        kind: "scheduled" as const,
        jobType: occurrence.jobType,
      })),
    [resources],
  );

  const runEvents = useMemo<CalendarEvent[]>(() => {
    const resourceById = new Map(resources.map((resource) => [resource.id, resource]));
    return runs.map((run) => {
      const resource = resourceById.get(run.resource_id);
      const eventDate = new Date(run.created_at);
      const isUpcoming = ["queued", "scheduled", "pending", "executing", "running"].includes(run.status.toLowerCase());
      return {
        id: run.id,
        jobId: run.resource_id,
        title: resource?.name ?? run.resource_id,
        date: toDateKey(eventDate),
        time: eventDate.toTimeString().slice(0, 5),
        kind: isUpcoming ? "scheduled" as const : "past" as const,
        jobType: resource?.type?.toUpperCase(),
      };
    });
  }, [resources, runs]);

  const calendarEvents = useMemo(
    () =>
      [...baseCalendarEvents, ...createdJobEvents, ...resourceScheduleEvents, ...runEvents].sort((a, b) =>
        `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`)
      ),
    [createdJobEvents, resourceScheduleEvents, runEvents]
  );

  useEffect(() => {
    const nextEvents = getCalendarEvents();
    setCreatedJobEvents(nextEvents);
    void refresh();
    const unsubscribeDashboardStore = subscribeToUserDashboardStore(() => {
      const updatedEvents = getCalendarEvents();
      setCreatedJobEvents(updatedEvents);
      void refresh();
    });
    window.addEventListener(RESOURCE_SCHEDULES_UPDATED_EVENT, refresh);
    return () => {
      unsubscribeDashboardStore();
      window.removeEventListener(RESOURCE_SCHEDULES_UPDATED_EVENT, refresh);
    };
  }, []);

  useEffect(() => {
    setCurrentMonth(getInitialCalendarMonth(calendarEvents));
  }, [calendarEvents]);

  const monthStart = useMemo(() => getMonthStart(currentMonth), [currentMonth]);

  const cells = useMemo(() => {
    const startWeekday = monthStart.getDay();
    const daysInMonth = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0).getDate();
    const grid: Array<Date | null> = [];

    for (let i = 0; i < startWeekday; i += 1) {
      grid.push(null);
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
      grid.push(new Date(monthStart.getFullYear(), monthStart.getMonth(), day));
    }
    while (grid.length % 7 !== 0) {
      grid.push(null);
    }
    return grid;
  }, [monthStart]);

  const eventsByDay = useMemo(() => {
    return calendarEvents.reduce<Record<string, CalendarEvent[]>>((acc, event) => {
      if (!acc[event.date]) {
        acc[event.date] = [];
      }
      acc[event.date].push(event);
      return acc;
    }, {});
  }, [calendarEvents]);

  const monthEvents = useMemo(() => {
    const prefix = `${monthStart.getFullYear()}-${`${monthStart.getMonth() + 1}`.padStart(2, "0")}`;
    const monthly = calendarEvents
      .filter((event) => event.date.startsWith(prefix))
      .sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`));
    if (eventFilter === "all") return monthly;
    return monthly.filter((event) => event.kind === eventFilter);
  }, [calendarEvents, monthStart, eventFilter]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Run Calendar</h2>
          <p className="mt-1 text-sm text-gray-600">
            Track past run history and future scheduled runs in one monthly view.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            className="border-gray-300"
            onClick={() => setCurrentMonth(new Date(monthStart.getFullYear(), monthStart.getMonth() - 1, 1))}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <div className="min-w-[180px] text-center text-sm font-semibold text-gray-900">{getMonthLabel(monthStart)}</div>
          <Button
            variant="outline"
            className="border-gray-300"
            onClick={() => setCurrentMonth(new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 1))}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-xs">
        <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-1 font-medium text-blue-700">
          <History className="h-3 w-3" /> Past Run
        </span>
        <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-1 font-medium text-green-700">
          <Clock3 className="h-3 w-3" /> Scheduled Run
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-4">
        <div className="xl:col-span-3 rounded-lg border border-gray-200 bg-white shadow-sm">
          <div className="grid grid-cols-7 border-b border-gray-200 bg-gray-50 text-xs font-semibold uppercase tracking-wide text-gray-500">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
              <div key={day} className="border-r border-gray-200 px-3 py-2 last:border-r-0">
                {day}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7">
            {cells.map((cell, index) => {
              const key = cell ? toDateKey(cell) : `empty-${index}`;
              const dayEvents = cell ? eventsByDay[key] || [] : [];

              return (
                <div
                  key={key}
                  className="min-h-[130px] border-r border-b border-gray-200 p-2 last:border-r-0"
                >
                  {cell && (
                    <>
                      <div className="mb-2 text-xs font-semibold text-gray-700">{cell.getDate()}</div>
                      <div className="space-y-1">
                        {dayEvents.map((event) => (
                          <button
                            key={event.id}
                            onClick={() => setSelectedEvent(event)}
                            className={`rounded px-2 py-1 text-[11px] leading-tight ${
                              event.kind === "past"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-green-100 text-green-800"
                            }`}
                          >
                            <div className="font-medium">{event.time}</div>
                            <div>{event.title}</div>
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
            <h2 className="font-semibold text-gray-900">This Month</h2>
            <p className="mt-1 text-xs text-gray-600">Run history + upcoming schedule</p>
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => setEventFilter("all")}
                className={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                  eventFilter === "all"
                    ? "bg-gray-900 text-white"
                    : "bg-white text-gray-700 border border-gray-300"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setEventFilter("past")}
                className={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                  eventFilter === "past"
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-700 border border-gray-300"
                }`}
              >
                Past
              </button>
              <button
                onClick={() => setEventFilter("scheduled")}
                className={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                  eventFilter === "scheduled"
                    ? "bg-green-600 text-white"
                    : "bg-white text-gray-700 border border-gray-300"
                }`}
              >
                Scheduled
              </button>
            </div>
          </div>
          <div className="max-h-[620px] space-y-2 overflow-y-auto p-4">
            {monthEvents.map((event) => (
              <button
                key={event.id}
                onClick={() => setSelectedEvent(event)}
                className="w-full rounded-lg border border-gray-200 p-3 text-left"
              >
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-gray-900">{event.title}</p>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      event.kind === "past"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-green-100 text-green-700"
                    }`}
                  >
                    {event.kind === "past" ? "Past" : "Scheduled"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-600">{event.date} at {event.time}</p>
              </button>
            ))}
            {monthEvents.length === 0 && (
              <div className="rounded-lg border border-dashed border-gray-300 p-4 text-xs text-gray-600">
                No events for this filter in {getMonthLabel(monthStart)}.
              </div>
            )}
          </div>
        </div>
      </div>

      {selectedEvent && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">{selectedEvent.title}</h3>
              <p className="mt-1 text-xs text-gray-600">
                {selectedEvent.kind === "past" ? "Past run" : "Scheduled run"} on {selectedEvent.date} at {selectedEvent.time}
              </p>
            </div>
            <button
              onClick={() => setSelectedEvent(null)}
              className="rounded-md border border-gray-300 px-2 py-1 text-[11px] font-semibold text-gray-700 hover:bg-gray-50"
            >
              Clear
            </button>
          </div>
          {selectedEvent.jobType && (
            <div className="mt-3 inline-flex rounded-full bg-gray-100 px-2 py-1 text-[11px] font-semibold text-gray-700">
              {selectedEvent.jobType}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
