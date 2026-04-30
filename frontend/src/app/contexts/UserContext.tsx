import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { getCurrentUser } from "../lib/controlCenterApi";

const USER_ROLE_KEY = "control-center-user-role";

interface UserProfile {
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
  role: "admin" | "user"; // Add role field
}

interface UserContextType {
  profile: UserProfile;
  updateProfile: (updates: Partial<UserProfile>) => void;
  setUserRole: (role: "admin" | "user") => void;
}

const defaultProfile: UserProfile = {
  firstName: "Sarah",
  lastName: "Chen",
  email: "sarah.chen@company.com",
  phone: "+1 (555) 123-4567",
  bio: "Platform Admin at Control Center. Passionate about data governance and AI safety.",
  location: "San Francisco, CA",
  jobTitle: "Senior Platform Engineer",
  department: "Data Platform",
  team: "AI Governance",
  manager: "Alex Rodriguez",
  employeeId: "EMP-2847",
  avatarType: "color",
  selectedColor: "bg-blue-500",
  uploadedImage: null,
  initials: "SC",
  role: "admin", // Default to admin
};

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<UserProfile>(() => {
    if (typeof window === "undefined") {
      return defaultProfile;
    }

    const savedRole = window.localStorage.getItem(USER_ROLE_KEY);
    return savedRole === "user" || savedRole === "admin"
      ? { ...defaultProfile, role: savedRole }
      : defaultProfile;
  });

  const updateProfile = (updates: Partial<UserProfile>) => {
    setProfile((prev) => ({ ...prev, ...updates }));
  };

  useEffect(() => {
    let ignore = false;

    const loadBackendUser = async () => {
      if (typeof window === "undefined") {
        return;
      }

      const token = window.localStorage.getItem("control-center-auth-token");
      if (!token) {
        return;
      }

      try {
        const currentUser = await getCurrentUser(token);
        if (ignore) return;

        const nameParts = (currentUser.name ?? "").trim().split(/\s+/).filter(Boolean);
        const firstName = nameParts[0] || defaultProfile.firstName;
        const lastName = nameParts.slice(1).join(" ") || defaultProfile.lastName;
        const derivedInitials = `${firstName[0] ?? ""}${lastName[0] ?? ""}`.toUpperCase() || defaultProfile.initials;
        const mappedRole: "admin" | "user" = currentUser.role === "user" ? "user" : "admin";

        setProfile((prev) => ({
          ...prev,
          firstName,
          lastName,
          email: currentUser.email ?? prev.email,
          department: currentUser.domain ?? prev.department,
          employeeId: currentUser.id ?? prev.employeeId,
          jobTitle: (currentUser.role ?? prev.jobTitle).replaceAll("_", " "),
          initials: derivedInitials,
          role: mappedRole,
        }));
      } catch {
        // Keep local defaults when the backend is unavailable.
      }
    };

    void loadBackendUser();

    return () => {
      ignore = true;
    };
  }, []);

  const setUserRole = (role: "admin" | "user") => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(USER_ROLE_KEY, role);
    }
    setProfile((prev) => ({ ...prev, role }));
  };

  return (
    <UserContext.Provider value={{ profile, updateProfile, setUserRole }}>
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
