import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  PlayCircle,
  Sparkles,
} from "lucide-react";
import { useNavigate } from "react-router";
import { Button } from "../components/ui/button";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import {
  pendingRequiredActionsCount,
  requiredActionItems,
  requiredActionStateBadge,
} from "./requiredActionsData";

const kpis = [
  { label: "My Active Jobs", value: 12, hint: "+2 this week", tone: "text-green-600" },
  { label: "Pending Approvals", value: 3, hint: "2 high priority", tone: "text-amber-600" },
  { label: "Failed Runs (24h)", value: 1, hint: "Investigate before noon", tone: "text-red-600" },
  { label: "Saved Jobs", value: 27, hint: "5 updated recently", tone: "text-[#ed0923]" },
];

const recentJobs = [
  { name: "Monthly Dealer KPI Deck", type: "PowerPoint", schedule: "Monthly, day 1", status: "Healthy" },
  { name: "Warranty Claims Rollup", type: "Excel", schedule: "Weekly, Mon 08:00", status: "Running" },
  { name: "Customer Churn Analysis", type: "SQL", schedule: "Daily, 06:00", status: "Needs Attention" },
  { name: "Quarterly Revenue Report", type: "PowerPoint", schedule: "Quarterly, day 1", status: "Healthy" },
];

export default function UserHome() {
  const navigate = useNavigate();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const requiredActionPreview = requiredActionItems.slice(0, 3);
  const pendingCount = pendingRequiredActionsCount();

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="Dashboard"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-8">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">User Control Dashboard</h1>
              <p className="mt-1 text-sm text-gray-600">
                Track jobs, submit forms, and use AI assistance to draft workflow requests.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                className="bg-[#ed0923] text-white hover:bg-[#d10820]"
                onClick={() => navigate("/create-job")}
              >
                <Sparkles className="mr-2 h-4 w-4" />
                Create Job with AI
              </Button>
              <Button
                className="bg-white border border-gray-200 text-gray-700 hover:bg-gray-50"
                onClick={() => navigate("/forms")}
              >
                Open Forms
              </Button>
              <Button
                className="bg-white border border-gray-200 text-gray-700 hover:bg-gray-50"
                onClick={() => navigate("/jobs/my-jobs")}
              >
                Go to My Jobs
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {kpis.map((kpi) => (
              <div key={kpi.label} className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{kpi.label}</p>
                <p className="mt-2 text-3xl font-bold text-gray-900">{kpi.value}</p>
                <p className={`mt-1 text-sm font-medium ${kpi.tone}`}>{kpi.hint}</p>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">System Snapshot</h3>
            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-green-600" /> DEV</span>
                <span className="text-green-700">Healthy</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
                <span className="flex items-center gap-2"><PlayCircle className="h-4 w-4 text-blue-600" /> UAT</span>
                <span className="text-blue-700">3 jobs running</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
                <span className="flex items-center gap-2"><Clock3 className="h-4 w-4 text-amber-600" /> PROD</span>
                <span className="text-amber-700">1 approval pending</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <div className="space-y-6 xl:col-span-2">
              <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
                <div className="border-b border-gray-200 p-5">
                  <h2 className="text-lg font-semibold text-gray-900">Recent Jobs</h2>
                  <p className="mt-1 text-sm text-gray-600">Current state of your most-used workflows.</p>
                </div>
                <div className="divide-y divide-gray-100">
                  {recentJobs.map((job) => (
                    <div key={job.name} className="grid grid-cols-1 gap-3 p-5 md:grid-cols-4 md:items-center">
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{job.name}</p>
                        <p className="text-xs text-gray-500">{job.type}</p>
                      </div>
                      <p className="text-sm text-gray-600">{job.schedule}</p>
                      <div>
                        <span
                          className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                            job.status === "Healthy"
                              ? "bg-green-100 text-green-700"
                              : job.status === "Running"
                                ? "bg-blue-100 text-blue-700"
                                : "bg-red-100 text-red-700"
                          }`}
                        >
                          {job.status}
                        </span>
                      </div>
                      <div className="md:text-right">
                        <Button
                          variant="ghost"
                          className="text-[#ed0923] hover:bg-red-50 hover:text-[#d10820]"
                          onClick={() => navigate("/jobs/my-jobs")}
                        >
                          View Details
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
                <div className="border-b border-gray-200 p-5">
                  <h2 className="text-lg font-semibold text-gray-900">Required Actions Preview</h2>
                  <p className="mt-1 text-sm text-gray-600">
                    {pendingCount} pending. Open the full queue for all action details.
                  </p>
                </div>
                <div className="divide-y divide-gray-100">
                  {requiredActionPreview.map((item) => (
                    <div key={item.id} className="flex items-start justify-between gap-3 p-4">
                      <div className="min-w-0">
                        <div className="mb-1 flex items-center gap-2">
                          <span className={`inline-flex rounded-full px-2 py-1 text-[11px] font-semibold ${requiredActionStateBadge(item.state)}`}>
                            {item.state}
                          </span>
                          <span className="text-xs text-gray-500">{item.runAfter}</span>
                        </div>
                        <p className="truncate text-sm font-medium text-gray-900">{item.subject}</p>
                      </div>
                      {item.state === "pending" && <AlertTriangle className="h-4 w-4 text-amber-500" />}
                    </div>
                  ))}
                </div>
                <div className="border-t border-gray-200 p-4">
                  <Button
                    onClick={() => navigate("/required-actions")}
                    className="bg-[#ed0923] text-white hover:bg-[#d10820]"
                  >
                    Go to Required Actions
                  </Button>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900">Next Best Steps</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button onClick={() => navigate("/forms")} className="bg-[#ed0923] text-white hover:bg-[#d10820]">
                Create New Job
              </Button>
              <Button variant="outline" className="border-gray-300" onClick={() => navigate("/promotions-edits/promotions")}>
                Review Promotions
              </Button>
              <Button variant="outline" className="border-gray-300" onClick={() => navigate("/calendar")}>
                Open Run Calendar
              </Button>
            </div>
          </div>
        </div>
      </main>

      <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
    </div>
  );
}
