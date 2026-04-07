import { useState } from "react";
import { useLocation } from "react-router";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import PowerPointForm from "../components/user/PowerPointForm";

export default function PowerPoint() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const location = useLocation();
  const aiState = (location.state as { aiPrompt?: string; aiDraft?: Record<string, unknown> } | null) ?? null;

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="Forms"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <PowerPointForm
          initialData={aiState?.aiDraft}
          aiPrompt={aiState?.aiPrompt}
        />
      </main>
      <UserProfilePanel
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
      />
    </div>
  );
}
