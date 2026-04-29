import { createContext, useContext, useState, ReactNode, useEffect } from "react";

const USER_ROLE_KEY = "control-center-user-role";
const AUTH_TOKEN_KEY = "control-center-auth-token";
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

interface UserProfile {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  bio: string;
  location: string;
  jobTitle: string;
  department: string;
  team: string;
  manager: string;
  employeeId: string;
  avatarType: "color" | "upload";
  selectedColor: string;
  uploadedImage: string | null;
  initials: string;
  role: "admin" | "user";
  createdAt?: string;
  // New settings fields
  mfaEnabled?: boolean;
  approvalAuthority?: boolean;
  allowedEnvironments?: string;
  theme?: string;
  notifications?: string;
  timezone?: string;
  accessToken?: string;
}

interface UserContextType {
  profile: UserProfile;
  updateProfile: (updates: Partial<UserProfile>) => void;
  setUserRole: (role: "admin" | "user") => void;
  isLoading: boolean;
  refetchProfile: () => Promise<void>;
}

const defaultProfile: UserProfile = {
  id: "u_unknown",
  firstName: "User",
  lastName: "Profile",
  email: "user@company.com",
  phone: "+1 (555) 000-0000",
  bio: "",
  location: "",
  jobTitle: "",
  department: "",
  team: "",
  manager: "",
  employeeId: "",
  avatarType: "color",
  selectedColor: "bg-blue-500",
  uploadedImage: null,
  initials: "UP",
  role: "user",
  createdAt: new Date().toISOString(),
};

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<UserProfile>(defaultProfile);
  const [isLoading, setIsLoading] = useState(true);

  // Create refetch function that can be called from anywhere
  const refetchProfile = async () => {
    try {
      const token = typeof window !== "undefined" ? window.localStorage.getItem(AUTH_TOKEN_KEY) : null;
      if (!token) {
        setIsLoading(false);
        return;
      }

      const response = await fetch(`${BACKEND_URL}/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const userData = await response.json();
        const initials = `${userData.first_name?.[0] || userData.name?.[0] || ""}${userData.last_name?.[0] || userData.name?.split(" ")[1]?.[0] || ""}`.toUpperCase();
        
        // Map role from backend to frontend role
        const frontendRole = userData.role === "root" || userData.role === "domain_admin" ? "admin" : "user";
        
        setProfile({
          id: userData.id,
          firstName: userData.first_name || userData.name?.split(" ")[0] || "",
          lastName: userData.last_name || userData.name?.split(" ").slice(1).join(" ") || "",
          email: userData.email,
          phone: userData.phone || "",
          bio: userData.bio || "",
          location: userData.location || "",
          jobTitle: userData.job_title || "",
          department: userData.department || "",
          team: userData.team || "",
          manager: userData.manager || "",
          employeeId: userData.employee_id || "",
          avatarType: (userData.avatar_type as "color" | "upload") || "color",
          selectedColor: userData.selected_color || "bg-blue-500",
          uploadedImage: userData.uploaded_image || null,
          initials: initials || "UP",
          role: frontendRole,
          createdAt: userData.created_at,
          mfaEnabled: userData.mfa_enabled,
          approvalAuthority: userData.approval_authority,
          allowedEnvironments: userData.allowed_environments,
          theme: userData.theme || "Light",
          notifications: userData.notifications || "All",
          timezone: userData.timezone || "UTC-8 (Pacific)",
          accessToken: userData.access_token,
        });

        // Save role to localStorage
        if (typeof window !== "undefined") {
          window.localStorage.setItem(USER_ROLE_KEY, frontendRole);
        }
      }
    } catch (error) {
      console.error("Failed to fetch user profile:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch user profile from backend on mount
  useEffect(() => {
    refetchProfile();
  }, []);

  const updateProfile = (updates: Partial<UserProfile>) => {
    setProfile((prev) => ({ ...prev, ...updates }));
  };

  const setUserRole = (role: "admin" | "user") => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(USER_ROLE_KEY, role);
    }
    setProfile((prev) => ({ ...prev, role }));
  };

  return (
    <UserContext.Provider value={{ profile, updateProfile, setUserRole, isLoading, refetchProfile }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error("useUser must be used within a UserProvider");
  }
  return context;
}
