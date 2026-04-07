import React, { createContext, useContext, useState } from "react";

type CalendarContextType = {
  isOpen: boolean;
  openCalendar: () => void;
  closeCalendar: () => void;
};

const CalendarContext = createContext<CalendarContextType | undefined>(undefined);

export function CalendarProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);

  const openCalendar = () => setIsOpen(true);
  const closeCalendar = () => setIsOpen(false);

  return (
    <CalendarContext.Provider value={{ isOpen, openCalendar, closeCalendar }}>
      {children}
    </CalendarContext.Provider>
  );
}

export function useCalendarOverlay() {
  const context = useContext(CalendarContext);
  if (!context) {
    throw new Error("useCalendarOverlay must be used within CalendarProvider");
  }
  return context;
}
