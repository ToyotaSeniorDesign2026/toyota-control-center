import { useState } from "react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import SQLJobForm from "../components/user/SQLJobForm";

export default function SQLJob() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="My Resources"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <SQLJobForm />
      </main>
      <UserProfilePanel
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
      />
    </div>
  );
}
