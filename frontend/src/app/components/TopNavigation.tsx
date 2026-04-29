import { Bell, ChevronDown } from "lucide-react";
import { Link } from "react-router";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { Button } from "./ui/button";
import { useUser } from "../contexts/UserContext";
import { useState } from "react";
import { NotificationPanel } from "./notifications/NotificationPanel";
import { ImageWithFallback } from "./figma/ImageWithFallback";
import logoImg from "figma:asset/78cbd1f20e12e98c3e07fe4c9b0e4faacfef3d82.png";

export function TopNavigation({ 
  activePage = "Dashboard",
  onProfileClick,
  userRole = "admin"
}: { 
  activePage?: string;
  onProfileClick?: () => void;
  userRole?: "admin" | "user";
}) {
  const { profile } = useUser();
  const [isNotificationPanelOpen, setIsNotificationPanelOpen] = useState(false);
  
  // Define navigation items based on user role
  const getNavItems = () => {
    if (userRole === "user") {
      return [
        { label: "Home", active: activePage === "Home", path: "/user-home" },
        { label: "User", active: activePage === "User", secondary: true, path: "/profile" },
      ];
    }
    
    // Admin navigation
    return [
      { label: "Dashboard", active: activePage === "Dashboard", path: "/" },
      { label: "Jobs", active: activePage === "Jobs", path: "/jobs" },
      { label: "Connectors", active: activePage === "Connectors", path: "/connectors" },
      { label: "Runs", active: activePage === "Runs", path: "/runs" },
      { label: "Research", active: activePage === "Research", path: "/research" },
      { label: "Approvals", active: activePage === "Approvals", path: "/approvals" },
      { label: "Risk", active: activePage === "Risk", path: "/risk" },
      { label: "Admin", active: activePage === "Admin", secondary: true, path: "/admin" },
    ];
  };

  const navItems = getNavItems();

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="flex h-16 items-center justify-between px-6">
        {/* Left: Logo and Nav */}
        <div className="flex items-center gap-8">
          <Link to={userRole === "user" ? "/user-home" : "/"} className="flex items-center gap-2">
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
                    : item.secondary
                    ? "text-gray-400 hover:text-gray-600"
                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>

        {/* Right: Notifications, User */}
        <div className="flex items-center gap-4">
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
  );
}