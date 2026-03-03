import { Bell, CalendarDays, ChevronDown } from "lucide-react";
import { Link } from "react-router";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import { useUser } from "../contexts/UserContext";
import { useState } from "react";
import { NotificationPanel } from "./notifications/NotificationPanel";
import ChatAgent from "./user/ChatAgent";
import { pendingRequiredActionsCount } from "../pages/requiredActionsData";

export function UserNavigation({ 
  activePage = "Dashboard",
  activeSubPage,
  onProfileClick
}: { 
  activePage?: string;
  activeSubPage?:
    | "Pre Built Forms"
    | "Saved Templates"
    | "My Jobs"
    | "Pending Approvals"
    | "Running Jobs"
    | "Promotions"
    | "Edits";
  onProfileClick?: () => void;
}) {
  const { profile } = useUser();
  const [isNotificationPanelOpen, setIsNotificationPanelOpen] = useState(false);
  const isFormsActive = activePage === "Forms";
  const isJobsActive = activePage === "Jobs";
  const isPromotionsActive = activePage === "Promotions & Edits";
  
  const navItems = [
    { label: "Dashboard", active: activePage === "Dashboard", path: "/user-home" },
    {
      label: "Required Actions",
      active: activePage === "Required Actions",
      path: "/required-actions",
      badge: pendingRequiredActionsCount(),
    },
  ];
  const jobsItems = [
    { label: "My Jobs", path: "/jobs/my-jobs" },
    { label: "Pending Approvals", path: "/jobs/pending-approvals" },
    { label: "Running Jobs", path: "/jobs/running-jobs" },
  ];
  const promotionsItems = [
    { label: "Promotions", path: "/promotions-edits/promotions" },
    { label: "Edits", path: "/promotions-edits/edits" },
  ];
  const formsItems = [
    { label: "Pre Built Forms", path: "/forms/pre-built-forms" },
    { label: "Saved Templates", path: "/forms/saved-templates" },
  ];

  return (
    <>
      <header className="border-b border-gray-200 bg-white">
        <div className="flex h-16 items-center justify-between px-6">
        {/* Left: Logo and Nav */}
        <div className="flex items-center gap-8">
          <Link to="/user-home" className="flex items-center gap-2">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded bg-[#ed0923] flex items-center justify-center">
                <span className="text-white font-bold text-sm">T</span>
              </div>
              <span className="text-lg font-semibold text-gray-900">Toyota Control Center</span>
            </div>
          </Link>
          <nav className="flex items-center gap-1">
            {navItems.map((item) => (
              <Link
                key={item.label}
                to={item.path}
                className={`px-3 py-2 text-sm font-medium transition-colors rounded-md ${
                  item.active
                    ? "bg-gray-100 text-gray-900"
                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                }`}
              >
                <span className="inline-flex items-center gap-2">
                  {item.label}
                  {typeof item.badge === "number" && item.badge > 0 && (
                    <span className="inline-flex min-w-[18px] items-center justify-center rounded-full bg-[#ed0923] px-1.5 py-0.5 text-[10px] font-semibold text-white">
                      {item.badge}
                    </span>
                  )}
                </span>
              </Link>
            ))}
            <div className="group relative">
              <Link
                to="/forms"
                className={`flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isFormsActive
                    ? "bg-gray-100 text-gray-900"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
              >
                Forms
                <ChevronDown className="h-4 w-4" />
              </Link>
              <div className="absolute left-0 top-full z-50 hidden min-w-[210px] pt-2 group-hover:block">
                <div className="rounded-md border border-gray-200 bg-white py-1 shadow-lg">
                  {formsItems.map((item) => (
                    <Link
                      key={item.label}
                      to={item.path}
                      className={`block px-3 py-2 text-sm ${
                        activeSubPage === item.label
                          ? "bg-red-50 text-[#ed0923]"
                          : "text-gray-700 hover:bg-gray-50"
                      }`}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
            <div className="group relative">
              <Link
                to="/jobs/my-jobs"
                className={`flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isJobsActive
                    ? "bg-gray-100 text-gray-900"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
              >
                Jobs
                <ChevronDown className="h-4 w-4" />
              </Link>
              <div className="absolute left-0 top-full z-50 hidden min-w-[220px] pt-2 group-hover:block">
                <div className="rounded-md border border-gray-200 bg-white py-1 shadow-lg">
                  {jobsItems.map((item) => (
                    <Link
                      key={item.label}
                      to={item.path}
                      className={`block px-3 py-2 text-sm ${
                        activeSubPage === item.label
                          ? "bg-red-50 text-[#ed0923]"
                          : "text-gray-700 hover:bg-gray-50"
                      }`}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
            <div className="group relative">
              <Link
                to="/promotions-edits/promotions"
                className={`flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isPromotionsActive
                    ? "bg-gray-100 text-gray-900"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
              >
                Promotions & Edits
                <ChevronDown className="h-4 w-4" />
              </Link>
              <div className="absolute left-0 top-full z-50 hidden min-w-[180px] pt-2 group-hover:block">
                <div className="rounded-md border border-gray-200 bg-white py-1 shadow-lg">
                  {promotionsItems.map((item) => (
                    <Link
                      key={item.label}
                      to={item.path}
                      className={`block px-3 py-2 text-sm ${
                        activeSubPage === item.label
                          ? "bg-red-50 text-[#ed0923]"
                          : "text-gray-700 hover:bg-gray-50"
                      }`}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
            <span className="px-3 py-2 text-sm font-medium text-gray-400">User</span>
          </nav>
        </div>

        {/* Right: Notifications, User */}
        <div className="flex items-center gap-4">
          <Link
            to="/calendar"
            className={`rounded-lg p-2 transition-colors ${
              activePage === "Calendar"
                ? "bg-red-50 text-[#ed0923]"
                : "text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            }`}
          >
            <CalendarDays className="h-5 w-5" />
          </Link>

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

      <ChatAgent />
    </>
  );
}
