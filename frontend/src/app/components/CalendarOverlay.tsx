import { X } from "lucide-react";
import { useEffect } from "react";
import { CalendarContent } from "./CalendarContent";
import { useCalendarOverlay } from "../contexts/CalendarContext";

export function CalendarOverlay() {
  const { isOpen, closeCalendar } = useCalendarOverlay();

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeCalendar();
      }
    };

    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [isOpen, closeCalendar]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm transition-opacity"
        onClick={closeCalendar}
      />

      {/* Overlay Panel */}
      <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[80%] flex-col bg-white shadow-2xl sm:max-w-[75%] lg:max-w-[70%] xl:max-w-[65%] 2xl:max-w-[1200px]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
          <h1 className="text-xl font-bold text-gray-900">Run Calendar</h1>
          <button
            onClick={closeCalendar}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            aria-label="Close calendar"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-8">
          <CalendarContent />
        </div>
      </div>
    </>
  );
}
