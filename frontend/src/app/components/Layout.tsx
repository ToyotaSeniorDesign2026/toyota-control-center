import { Outlet, useLocation } from "react-router";
import { TopNavigation } from "./TopNavigation";
import { UserProfilePanel } from "./user/UserProfilePanel";
import { GlobalAIChatPanel } from "./GlobalAIChatPanel";
import { FloatingAIButton } from "./FloatingAIButton";
import { useState } from "react";
import { useUser } from "../contexts/UserContext";

export default function Layout() {
  const location = useLocation();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const { profile } = useUser();
  
  // Determine active page based on current route
  const getActivePage = () => {
    if (location.pathname === "/") return "Dashboard";
    if (location.pathname === "/user-home") return "Home";
    if (location.pathname.startsWith("/research")) return "Research";
    if (location.pathname.startsWith("/resources")) return "Resources";
    if (location.pathname.startsWith("/runs")) return "Runs";
    if (location.pathname.startsWith("/approvals")) return "Approvals";
    if (location.pathname.startsWith("/risk")) return "Risk";
    if (location.pathname.startsWith("/admin")) return "Admin";
    return "Dashboard";
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <TopNavigation 
        activePage={getActivePage()} 
        onProfileClick={() => setIsProfileOpen(true)}
        userRole={profile.role}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <Outlet />
      </main>
      <UserProfilePanel 
        isOpen={isProfileOpen} 
        onClose={() => setIsProfileOpen(false)} 
      />
      
      {/* Global AI Assistant - Available on all admin pages */}
      <FloatingAIButton />
      <GlobalAIChatPanel />
    </div>
  );
}