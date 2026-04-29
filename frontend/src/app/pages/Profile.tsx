import { useState, useEffect } from "react";
import { ArrowLeft, Upload, Check } from "lucide-react";
import { Button } from "../components/ui/button";
import { useNavigate } from "react-router";
import { useUser } from "../contexts/UserContext";

const AUTH_TOKEN_KEY = "control-center-auth-token";
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

const defaultAvatarColors = [
  { name: "Blue", color: "bg-blue-500" },
  { name: "Purple", color: "bg-purple-500" },
  { name: "Green", color: "bg-green-500" },
  { name: "Orange", color: "bg-orange-500" },
  { name: "Pink", color: "bg-pink-500" },
  { name: "Indigo", color: "bg-indigo-500" },
  { name: "Red", color: "bg-red-500" },
  { name: "Teal", color: "bg-teal-500" },
];

export default function Profile() {
  const navigate = useNavigate();
  const { profile, updateProfile } = useUser();
  
  // Profile Picture State
  const [avatarType, setAvatarType] = useState<"color" | "upload">(profile.avatarType);
  const [selectedColor, setSelectedColor] = useState(profile.selectedColor);
  const [uploadedImage, setUploadedImage] = useState<string | null>(profile.uploadedImage);
  const [initials, setInitials] = useState(profile.initials);

  // Basic Information State
  const [firstName, setFirstName] = useState(profile.firstName);
  const [lastName, setLastName] = useState(profile.lastName);
  const [email, setEmail] = useState(profile.email);
  const [phone, setPhone] = useState(profile.phone);
  const [bio, setBio] = useState(profile.bio);
  const [location, setLocation] = useState(profile.location);

  // Organization State
  const [jobTitle, setJobTitle] = useState(profile.jobTitle);
  const [department, setDepartment] = useState(profile.department);
  const [team, setTeam] = useState(profile.team);
  const [manager, setManager] = useState(profile.manager);
  const [employeeId, setEmployeeId] = useState(profile.employeeId);

  // UI State
  const [isSavingPicture, setIsSavingPicture] = useState(false);
  const [isSavingBasicInfo, setIsSavingBasicInfo] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load profile data when component mounts
  useEffect(() => {
    setAvatarType(profile.avatarType);
    setSelectedColor(profile.selectedColor);
    setUploadedImage(profile.uploadedImage);
    setInitials(profile.initials);
    setFirstName(profile.firstName);
    setLastName(profile.lastName);
    setEmail(profile.email);
    setPhone(profile.phone);
    setBio(profile.bio);
    setLocation(profile.location);
    setJobTitle(profile.jobTitle);
    setDepartment(profile.department);
    setTeam(profile.team);
    setManager(profile.manager);
    setEmployeeId(profile.employeeId);
  }, [profile]);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setUploadedImage(reader.result as string);
        setAvatarType("upload");
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSaveProfilePicture = async () => {
    setIsSavingPicture(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = typeof window !== "undefined" ? window.localStorage.getItem(AUTH_TOKEN_KEY) : null;
      if (!token) {
        setErrorMessage("Not authenticated. Please log in again.");
        return;
      }

      const response = await fetch(`${BACKEND_URL}/auth/me`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          avatar_type: avatarType,
          uploaded_image: uploadedImage,
          selected_color: selectedColor,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to save profile picture");
      }

      const updatedUser = await response.json();
      
      // Update context with new avatar data
      updateProfile({
        avatarType: updatedUser.avatar_type,
        uploadedImage: updatedUser.uploaded_image,
        selectedColor: updatedUser.selected_color,
      });

      setSuccessMessage("Profile picture saved successfully!");
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (error) {
      console.error("Failed to save profile picture:", error);
      setErrorMessage("Failed to save profile picture. Please try again.");
    } finally {
      setIsSavingPicture(false);
    }
  };

  const handleSaveBasicInfo = async () => {
    setIsSavingBasicInfo(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = typeof window !== "undefined" ? window.localStorage.getItem(AUTH_TOKEN_KEY) : null;
      if (!token) {
        setErrorMessage("Not authenticated. Please log in again.");
        return;
      }

      const response = await fetch(`${BACKEND_URL}/auth/me`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          phone,
          location,
          bio,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to save basic information");
      }

      const updatedUser = await response.json();
      
      // Update context with new profile data
      updateProfile({
        firstName: updatedUser.first_name,
        lastName: updatedUser.last_name,
        phone: updatedUser.phone,
        location: updatedUser.location,
        bio: updatedUser.bio,
      });

      setSuccessMessage("Basic information saved successfully!");
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (error) {
      console.error("Failed to save basic information:", error);
      setErrorMessage("Failed to save basic information. Please try again.");
    } finally {
      setIsSavingBasicInfo(false);
    }
  };



  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-5xl px-6 py-6">
          <button
            onClick={() => navigate(-1)}
            className="mb-4 flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Profile Settings</h1>
            <p className="mt-2 text-sm text-gray-600">
              Manage your personal information and profile settings
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-5xl px-6 py-8 space-y-6">
        {/* Messages */}
        {successMessage && (
          <div className="rounded-lg border border-green-200 bg-green-50 p-4">
            <p className="text-sm font-medium text-green-800">✓ {successMessage}</p>
          </div>
        )}
        {errorMessage && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-medium text-red-800">✗ {errorMessage}</p>
          </div>
        )}

        {/* Profile Picture Section */}
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900">Profile Picture</h2>
            <p className="mt-1 text-sm text-gray-600">
              Upload a custom image or choose a color for your avatar
            </p>
          </div>

          <div className="space-y-6">
            {/* Current Avatar Preview */}
            <div className="flex items-center gap-6">
              <div className="flex items-center justify-center">
                {avatarType === "upload" && uploadedImage ? (
                  <img
                    src={uploadedImage}
                    alt="Profile"
                    className="h-24 w-24 rounded-full object-cover shadow-md"
                  />
                ) : (
                  <div
                    className={`flex h-24 w-24 items-center justify-center rounded-full text-white text-2xl font-semibold shadow-md ${selectedColor}`}
                  >
                    {initials}
                  </div>
                )}
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-gray-900">Current Avatar</h3>
                <p className="mt-1 text-xs text-gray-600">
                  This is how your avatar appears across the platform
                </p>
              </div>
            </div>

            {/* Upload Custom Image */}
            <div>
              <label className="text-sm font-semibold text-gray-900">
                Upload Custom Image
              </label>
              <div className="mt-2">
                <label
                  htmlFor="avatar-upload"
                  className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <Upload className="h-4 w-4" />
                  Choose File
                </label>
                <input
                  id="avatar-upload"
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleImageUpload}
                />
                <p className="mt-2 text-xs text-gray-500">
                  JPG, PNG or GIF. Max size 2MB. Recommended 400x400px.
                </p>
              </div>
            </div>

            {/* Default Color Avatars */}
            <div>
              <label className="text-sm font-semibold text-gray-900">
                Or Choose a Color
              </label>
              <div className="mt-3 grid grid-cols-8 gap-3">
                {defaultAvatarColors.map((avatar) => (
                  <button
                    key={avatar.name}
                    onClick={() => {
                      setSelectedColor(avatar.color);
                      setAvatarType("color");
                    }}
                    className={`relative h-12 w-12 rounded-full ${avatar.color} transition-transform hover:scale-110 ${
                      avatarType === "color" && selectedColor === avatar.color
                        ? "ring-2 ring-blue-500 ring-offset-2"
                        : ""
                    }`}
                  >
                    {avatarType === "color" && selectedColor === avatar.color && (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Check className="h-5 w-5 text-white" />
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Initials */}
            <div>
              <label className="text-sm font-semibold text-gray-900">
                Avatar Initials
              </label>
              <input
                type="text"
                value={initials}
                onChange={(e) => setInitials(e.target.value.toUpperCase().slice(0, 2))}
                maxLength={2}
                className="mt-2 block w-full max-w-xs rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="SC"
              />
              <p className="mt-2 text-xs text-gray-500">
                Enter 1-2 characters for your avatar (used with color avatars)
              </p>
            </div>

            {/* Save Button */}
            <div className="flex justify-end pt-4 border-t border-gray-200">
              <Button
                onClick={handleSaveProfilePicture}
                disabled={isSavingPicture}
                className="gap-2 bg-blue-600 text-white hover:bg-blue-700"
              >
                <Check className="h-4 w-4" />
                {isSavingPicture ? "Saving..." : "Save Profile Picture"}
              </Button>
            </div>
          </div>
        </section>

        {/* Basic Information Section */}
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900">Basic Information</h2>
            <p className="mt-1 text-sm text-gray-600">
              Update your personal details and contact information
            </p>
          </div>

          <div className="space-y-6">
            {/* Name Fields */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-semibold text-gray-900">
                  First Name
                </label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="mt-2 block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="text-sm font-semibold text-gray-900">
                  Last Name
                </label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="mt-2 block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Email */}
            <div>
              <label className="text-sm font-semibold text-gray-900">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                disabled
                className="mt-2 block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 cursor-not-allowed"
              />
              <p className="mt-2 text-xs text-gray-500">
                Email address is preset and cannot be changed
              </p>
            </div>

            {/* Phone */}
            <div>
              <label className="text-sm font-semibold text-gray-900">
                Phone Number
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="mt-2 block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Location */}
            <div>
              <label className="text-sm font-semibold text-gray-900">
                Location
              </label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                className="mt-2 block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="City, State/Country"
              />
            </div>

            {/* Bio */}
            <div>
              <label className="text-sm font-semibold text-gray-900">
                Bio
              </label>
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                rows={4}
                className="mt-2 block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                placeholder="Tell us about yourself..."
              />
              <p className="mt-2 text-xs text-gray-500">
                Brief description for your profile. Maximum 200 characters.
              </p>
            </div>

            {/* Save Button */}
            <div className="flex justify-end pt-4 border-t border-gray-200">
              <Button
                onClick={handleSaveBasicInfo}
                disabled={isSavingBasicInfo}
                className="gap-2 bg-blue-600 text-white hover:bg-blue-700"
              >
                <Check className="h-4 w-4" />
                {isSavingBasicInfo ? "Saving..." : "Save Basic Information"}
              </Button>
            </div>
          </div>
        </section>

        {/* Organization/Team Information Section */}
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Organization & Team Information
            </h2>
            <p className="mt-1 text-sm text-gray-600">
              Your role and team details within the organization (preset and managed by HR)
            </p>
          </div>

          <div className="space-y-6">
            {/* Job Title */}
            <div>
              <label className="text-sm font-semibold text-gray-900">
                Job Title
              </label>
              <input
                type="text"
                value={jobTitle}
                disabled
                className="mt-2 block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 cursor-not-allowed"
              />
            </div>

            {/* Department and Team */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-semibold text-gray-900">
                  Department
                </label>
                <input
                  type="text"
                  value={department}
                  disabled
                  className="mt-2 block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 cursor-not-allowed"
                />
              </div>
              <div>
                <label className="text-sm font-semibold text-gray-900">
                  Team
                </label>
                <input
                  type="text"
                  value={team}
                  disabled
                  className="mt-2 block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 cursor-not-allowed"
                />
              </div>
            </div>

            {/* Manager */}
            <div>
              <label className="text-sm font-semibold text-gray-900">
                Manager
              </label>
              <input
                type="text"
                value={manager}
                disabled
                className="mt-2 block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 cursor-not-allowed"
              />
            </div>

            {/* Employee ID */}
            <div>
              <label className="text-sm font-semibold text-gray-900">
                Employee ID
              </label>
              <input
                type="text"
                value={employeeId}
                disabled
                className="mt-2 block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 cursor-not-allowed"
              />
              <p className="mt-2 text-xs text-gray-500">
                Organization information is managed by HR. Contact your administrator for changes.
              </p>
            </div>
          </div>
        </section>

        {/* Control Center CLI Installation Section */}
        <section className="rounded-lg border border-gray-700 bg-gray-900 p-6 shadow-sm">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-white">
              Control Center CLI
            </h2>
            <p className="mt-1 text-sm text-gray-400">
              Install the Control Center CLI to manage jobs directly from your terminal.
            </p>
          </div>

          <div className="space-y-6">
            {/* Installation Instructions */}
            <div>
              <label className="text-sm font-semibold text-white">
                Installation
              </label>
              <p className="mt-2 text-sm text-gray-300">
                Install the Control Center CLI to manage jobs from your terminal:
              </p>
              <div className="mt-3 rounded-lg bg-gray-800 p-4 border border-gray-700">
                <code className="text-sm font-mono text-emerald-400">
                  npm install -g @control-center/cli
                </code>
              </div>
              <p className="mt-2 text-xs text-gray-500">
                Works from any directory after installation. Run <code className="text-gray-300 font-mono">cc --help</code> to see available commands.
              </p>
            </div>

            {/* Getting Started */}
            <div>
              <label className="text-sm font-semibold text-white">
                Getting Started
              </label>
              <p className="mt-2 text-sm text-gray-300">
                After installing, run <code className="text-gray-300 font-mono">cc login</code> to connect your account. You'll be prompted for your email.
              </p>
            </div>

            {/* Documentation Link */}
            <div className="pt-2">
              <a
                href="#"
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-700 px-4 py-2 text-sm font-medium text-white transition-colors"
              >
                View CLI Documentation
                <ArrowLeft className="h-4 w-4 rotate-180" />
              </a>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}