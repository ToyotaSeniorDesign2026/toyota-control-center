import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  PlayCircle,
  Send,
  Sparkles,
} from "lucide-react";
import { useNavigate } from "react-router";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { ManualJobCreationModal } from "../components/ManualResourceCreationModal";
import {
  pendingRequiredActionsCount,
  requiredActionItems,
  requiredActionStateBadge,
} from "./requiredActionsData";

const starterPrompts = [
  "Create a weekly dealer performance SQL report for Texas",
  "Build a monthly executive PowerPoint for finance leaders",
  "Set up a daily Excel job for warranty claim trends",
];

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
];

type PreviewTemplateForm = {
  formName: string;
  jobType: "SQL" | "Excel" | "PowerPoint" | "AI Agent";
  schedule: string;
  owner: string;
  destination: string;
  description: string;
};

function buildTemplateDraft(prompt: string): PreviewTemplateForm {
  const lower = prompt.toLowerCase();
  const jobType: PreviewTemplateForm["jobType"] = lower.includes("powerpoint")
    ? "PowerPoint"
    : lower.includes("excel")
      ? "Excel"
      : lower.includes("agent")
        ? "AI Agent"
        : "SQL";
  const schedule = lower.includes("daily")
    ? "Daily - 08:00"
    : lower.includes("weekly")
      ? "Weekly - Monday 08:00"
      : "Monthly - Day 1 09:00";
  const formName = prompt
    ? `form_${prompt.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 36)}`
    : "form_new_job";

  return {
    formName,
    jobType,
    schedule,
    owner: lower.includes("finance") ? "finance.ops@toyota.com" : "analyst@toyota.com",
    destination: "Email + Dashboard",
    description: prompt || "AI-generated form draft.",
  };
}

export default function UserHome() {
  const navigate = useNavigate();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
  const [previewForm, setPreviewForm] = useState<PreviewTemplateForm>(buildTemplateDraft(""));
  const requiredActionPreview = requiredActionItems.slice(0, 3);
  const pendingCount = pendingRequiredActionsCount();

  const createPreview = () => {
    const value = prompt.trim();
    if (!value) return;
    setPreviewForm(buildTemplateDraft(value));
    setIsPreviewModalOpen(true);
    setPrompt("");
  };

  const handleSaveTemplate = () => {
    console.log("Save form:", previewForm);
    setIsPreviewModalOpen(false);
  };

  const handleCreateTemplate = () => {
    console.log("Create form:", previewForm);
    setIsPreviewModalOpen(false);
    navigate("/forms");
  };

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
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                className="border-gray-300"
                onClick={() => navigate("/forms")}
              >
                Open Forms
              </Button>
              <Button
                className="bg-[#ed0923] text-white hover:bg-[#d10820]"
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
                <div className="border-b border-gray-200 bg-gradient-to-r from-[#ed0923]/10 to-transparent p-5">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-[#ed0923]" />
                    <h2 className="text-lg font-semibold text-gray-900">AI Build Assistant</h2>
                  </div>
                </div>
                <div className="space-y-3 p-5">
                  <Textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Describe the job you want AI to plan..."
                    rows={4}
                    className="border-gray-200"
                  />
                  <div className="grid grid-cols-1 gap-2">
                    {starterPrompts.map((item) => (
                      <button
                        key={item}
                        onClick={() => setPrompt(item)}
                        className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-left text-xs text-gray-700 hover:border-[#ed0923] hover:bg-red-50"
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  <Button
                    onClick={createPreview}
                    className="w-full bg-[#ed0923] text-white hover:bg-[#d10820]"
                  >
                    <Send className="mr-2 h-4 w-4" />
                    Generate Preview
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full border-gray-300"
                    onClick={() => setIsManualModalOpen(true)}
                  >
                    Manually Create Job
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
                Open Run History
              </Button>
            </div>
          </div>
        </div>
      </main>

      <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
      <ManualJobCreationModal
        isOpen={isManualModalOpen}
        onClose={() => setIsManualModalOpen(false)}
      />

      {isPreviewModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-2xl rounded-xl border border-gray-200 bg-white shadow-xl">
            <div className="border-b border-gray-200 bg-gray-50 p-5">
              <h2 className="text-xl font-semibold text-gray-900">AI Job Preview Form</h2>
              <p className="mt-1 text-sm text-gray-600">
                Review and edit this generated form before saving or creating.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-4 p-5 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">Form Name</label>
                <input
                  value={previewForm.formName}
                  onChange={(e) => setPreviewForm((prev) => ({ ...prev, formName: e.target.value }))}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">Job Type</label>
                <select
                  value={previewForm.jobType}
                  onChange={(e) =>
                    setPreviewForm((prev) => ({ ...prev, jobType: e.target.value as PreviewTemplateForm["jobType"] }))
                  }
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                >
                  <option value="SQL">SQL</option>
                  <option value="Excel">Excel</option>
                  <option value="PowerPoint">PowerPoint</option>
                  <option value="AI Agent">AI Agent</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">Schedule</label>
                <input
                  value={previewForm.schedule}
                  onChange={(e) => setPreviewForm((prev) => ({ ...prev, schedule: e.target.value }))}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">Owner</label>
                <input
                  value={previewForm.owner}
                  onChange={(e) => setPreviewForm((prev) => ({ ...prev, owner: e.target.value }))}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                />
              </div>
              <div className="md:col-span-2">
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">Destination</label>
                <input
                  value={previewForm.destination}
                  onChange={(e) => setPreviewForm((prev) => ({ ...prev, destination: e.target.value }))}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                />
              </div>
              <div className="md:col-span-2">
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">Description</label>
                <Textarea
                  value={previewForm.description}
                  onChange={(e) => setPreviewForm((prev) => ({ ...prev, description: e.target.value }))}
                  rows={4}
                  className="border-gray-200"
                />
              </div>
            </div>

            <div className="flex flex-wrap justify-end gap-2 border-t border-gray-200 bg-gray-50 p-4">
              <Button
                variant="outline"
                className="border-gray-300"
                onClick={() => setIsPreviewModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                variant="outline"
                className="border-[#ed0923] text-[#ed0923] hover:bg-red-50"
                onClick={handleSaveTemplate}
              >
                Save Form
              </Button>
              <Button
                className="bg-[#ed0923] text-white hover:bg-[#d10820]"
                onClick={handleCreateTemplate}
              >
                Create Form
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
