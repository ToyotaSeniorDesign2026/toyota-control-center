import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router";
import { Eye, EyeOff, ArrowRight, Shield, CheckCircle } from "lucide-react";
import { Button } from "../components/ui/button";
import { ImageWithFallback } from "../components/figma/ImageWithFallback";
import { useUser } from "../contexts/UserContext";
import logoImg from "figma:asset/78cbd1f20e12e98c3e07fe4c9b0e4faacfef3d82.png";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUserRole } = useUser();
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showMFA, setShowMFA] = useState(false);
  const [mfaCode, setMfaCode] = useState(["", "", "", "", "", ""]);
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [userRole, setLocalUserRole] = useState<"admin" | "user">("admin");

  // Check if user was just signed out
  useEffect(() => {
    if (location.state?.signedOut) {
      setShowSuccessMessage(true);
      // Clear the state
      window.history.replaceState({}, document.title);
      // Hide message after 3 seconds
      setTimeout(() => setShowSuccessMessage(false), 3000);
    }
  }, [location]);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    // Simulate API call
    setTimeout(() => {
      setIsLoading(false);
      setShowMFA(true);
    }, 800);
  };

  const handleMFASubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    // Simulate MFA verification
    setTimeout(() => {
      setIsLoading(false);
      // Set the user role in context
      setUserRole(userRole);
      // Navigate to appropriate dashboard based on role
      if (userRole === "user") {
        navigate("/user-home");
      } else {
        navigate("/");
      }
    }, 800);
  };

  const handleMFACodeChange = (index: number, value: string) => {
    if (value.length > 1) return;
    
    const newCode = [...mfaCode];
    newCode[index] = value;
    setMfaCode(newCode);

    // Auto-focus next input
    if (value && index < 5) {
      const nextInput = document.getElementById(`mfa-${index + 1}`);
      nextInput?.focus();
    }
  };

  const handleMFAKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !mfaCode[index] && index > 0) {
      const prevInput = document.getElementById(`mfa-${index - 1}`);
      prevInput?.focus();
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

      {/* Left Side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        {/* Gradient Background */}
        <div className="absolute inset-0 bg-gradient-to-br from-[#ed0923] via-[#b8071c] to-[#8b0515]" />
        
        {/* Overlay Pattern */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_120%,rgba(255,255,255,0.1),transparent)]" />
        
        {/* Content */}
        <div className="relative flex flex-col justify-center items-start p-16 text-white z-10 w-full">
          <div className="max-w-lg">
            {/* Logo and Title */}
            <div className="flex items-center gap-4 mb-8">
              <div className="w-20 h-20 rounded-2xl bg-white flex items-center justify-center shadow-2xl">
                <span className="text-[#ed0923] font-bold text-4xl">T</span>
              </div>
              <div>
                <h1 className="text-3xl font-bold">Toyota</h1>
                <p className="text-lg font-medium text-red-100">Control Center</p>
              </div>
            </div>

            {/* Tagline */}
            <p className="text-2xl font-semibold mb-12 leading-tight">
              Unified job and AI agent<br />management platform
            </p>

            {/* Features */}
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

            {/* Footer */}
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
          {!showMFA ? (
            // Login Form
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
                {/* Role Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Sign in as
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setLocalUserRole("admin")}
                      className={`px-4 py-3 rounded-lg border-2 font-medium transition-all ${
                        userRole === "admin"
                          ? "border-[#ed0923] bg-red-50 text-[#ed0923]"
                          : "border-gray-300 bg-white text-gray-700 hover:border-gray-400"
                      }`}
                    >
                      Admin
                    </button>
                    <button
                      type="button"
                      onClick={() => setLocalUserRole("user")}
                      className={`px-4 py-3 rounded-lg border-2 font-medium transition-all ${
                        userRole === "user"
                          ? "border-[#ed0923] bg-red-50 text-[#ed0923]"
                          : "border-gray-300 bg-white text-gray-700 hover:border-gray-400"
                      }`}
                    >
                      User
                    </button>
                  </div>
                </div>

                {/* Email */}
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
                    className="w-full px-4 py-3 rounded-lg border border-gray-300 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#ed0923] focus:border-transparent transition-all"
                    placeholder="you@company.com"
                  />
                </div>

                {/* Password */}
                <div>
                  <label 
                    htmlFor="password" 
                    className="block text-sm font-medium text-gray-700 mb-2"
                  >
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      className="w-full px-4 py-3 rounded-lg border border-gray-300 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#ed0923] focus:border-transparent transition-all"
                      placeholder="Enter your password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      {showPassword ? (
                        <EyeOff className="h-5 w-5" />
                      ) : (
                        <Eye className="h-5 w-5" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Remember Me & Forgot Password */}
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-300 text-[#ed0923] focus:ring-[#ed0923] cursor-pointer"
                    />
                    <span className="text-sm text-gray-700">Remember me</span>
                  </label>
                  <a 
                    href="#" 
                    className="text-sm font-medium text-[#ed0923] hover:text-[#b8071c] transition-colors"
                  >
                    Forgot password?
                  </a>
                </div>

                {/* Sign In Button */}
                <Button
                  type="submit"
                  className="w-full bg-[#ed0923] hover:bg-[#b8071c] text-white py-3 rounded-lg font-medium transition-colors flex items-center justify-center gap-2 group"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    "Signing in..."
                  ) : (
                    <>
                      Sign in
                      <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                    </>
                  )}
                </Button>
              </form>

              {/* Links */}
              <div className="mt-8 pt-6 border-t border-gray-200">
                <div className="flex items-center justify-center gap-6 text-sm">
                  <a 
                    href="#" 
                    className="text-gray-600 hover:text-gray-900 transition-colors"
                  >
                    Documentation
                  </a>
                  <span className="text-gray-300">•</span>
                  <a 
                    href="#" 
                    className="text-gray-600 hover:text-gray-900 transition-colors"
                  >
                    Support
                  </a>
                </div>
              </div>

              {/* Mobile Footer */}
              <div className="lg:hidden mt-8 pt-6 border-t border-gray-200 text-center">
                <p className="text-sm text-gray-600">
                  © 2026{" "}
                  <a 
                    href="https://www.toyotafinancial.com" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="font-medium text-gray-900 hover:underline"
                  >
                    Toyota Financial Services
                  </a>
                </p>
              </div>
            </div>
          ) : (
            // MFA Verification
            <div>
              <div className="mb-8">
                <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mb-4">
                  <Shield className="h-6 w-6 text-[#ed0923]" />
                </div>
                <h2 className="text-3xl font-bold text-gray-900 mb-2">
                  Two-factor authentication
                </h2>
                <p className="text-gray-600">
                  Enter the 6-digit code from your authenticator app
                </p>
              </div>

              <form onSubmit={handleMFASubmit} className="space-y-6">
                {/* MFA Code Input */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-4">
                    Authentication code
                  </label>
                  <div className="flex gap-2 justify-between">
                    {mfaCode.map((digit, index) => (
                      <input
                        key={index}
                        id={`mfa-${index}`}
                        type="text"
                        inputMode="numeric"
                        maxLength={1}
                        value={digit}
                        onChange={(e) => handleMFACodeChange(index, e.target.value)}
                        onKeyDown={(e) => handleMFAKeyDown(index, e)}
                        className="w-full aspect-square text-center text-2xl font-semibold rounded-lg border border-gray-300 bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#ed0923] focus:border-transparent transition-all"
                      />
                    ))}
                  </div>
                </div>

                {/* Verify Button */}
                <Button
                  type="submit"
                  className="w-full bg-[#ed0923] hover:bg-[#b8071c] text-white py-3 rounded-lg font-medium transition-colors"
                  disabled={isLoading || mfaCode.some(d => !d)}
                >
                  {isLoading ? "Verifying..." : "Verify and sign in"}
                </Button>

                {/* Back Link */}
                <button
                  type="button"
                  onClick={() => setShowMFA(false)}
                  className="w-full text-sm text-gray-600 hover:text-gray-900 transition-colors"
                >
                  ← Back to sign in
                </button>
              </form>

              {/* Help Text */}
              <div className="mt-6 p-4 rounded-lg bg-gray-100 border border-gray-200">
                <p className="text-sm text-gray-700">
                  Can't access your authenticator app?{" "}
                  <a href="#" className="font-medium text-[#ed0923] hover:text-[#b8071c]">
                    Use recovery code
                  </a>
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}