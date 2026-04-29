import { X, Shield, Check, AlertCircle, Copy, Download, LogOut, ChevronDown, Globe, Bell, Moon, Settings, User, Key } from "lucide-react";
import { Button } from "../ui/button";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { useUser } from "../../contexts/UserContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

const AUTH_TOKEN_KEY = "control-center-auth-token";
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

interface UserProfilePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function UserProfilePanel({ isOpen, onClose }: UserProfilePanelProps) {
  const navigate = useNavigate();
  const { profile, updateProfile } = useUser();
  
  // Preferences
  const [mfaEnabled, setMfaEnabled] = useState(true);
  const [notifications, setNotifications] = useState("All");
  const [theme, setTheme] = useState("Light");
  const [timezone, setTimezone] = useState("UTC-8 (Pacific)");
  
  // UI state
  const [copied, setCopied] = useState(false);
  const [showSignOutConfirm, setShowSignOutConfirm] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Initialize preferences from profile when it loads
  useEffect(() => {
    if (profile) {
      setMfaEnabled(profile.mfaEnabled ?? true);
      setNotifications(profile.notifications || "All");
      setTheme(profile.theme || "Light");
      setTimezone(profile.timezone || "UTC-8 (Pacific)");
    }
  }, [profile]);

  const savePreferences = async () => {
    setIsSaving(true);
    try {
      const token = typeof window !== "undefined" ? window.localStorage.getItem(AUTH_TOKEN_KEY) : null;
      if (!token) return;

      const response = await fetch(`${BACKEND_URL}/auth/me`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          theme,
          notifications,
          timezone,
        }),
      });

      if (response.ok) {
        const updatedUser = await response.json();
        // Update context with all updated fields
        updateProfile({
          firstName: updatedUser.first_name,
          lastName: updatedUser.last_name,
          phone: updatedUser.phone,
          location: updatedUser.location,
          bio: updatedUser.bio,
          theme: updatedUser.theme,
          notifications: updatedUser.notifications,
          timezone: updatedUser.timezone,
        });
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2000);
      }
    } catch (error) {
      console.error("Failed to save profile:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCopyToken = () => {
    const token = profile.accessToken || "cc_prod_a7b3f9e2d4c8k1m5n6p8q9r2s4t7v8w1";
    
    // Try modern clipboard API first
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(token).catch(() => {
        // Fallback to older method if clipboard API fails
        fallbackCopyTextToClipboard(token);
      });
    } else {
      // Use fallback for browsers that don't support clipboard API
      fallbackCopyTextToClipboard(token);
    }
    
    // Show copied notification
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fallbackCopyTextToClipboard = (text: string) => {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.width = "2em";
    textArea.style.height = "2em";
    textArea.style.padding = "0";
    textArea.style.border = "none";
    textArea.style.outline = "none";
    textArea.style.boxShadow = "none";
    textArea.style.background = "transparent";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand("copy");
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
    document.body.removeChild(textArea);
  };

  const handleViewProfile = () => {
    navigate("/profile");
    onClose();
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 z-50 h-full w-full max-w-lg bg-white shadow-2xl flex flex-col overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 border-b border-gray-200 bg-white px-6 py-4 z-10">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">
              Account Settings
            </h2>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-6 space-y-6">
          {/* User Identity */}
          <section>
            <div className="flex items-start gap-4">
              <div className="relative group">
                {profile.avatarType === "upload" && profile.uploadedImage ? (
                  <img
                    src={profile.uploadedImage}
                    alt="Profile"
                    className="h-16 w-16 rounded-full object-cover shadow-md cursor-pointer group-hover:opacity-90 transition-opacity"
                  />
                ) : (
                  <div className={`flex h-16 w-16 items-center justify-center rounded-full text-white text-xl font-semibold shadow-md cursor-pointer group-hover:opacity-90 transition-opacity ${profile.selectedColor}`}>
                    {profile.initials}
                  </div>
                )}
                <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                  <Settings className="h-5 w-5 text-white" />
                </div>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-semibold text-gray-900">
                    {profile.firstName} {profile.lastName}
                  </h3>
                  <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold bg-purple-100 text-purple-700">
                    {profile.role === "admin" ? "Admin" : "User"}
                  </span>
                </div>
                <p className="mt-1 text-sm text-gray-600">
                  {profile.email}
                </p>
                <p className="mt-0.5 text-xs text-gray-500">
                  Member since {profile.createdAt ? new Date(profile.createdAt).toLocaleDateString("en-US", { month: "short", year: "numeric" }) : "Jan 2024"}
                </p>
              </div>
            </div>
            
            {/* View Profile Button */}
            <div className="mt-4">
              <Button
                variant="outline"
                className="w-full gap-2 border-[#ed0923] text-[#ed0923] hover:bg-red-50 hover:text-[#b8071c]"
                onClick={handleViewProfile}
              >
                <User className="h-4 w-4" />
                View & Edit Profile
              </Button>
            </div>
          </section>

          <div className="border-t border-gray-200" />

          {/* Access & Permissions */}
          <section>
            <h4 className="text-sm font-semibold text-gray-900 mb-3">
              Access & Permissions
            </h4>
            <div className="space-y-3">
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-600 uppercase tracking-wider">
                    Role
                  </span>
                  <span className="text-sm font-semibold text-gray-900">
                    {profile.role === "admin" ? "Admin" : "User"}
                  </span>
                </div>
              </div>
              
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-600 uppercase tracking-wider">
                    Environment Access
                  </span>
                  <span className="text-sm font-semibold text-gray-900">
                    {profile.allowedEnvironments ? (
                      profile.allowedEnvironments.split(",").map(env => env.trim()).join(", ")
                    ) : (
                      "No access"
                    )}
                  </span>
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-600 uppercase tracking-wider">
                    Approval Authority
                  </span>
                  {profile.approvalAuthority ? (
                    <span className="inline-flex items-center gap-1 text-sm font-semibold text-green-600">
                      <Check className="h-4 w-4" />
                      Enabled
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-sm font-semibold text-gray-500">
                      <AlertCircle className="h-4 w-4" />
                      Disabled
                    </span>
                  )}
                </div>
              </div>
            </div>
          </section>

          <div className="border-t border-gray-200" />

          {/* Password & Security */}
          <section>
            <h4 className="text-sm font-semibold text-gray-900 mb-3">
              Password & Security
            </h4>
            <div className="space-y-3">
              {/* Change Password */}
              <div className="rounded-lg border border-gray-200 bg-white p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Key className="h-4 w-4 text-gray-600" />
                    <span className="text-sm font-medium text-gray-900">
                      Password
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-[#ed0923] hover:text-[#b8071c]"
                  >
                    Change
                  </Button>
                </div>
                <p className="mt-1 text-xs text-gray-600 ml-6">
                  Last changed 45 days ago
                </p>
              </div>

              {/* MFA Status */}
              <div className="rounded-lg border border-gray-200 bg-white p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Shield className={`h-4 w-4 ${mfaEnabled ? 'text-green-600' : 'text-gray-400'}`} />
                    <span className="text-sm font-medium text-gray-900">
                      Multi-Factor Authentication
                    </span>
                  </div>
                  {mfaEnabled ? (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-green-600">
                      <Check className="h-3 w-3" />
                      Enabled
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-orange-600">
                      <AlertCircle className="h-3 w-3" />
                      Disabled
                    </span>
                  )}
                </div>
              </div>

              {/* Active Sessions */}
              <div className="rounded-lg border border-gray-200 bg-white p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-900">
                    Active Sessions
                  </span>
                  <span className="text-sm font-semibold text-blue-600">
                    3 active
                  </span>
                </div>
                <div className="space-y-1.5 text-xs text-gray-600">
                  <div className="flex items-center justify-between">
                    <span>Web (Current)</span>
                    <span className="text-gray-500">Now</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>CLI (macOS)</span>
                    <span className="text-gray-500">2h ago</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>API Integration</span>
                    <span className="text-gray-500">5h ago</span>
                  </div>
                </div>
              </div>

              {/* API Tokens */}
              <div className="rounded-lg border border-gray-200 bg-white p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-900">
                    API Tokens
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-[#ed0923] hover:text-[#b8071c]"
                  >
                    Manage
                  </Button>
                </div>
                <p className="mt-1 text-xs text-gray-600">
                  2 active tokens
                </p>
              </div>
            </div>
          </section>

          <div className="border-t border-gray-200" />

          {/* Preferences */}
          <section>
            <h4 className="text-sm font-semibold text-gray-900 mb-3">
              Preferences
            </h4>
            <div className="space-y-3">
              {/* Theme */}
              <div>
                <label className="text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Theme
                </label>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="mt-1.5 w-full flex items-center justify-between rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-900 hover:bg-gray-50 transition-colors">
                      <span className="flex items-center gap-2">
                        <Moon className="h-4 w-4 text-gray-600" />
                        {theme}
                      </span>
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-full">
                    <DropdownMenuItem onClick={() => setTheme("Light")}>
                      Light
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setTheme("Dark")}>
                      Dark
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setTheme("System")}>
                      System
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              {/* Notifications */}
              <div>
                <label className="text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Notifications
                </label>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="mt-1.5 w-full flex items-center justify-between rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-900 hover:bg-gray-50 transition-colors">
                      <span className="flex items-center gap-2">
                        <Bell className="h-4 w-4 text-gray-600" />
                        {notifications}
                      </span>
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-full">
                    <DropdownMenuItem onClick={() => setNotifications("All")}>
                      All
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setNotifications("Important")}>
                      Important Only
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setNotifications("None")}>
                      None
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              {/* Timezone */}
              <div>
                <label className="text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Timezone
                </label>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="mt-1.5 w-full flex items-center justify-between rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-900 hover:bg-gray-50 transition-colors">
                      <span className="flex items-center gap-2">
                        <Globe className="h-4 w-4 text-gray-600" />
                        {timezone}
                      </span>
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-full">
                    <DropdownMenuItem onClick={() => setTimezone("UTC-8 (Pacific)")}>
                      UTC-8 (Pacific)
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setTimezone("UTC-5 (Eastern)")}>
                      UTC-5 (Eastern)
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setTimezone("UTC+0 (London)")}>
                      UTC+0 (London)
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setTimezone("UTC+1 (Berlin)")}>
                      UTC+1 (Berlin)
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              {/* Save Button */}
              <div className="mt-4 pt-3 border-t border-gray-200">
                <Button
                  onClick={savePreferences}
                  disabled={isSaving}
                  className="w-full bg-[#ed0923] hover:bg-[#b8071c] text-white"
                >
                  {isSaving ? "Saving..." : "Save Preferences"}
                </Button>
                {saveSuccess && (
                  <p className="mt-2 text-xs text-green-600 text-center">
                    ✓ Preferences saved successfully
                  </p>
                )}
              </div>
            </div>
          </section>

          <div className="border-t border-gray-200" />

          {/* CLI Access */}
          <section>
            <h4 className="text-sm font-semibold text-gray-900 mb-3">
              CLI Access
            </h4>
            <div className="space-y-3">
              {/* Token */}
              <div>
                <label className="text-xs font-medium text-gray-600 uppercase tracking-wider">
                  Access Token
                </label>
                <div className="mt-1.5 flex items-center gap-2">
                  <div className="flex-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
                    <code className="text-xs font-mono text-gray-600">
                      {profile.accessToken ? `${profile.accessToken.substring(0, 8)}...${profile.accessToken.substring(profile.accessToken.length - 8)}` : "cc_prod_a7b3f9e2d4c8..."}
                    </code>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCopyToken}
                    className="h-9 gap-2"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    Copy
                  </Button>
                </div>
                <p className="mt-1.5 text-xs text-gray-500">
                  Use this token to authenticate CLI commands
                </p>
                {copied && (
                  <p className="mt-1 text-xs text-green-600">
                    Copied to clipboard!
                  </p>
                )}
              </div>

              {/* CLI Install */}
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                <div className="flex items-start gap-2">
                  <Download className="h-4 w-4 text-blue-600 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-blue-900">
                      Install Control Center CLI
                    </p>
                    <p className="mt-1 text-xs text-blue-700">
                      npm install -g @control-center/cli
                    </p>
                    <a
                      href="#"
                      className="mt-2 inline-block text-xs font-medium text-[#ed0923] hover:text-[#b8071c]"
                    >
                      View documentation →
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Footer - Logout */}
        <div className="sticky bottom-0 border-t border-gray-200 bg-white px-6 py-4">
          <Button
            variant="outline"
            className="w-full gap-2 border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
            onClick={() => setShowSignOutConfirm(true)}
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </Button>
        </div>
      </div>

      {/* Sign Out Confirmation */}
      {showSignOutConfirm && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm">
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-sm rounded-lg bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                Sign Out
              </h3>
              <button
                onClick={() => setShowSignOutConfirm(false)}
                className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="mt-4 text-sm text-gray-600">
              Are you sure you want to sign out? This will end your current session.
            </p>
            <div className="mt-6 flex gap-2 justify-end">
              <Button
                variant="outline"
                onClick={() => setShowSignOutConfirm(false)}
              >
                Cancel
              </Button>
              <Button
                variant="outline"
                className="border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
                onClick={() => {
                  setShowSignOutConfirm(false);
                  onClose();
                  navigate("/login", { state: { signedOut: true } });
                }}
              >
                Sign Out
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}