import { Bell, CalendarDays } from "lucide-react";
import { Link } from "react-router";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import { useUser } from "../contexts/UserContext";
import { useState } from "react";
import { NotificationPanel } from "./notifications/NotificationPanel";
import { useCalendarOverlay } from "../contexts/CalendarContext";
import tfsLogo from "../../assets/tfs-logo-white-red-bg.svg";

export function UserNavigation({ 
  activePage = "Dashboard",
  onProfileClick
}: { 
  activePage?: string;
  onProfileClick?: () => void;
}) {
  const { profile } = useUser();
  const { openCalendar } = useCalendarOverlay();
  const [isNotificationPanelOpen, setIsNotificationPanelOpen] = useState(false);

  return (
    <>
      <header className="border-b border-gray-200 bg-white">
        <div className="flex h-16 items-center justify-between px-6">
        {/* Left: Logo and Nav */}
        <div className="flex items-center gap-8">
          <Link to="/user-home" className="flex items-center gap-2">
            <div className="flex items-center gap-2">
              <div className="w-11 h-11 rounded bg-[#ed0923] flex items-center justify-center overflow-hidden">
                <img src={tfsLogo} alt="TFS" className="w-full h-full object-cover scale-150" />
              </div>
              <span className="text-lg font-semibold text-gray-900">Toyota Control Center</span>
            </div>
          </Link>
          <nav className="flex items-center gap-1">
            {/* Workspace */}
            <Link
              to="/user-home"
              className={`px-3 py-2 text-sm font-medium transition-colors rounded-md ${
                activePage === "Dashboard"
                  ? "bg-gray-100 text-gray-900"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
              }`}
            >
              Workspace
            </Link>

            {/* User */}
            <span className="px-3 py-2 text-sm font-medium text-gray-400">User</span>
          </nav>
        </div>

        {/* Right: Notifications, User */}
        <div className="flex items-center gap-4">
          <button
            onClick={openCalendar}
            className="rounded-lg p-2 transition-colors text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            title="Open Calendar"
          >
            <CalendarDays className="h-5 w-5" />
          </button>

          {/* Notifications */}
          <button
            className="relative rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            onClick={() => setIsNotificationPanelOpen(!isNotificationPanelOpen)}
          >
            <Bell className="h-5 w-5" />
            <span className="absolute right-1.5 top-1.5 flex h-2 w-2 rounded-full bg-red-500" />
          </button>

          {/* User Avatar */}
          <Avatar 
            className="h-8 w-8 cursor-pointer hover:ring-2 hover:ring-[#ed0923] hover:ring-offset-2 transition-all"
            onClick={onProfileClick}
          >
            {profile.avatarType === "upload" && profile.uploadedImage ? (
              <AvatarImage src={profile.uploadedImage} alt={`${profile.firstName} ${profile.lastName}`} />
            ) : (
              <AvatarFallback className={`${profile.selectedColor} text-xs text-white`}>
                {profile.initials}
              </AvatarFallback>
            )}
          </Avatar>
        </div>
        </div>
        
        {/* Notification Panel */}
        <NotificationPanel 
          isOpen={isNotificationPanelOpen} 
          onClose={() => setIsNotificationPanelOpen(false)} 
        />
      </header>
    </>
  );
}
