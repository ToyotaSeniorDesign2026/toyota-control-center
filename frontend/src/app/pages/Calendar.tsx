import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Clock3, History } from "lucide-react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { Button } from "../components/ui/button";

type CalendarEvent = {
  id: string;
  title: string;
  date: string; // yyyy-mm-dd
  time: string;
  kind: "past" | "scheduled";
};

const calendarEvents: CalendarEvent[] = [
  { id: "run-1", title: "Warranty Claims Rollup", date: "2026-03-01", time: "08:00", kind: "past" },
  { id: "run-2", title: "Customer Churn Analysis", date: "2026-03-02", time: "06:00", kind: "past" },
  { id: "run-3", title: "Dealer KPI Deck", date: "2026-03-03", time: "09:00", kind: "past" },
  { id: "run-4", title: "Finance Executive Deck", date: "2026-03-05", time: "09:00", kind: "scheduled" },
  { id: "run-5", title: "SQL Revenue Dashboard", date: "2026-03-08", time: "07:00", kind: "scheduled" },
  { id: "run-6", title: "Regional Sales Export", date: "2026-03-11", time: "10:30", kind: "scheduled" },
  { id: "run-7", title: "Dealer Scorecard Refresh", date: "2026-03-15", time: "06:30", kind: "scheduled" },
  { id: "run-8", title: "Monthly Board Presentation", date: "2026-03-21", time: "11:00", kind: "scheduled" },
  { id: "run-9", title: "Pricing Risk Monitor", date: "2026-03-25", time: "05:00", kind: "scheduled" },
];

function getMonthStart(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
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

export default function CalendarPage() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [currentMonth, setCurrentMonth] = useState(new Date(2026, 2, 1));
  const [eventFilter, setEventFilter] = useState<"all" | "past" | "scheduled">("all");

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
  }, []);

  const monthEvents = useMemo(() => {
    const prefix = `${monthStart.getFullYear()}-${`${monthStart.getMonth() + 1}`.padStart(2, "0")}`;
    const monthly = calendarEvents
      .filter((event) => event.date.startsWith(prefix))
      .sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`));
    if (eventFilter === "all") return monthly;
    return monthly.filter((event) => event.kind === eventFilter);
  }, [monthStart, eventFilter]);

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation activePage="Calendar" onProfileClick={() => setIsProfileOpen(true)} />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Run Calendar</h1>
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
                              <div
                                key={event.id}
                                className={`rounded px-2 py-1 text-[11px] leading-tight ${
                                  event.kind === "past"
                                    ? "bg-blue-100 text-blue-800"
                                    : "bg-green-100 text-green-800"
                                }`}
                              >
                                <div className="font-medium">{event.time}</div>
                                <div>{event.title}</div>
                              </div>
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
                  <div key={event.id} className="rounded-lg border border-gray-200 p-3">
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
                  </div>
                ))}
                {monthEvents.length === 0 && (
                  <div className="rounded-lg border border-dashed border-gray-300 p-4 text-xs text-gray-600">
                    No events for this filter in {getMonthLabel(monthStart)}.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
    </div>
  );
}
