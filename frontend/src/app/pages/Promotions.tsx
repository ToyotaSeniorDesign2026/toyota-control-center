import { useMemo, useState } from "react";
import { ArrowUpCircle, CheckCircle2, ChevronDown, Clock } from "lucide-react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { Button } from "../components/ui/button";
import { getPendingPromotionResources, withdrawPendingSubmission } from "../lib/userDashboardStore";
import {
  formatPromotionDate,
  getPromotionTypeColor,
  mockPendingPromotions,
  mockReadyForPromotion,
  mockRecentlyPromoted,
} from "./promotionsData";

export default function Promotions() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedJobs, setSelectedJobs] = useState<string[]>([]);
  const pendingPromotions = useMemo(
    () => [...getPendingPromotionResources(), ...mockPendingPromotions],
    []
  );
  const [openSections, setOpenSections] = useState({
    ready: false,
    pending: false,
    recent: false,
  });

  const handleToggleSelection = (jobId: string) => {
    setSelectedJobs((prev) =>
      prev.includes(jobId)
        ? prev.filter((id) => id !== jobId)
        : [...prev, jobId]
    );
  };

  const handleRequestPromotion = () => {
    console.log("Requesting promotion for:", selectedJobs);
    setSelectedJobs([]);
  };

  const handleWithdraw = (jobId: string) => {
    withdrawPendingSubmission(jobId);
    window.location.reload();
  };

  const toggleSection = (section: "ready" | "pending" | "recent") => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="Promotions & Edits"
        activeSubPage="Promotions"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Promotions</h1>
            <p className="mt-1 text-sm text-gray-600">
              Promote approved jobs and track promotion requests through environments.
            </p>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <button
              type="button"
              onClick={() => toggleSection("ready")}
              className={`w-full bg-gray-50 px-6 py-4 text-left ${openSections.ready ? "border-b border-gray-200" : ""}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <ArrowUpCircle className="h-5 w-5 text-blue-600" />
                    <h3 className="font-semibold text-gray-900">Ready for Promotion</h3>
                  </div>
                  <p className="mt-1 text-xs text-gray-600">Select jobs to promote to production</p>
                </div>
                <ChevronDown
                  className={`h-4 w-4 text-gray-500 transition-transform ${openSections.ready ? "rotate-180" : ""}`}
                />
              </div>
            </button>
            {openSections.ready && (
              <div className="divide-y divide-gray-200">
                {selectedJobs.length > 0 && (
                  <div className="flex justify-end px-6 py-3">
                    <Button
                      onClick={handleRequestPromotion}
                      className="gap-2 bg-[#ed0923] text-white hover:bg-[#d10820]"
                    >
                      <ArrowUpCircle className="h-4 w-4" />
                      Request Promotion ({selectedJobs.length})
                    </Button>
                  </div>
                )}
                {mockReadyForPromotion.map((job) => (
                  <div key={job.id} className="p-6 transition-colors hover:bg-gray-50">
                    <div className="flex items-start gap-4">
                      <input
                        type="checkbox"
                        checked={selectedJobs.includes(job.id)}
                        onChange={() => handleToggleSelection(job.id)}
                        className="mt-1 h-4 w-4 rounded border-gray-300 text-[#ed0923] focus:ring-[#ed0923]"
                      />
                      <div className="flex-1">
                        <div className="mb-2 flex items-start justify-between">
                          <div>
                            <div className="font-semibold text-gray-900">{job.name}</div>
                            <div className={`mt-1 text-xs font-medium ${getPromotionTypeColor(job.type)}`}>
                              {job.type}
                            </div>
                          </div>
                          <span className="rounded bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700">
                            {job.currentEnvironment}
                          </span>
                        </div>
                        <p className="mb-2 text-sm text-gray-600">{job.description}</p>
                        <div className="text-xs text-gray-500">Created: {formatPromotionDate(job.createdAt)}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <button
              type="button"
              onClick={() => toggleSection("pending")}
              className={`w-full bg-gray-50 px-4 py-3 text-left ${openSections.pending ? "border-b border-gray-200" : ""}`}
            >
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-yellow-600" />
                <h3 className="font-semibold text-gray-900">Pending Promotions</h3>
                <ChevronDown
                  className={`ml-auto h-4 w-4 text-gray-500 transition-transform ${openSections.pending ? "rotate-180" : ""}`}
                />
              </div>
              <p className="mt-1 text-xs text-gray-600">{pendingPromotions.length} awaiting approval</p>
            </button>
            {openSections.pending && (
              <div className="divide-y divide-gray-200">
                {pendingPromotions.map((job) => (
                  <div key={job.id} className="p-4">
                    <div className="mb-2">
                      <div className="mb-1 text-sm font-medium text-gray-900">{job.name}</div>
                      <div className={`text-xs font-medium ${getPromotionTypeColor(job.type)}`}>{job.type}</div>
                    </div>
                    <div className="mb-2 flex items-center gap-2">
                      <span className="rounded bg-blue-100 px-2 py-1 text-xs font-medium text-blue-700">
                        {job.currentEnvironment}
                      </span>
                      <span className="text-xs text-gray-400">→</span>
                      <span className="rounded bg-green-100 px-2 py-1 text-xs font-medium text-green-700">
                        {job.targetEnvironment}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500">
                      Requested: {formatPromotionDate(job.lastModified || job.createdAt)}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleWithdraw(job.id)}
                      className="mt-3 rounded border border-red-300 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50"
                    >
                      Withdraw Submission
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <button
              type="button"
              onClick={() => toggleSection("recent")}
              className={`w-full bg-gray-50 px-4 py-3 text-left ${openSections.recent ? "border-b border-gray-200" : ""}`}
            >
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <h3 className="font-semibold text-gray-900">Recently Promoted</h3>
                <ChevronDown
                  className={`ml-auto h-4 w-4 text-gray-500 transition-transform ${openSections.recent ? "rotate-180" : ""}`}
                />
              </div>
              <p className="mt-1 text-xs text-gray-600">Successfully promoted to production</p>
            </button>
            {openSections.recent && (
              <div className="divide-y divide-gray-200">
                {mockRecentlyPromoted.map((job) => (
                  <div key={job.id} className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="mb-1 text-sm font-medium text-gray-900">{job.name}</div>
                        <div className={`text-xs font-medium ${getPromotionTypeColor(job.type)}`}>{job.type}</div>
                        <p className="mt-2 text-xs text-gray-600">{job.description}</p>
                      </div>
                      <span className="rounded bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
                        {job.currentEnvironment}
                      </span>
                    </div>
                    <div className="mt-2 text-xs text-gray-500">
                      Promoted: {formatPromotionDate(job.lastModified || job.createdAt)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>

      <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
    </div>
  );
}
