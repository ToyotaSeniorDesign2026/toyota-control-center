import { useState } from "react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { CalendarContent } from "../components/CalendarContent";

export default function CalendarPage() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation activePage="Calendar" onProfileClick={() => setIsProfileOpen(true)} />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <CalendarContent />
      </main>

      <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
    </div>
  );
}
