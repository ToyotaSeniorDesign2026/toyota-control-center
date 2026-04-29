import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router";
import { ArrowRight, Shield, CheckCircle, AlertCircle } from "lucide-react";
import { Button } from "../components/ui/button";
import { useUser } from "../contexts/UserContext";

const AUTH_TOKEN_KEY = "control-center-auth-token";
const BACKEND_URL = "http://localhost:8000";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUserRole, refetchProfile } = useUser();
  const [email, setEmail] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);
  const [showErrorMessage, setShowErrorMessage] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Check if user was just signed out
  useEffect(() => {
    if (location.state?.signedOut) {
      setShowSuccessMessage(true);
      window.history.replaceState({}, document.title);
      setTimeout(() => setShowSuccessMessage(false), 3000);
    }
  }, [location]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setShowErrorMessage(false);
    
    try {
      const response = await fetch(`${BACKEND_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) {
        setErrorMessage("Invalid email. User not found in database.");
        setShowErrorMessage(true);
        setIsLoading(false);
        return;
      }

      const data = await response.json();
      
      // Store token and user info
      window.localStorage.setItem(AUTH_TOKEN_KEY, data.access_token);
      window.localStorage.setItem("user-info", JSON.stringify(data.user));
      
      // Set user role in context
      const roleMap: Record<string, "admin" | "user"> = {
        root: "admin",
        domain_admin: "admin",
        user: "user",
      };
      setUserRole(roleMap[data.user.role] || "user");

      // Refetch profile to get latest user data
      await refetchProfile();

      // Navigate to appropriate dashboard based on role
      if (data.user.role === "user") {
        navigate("/user-home");
      } else {
        navigate("/");
      }
    } catch (error) {
      setErrorMessage("Failed to connect to backend. Make sure the backend is running.");
      setShowErrorMessage(true);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Success Message Toast */}
      {showSuccessMessage && (
        <div className="fixed top-6 right-6 z-50 animate-in slide-in-from-top-2 duration-300">
          <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 shadow-lg">
            <CheckCircle className="h-5 w-5 text-green-600" />
            <p className="text-sm font-medium text-green-900">
              Signed out successfully
            </p>
          </div>
        </div>
      )}

      {/* Error Message Toast */}
      {showErrorMessage && (
        <div className="fixed top-6 right-6 z-50 animate-in slide-in-from-top-2 duration-300">
          <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 shadow-lg">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <p className="text-sm font-medium text-red-900">
              {errorMessage}
            </p>
          </div>
        </div>
      )}

      {/* Left Side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-[#ed0923] via-[#b8071c] to-[#8b0515]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_120%,rgba(255,255,255,0.1),transparent)]" />
        
        <div className="relative flex flex-col justify-center items-start p-16 text-white z-10 w-full">
          <div className="max-w-lg">
            <div className="flex items-center gap-4 mb-8">
              <div className="w-20 h-20 rounded-2xl bg-white flex items-center justify-center shadow-2xl">
                <span className="text-[#ed0923] font-bold text-4xl">T</span>
              </div>
              <div>
                <h1 className="text-3xl font-bold">Toyota</h1>
                <p className="text-lg font-medium text-red-100">Control Center</p>
              </div>
            </div>

            <p className="text-2xl font-semibold mb-12 leading-tight">
              Unified job and AI agent<br />management platform
            </p>

            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-white/10 backdrop-blur-sm flex items-center justify-center">
                  <Shield className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-semibold mb-1">Enterprise Security</h3>
                  <p className="text-sm text-red-100 leading-relaxed">
                    Advanced risk management and comprehensive audit trails
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-white/10 backdrop-blur-sm flex items-center justify-center">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-semibold mb-1">Real-time Monitoring</h3>
                  <p className="text-sm text-red-100 leading-relaxed">
                    Track job execution and agent performance in real-time
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-white/10 backdrop-blur-sm flex items-center justify-center">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-semibold mb-1">Compliance Ready</h3>
                  <p className="text-sm text-red-100 leading-relaxed">
                    SOC 2 certified with policy enforcement built-in
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-16 pt-8 border-t border-white/20">
              <p className="text-sm text-red-100">
                © 2026{" "}
                <a 
                  href="https://www.toyotafinancial.com" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="font-medium text-white hover:underline"
                >
                  Toyota Financial Services
                </a>
                . All rights reserved.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Right Side - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-gray-50">
        <div className="w-full max-w-md">
          <div>
            <div className="mb-8">
              <h2 className="text-3xl font-bold text-gray-900 mb-2">
                Welcome back
              </h2>
              <p className="text-gray-600">
                Sign in to your Control Center account
              </p>
            </div>

            <form onSubmit={handleLogin} className="space-y-6">
              <div>
                <label 
                  htmlFor="email" 
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={isLoading}
                  className="w-full px-4 py-3 rounded-lg border border-gray-300 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#ed0923] focus:border-transparent transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  placeholder="analyst@toyota.dev"
                />
                <p className="mt-2 text-xs text-gray-500">
                  Demo users: analyst@toyota.dev, root@toyota.dev, collections.admin@toyota.dev
                </p>
              </div>

              <div className="flex items-center">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    disabled={isLoading}
                    className="w-4 h-4 rounded border-gray-300 text-[#ed0923] focus:ring-[#ed0923] cursor-pointer disabled:opacity-50"
                  />
                  <span className="text-sm text-gray-700">Remember me</span>
                </label>
              </div>

              <Button
                type="submit"
                disabled={isLoading}
                className="w-full bg-[#ed0923] hover:bg-[#b8071c] text-white font-medium py-3 rounded-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? "Signing in..." : "Sign in"}
                {!isLoading && <ArrowRight className="h-4 w-4" />}
              </Button>
            </form>

            <div className="mt-8 p-4 rounded-lg bg-blue-50 border border-blue-200">
              <p className="text-sm text-blue-900">
                <strong>Demo Mode:</strong> Use any seed user email to login. No password required.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
