import { useState } from "react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import ExcelReportForm from "../components/user/ExcelReportForm";

export default function ExcelReport() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="My Resources"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <ExcelReportForm />
      </main>
      <UserProfilePanel
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
      />
    </div>
  );
}
