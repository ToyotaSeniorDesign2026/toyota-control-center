import { useState } from "react";
import { useNavigate } from "react-router";
import { Button } from "../components/ui/button";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { getLatestDraftForm, getSavedTemplates } from "../lib/userDashboardStore";

function buildEmail(prompt: string): string {
  if (prompt.toLowerCase().includes("finance")) return "finance.team@toyota.com";
  if (prompt.toLowerCase().includes("sales")) return "sales.ops@toyota.com";
  if (prompt.toLowerCase().includes("exec")) return "executive.team@toyota.com";
  return "analyst@toyota.com";
}

function buildName(prefix: string, prompt: string): string {
  const words = prompt
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 4)
    .join("_");
  return words ? `${prefix}_${words}` : `${prefix}_automation`;
}

function buildEmail(prompt: string): string {
  if (prompt.toLowerCase().includes("finance")) return "finance.team@toyota.com";
  if (prompt.toLowerCase().includes("sales")) return "sales.ops@toyota.com";
  if (prompt.toLowerCase().includes("exec")) return "executive.team@toyota.com";
  return "analyst@toyota.com";
}

function buildName(prefix: string, prompt: string): string {
  const words = prompt
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 4)
    .join("_");
  return words ? `${prefix}_${words}` : `${prefix}_automation`;
}

export default function Forms() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");
  const [isAutofillChooserOpen, setIsAutofillChooserOpen] = useState(false);
  const navigate = useNavigate();
  const draftForm = getLatestDraftForm();

  const openExcelWithAI = () => {
    const draft = {
      jobName: buildName("excel_report", aiPrompt),
      description: aiPrompt || "AI-generated Excel report workflow.",
      owner: buildEmail(aiPrompt),
      scheduleType: "monthly",
      scheduleDay: "1",
      scheduleTime: "09:00",
      outputFormat: "xlsx",
      emailRecipients: buildEmail(aiPrompt),
      includeCharts: true,
      dataSensitivity: "internal",
    };
    navigate("/excel-report", { state: { aiPrompt, aiDraft: draft } });
  };

  const openSQLWithAI = () => {
    const lower = aiPrompt.toLowerCase();
    const draft = {
      jobName: buildName("sql_report", aiPrompt),
      description: aiPrompt || "AI-generated SQL report workflow.",
      owner: buildEmail(aiPrompt),
      reportTemplate: lower.includes("customer")
        ? "customer_metrics"
        : lower.includes("dealer")
          ? "dealer_performance"
          : lower.includes("finance") || lower.includes("revenue")
            ? "revenue_breakdown"
            : "daily_sales",
      dateRange: "30",
      regionFilter: "all",
      departmentFilter: lower.includes("finance") ? "finance" : "all",
      minAmount: lower.includes("high value") ? "10000" : "1000",
      outputDestination: "email",
      emailRecipients: buildEmail(aiPrompt),
      dataSensitivity: "internal",
    };
    navigate("/sql-job", { state: { aiPrompt, aiDraft: draft } });
  };

  const openPowerPointWithAI = () => {
    const lower = aiPrompt.toLowerCase();
    const draft = {
      jobName: buildName("ppt_report", aiPrompt),
      description: aiPrompt || "AI-generated PowerPoint reporting workflow.",
      owner: buildEmail(aiPrompt),
      presentationType: lower.includes("board")
        ? "quarterly_board"
        : lower.includes("exec")
          ? "executive_dashboard"
          : lower.includes("customer")
            ? "customer_insights"
            : "monthly_review",
      dataSource: lower.includes("finance") ? "financial_database" : "sales_database",
      includeTables: true,
      includeCharts: true,
      includeImages: lower.includes("image") || lower.includes("logo"),
      outputFormat: "pptx",
      emailRecipients: buildEmail(aiPrompt),
      dataSensitivity: "internal",
    };
    navigate("/powerpoint", { state: { aiPrompt, aiDraft: draft } });
  };

  const savedTemplateOptions = getSavedTemplates().map((template) => ({
    label: `Saved Template: ${template.name}`,
    route: template.route,
    draft: template.draft,
  }));

  const openSavedTemplate = (route: string, draft: Record<string, unknown>) => {
    navigate(route, { state: { aiPrompt, aiDraft: draft } });
    setIsAutofillChooserOpen(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="Forms"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Forms</h1>
            <p className="mt-1 text-sm text-gray-600">
              Choose a guided form to create scheduled jobs quickly.
            </p>
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50 shadow-sm">
            <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  Continue editing {draftForm?.jobName ?? "your latest"} form
                </h2>
                <p className="mt-1 text-sm text-gray-600">
                  {draftForm
                    ? `This form is saved at ${draftForm.progress} completion and ready to finish.`
                    : "Your newest in-progress form will appear here once you save a draft."}
                </p>
              </div>
              <Button
                onClick={() =>
                  draftForm &&
                  navigate(draftForm.route, {
                    state: {
                      aiPrompt: "Resume saved draft form",
                      aiDraft: draftForm.draft,
                    },
                  })
                }
                disabled={!draftForm}
                className="gap-2 bg-[#ed0923] text-white hover:bg-[#d10820] disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                Continue Editing
              </Button>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 bg-gray-50 p-6">
              <h2 className="text-xl font-semibold text-gray-900">AI Form Autofill</h2>
              <p className="mt-1 text-sm text-gray-600">
                Describe what you want, then open a form with AI-suggested defaults.
              </p>
            </div>
            <div className="space-y-4 p-6">
              <textarea
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                placeholder="Example: Build a monthly executive sales deck for finance leaders with charts."
                rows={4}
                className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
              />
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={() => setIsAutofillChooserOpen((prev) => !prev)}
                  className="bg-[#ed0923] text-white hover:bg-[#d10820]"
                >
                  Choose Form to Autofill
                </Button>
              </div>
              {isAutofillChooserOpen && (
                <div className="rounded-lg border border-gray-200 bg-white p-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Pre Built Forms</p>
                  <div className="mb-4 flex flex-wrap gap-2">
                    <Button variant="outline" className="border-gray-300" onClick={openExcelWithAI}>
                      Excel Report Job
                    </Button>
                    <Button variant="outline" className="border-gray-300" onClick={openSQLWithAI}>
                      SQL Job
                    </Button>
                    <Button variant="outline" className="border-gray-300" onClick={openPowerPointWithAI}>
                      PowerPoint Job
                    </Button>
                  </div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Saved Templates</p>
                  <div className="flex flex-col gap-2">
                    {savedTemplateOptions.map((option) => (
                      <button
                        key={option.label}
                        onClick={() => openSavedTemplate(option.route, option.draft)}
                        className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-left text-sm text-gray-700 hover:border-[#ed0923] hover:bg-red-50"
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
      <UserProfilePanel
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
      />
    </div>
  );
}
