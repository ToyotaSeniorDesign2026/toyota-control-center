import { useState } from "react";
import { useNavigate } from "react-router";
import { Clock3, Database, FileSpreadsheet, Presentation } from "lucide-react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { Button } from "../components/ui/button";

type SavedForm = {
  id: string;
  name: string;
  type: "Excel" | "SQL" | "PowerPoint";
  lastEdited: string;
  progress: string;
  route: string;
  draft: Record<string, unknown>;
};

const savedForms: SavedForm[] = [
  {
    id: "sf-001",
    name: "q2_dealer_scorecard",
    type: "SQL",
    lastEdited: "Mar 3, 2026 11:20 AM",
    progress: "60%",
    route: "/sql-job",
    draft: {
      jobName: "q2_dealer_scorecard",
      description: "Quarterly dealer scorecard and KPI ranking output.",
      owner: "dealer.analytics@toyota.com",
      reportTemplate: "dealer_performance",
      dateRange: "90",
      regionFilter: "all",
      departmentFilter: "all",
      minAmount: "5000",
      outputDestination: "email",
      emailRecipients: "dealer.analytics@toyota.com",
      dataSensitivity: "internal",
    },
  },
  {
    id: "sf-002",
    name: "monthly_exec_finance_deck",
    type: "PowerPoint",
    lastEdited: "Mar 2, 2026 04:05 PM",
    progress: "45%",
    route: "/powerpoint",
    draft: {
      jobName: "monthly_exec_finance_deck",
      description: "Executive finance summary with revenue and margin charts.",
      owner: "finance.ops@toyota.com",
      presentationType: "executive_dashboard",
      dataSource: "financial_database",
      includeTables: true,
      includeCharts: true,
      includeImages: false,
      outputFormat: "pptx",
      emailRecipients: "finance.ops@toyota.com",
      dataSensitivity: "internal",
    },
  },
  {
    id: "sf-003",
    name: "warranty_claims_monthly_export",
    type: "Excel",
    lastEdited: "Mar 1, 2026 09:42 AM",
    progress: "80%",
    route: "/excel-report",
    draft: {
      jobName: "warranty_claims_monthly_export",
      description: "Monthly warranty claims export with trend charts.",
      owner: "quality.ops@toyota.com",
      scheduleType: "monthly",
      scheduleDay: "1",
      scheduleTime: "09:00",
      outputFormat: "xlsx",
      emailRecipients: "quality.ops@toyota.com",
      includeCharts: true,
      dataSensitivity: "internal",
    },
  },
];

function typeIcon(type: SavedForm["type"]) {
  if (type === "Excel") return <FileSpreadsheet className="h-5 w-5 text-white" />;
  if (type === "SQL") return <Database className="h-5 w-5 text-white" />;
  return <Presentation className="h-5 w-5 text-white" />;
}

export default function MySavedForms() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="Forms"
        activeSubPage="Saved Templates"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Saved Templates</h1>
            <p className="mt-1 text-sm text-gray-600">
              AI-created forms saved as reusable templates for future jobs.
            </p>
          </div>

          <div className="space-y-4">
            {savedForms.map((form) => (
              <div key={form.id} className="rounded-lg border border-gray-200 bg-white shadow-sm">
                <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#ed0923]">
                      {typeIcon(form.type)}
                    </div>
                    <div>
                      <h2 className="text-xl font-semibold text-gray-900">{form.name}</h2>
                      <p className="mt-1 text-sm text-gray-600">{form.type} AI form template</p>
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-gray-500">
                        <span className="rounded bg-gray-100 px-2 py-1 font-medium text-gray-700">{form.progress} complete</span>
                        <span className="inline-flex items-center gap-1"><Clock3 className="h-3 w-3" /> Last edited {form.lastEdited}</span>
                      </div>
                    </div>
                  </div>
                  <Button
                    onClick={() =>
                      navigate(form.route, {
                        state: {
                          aiPrompt: "Resume saved form",
                          aiDraft: form.draft,
                        },
                      })
                    }
                    className="gap-2 bg-[#ed0923] text-white hover:bg-[#d10820]"
                  >
                    Continue Editing
                  </Button>
                </div>
              </div>
            ))}
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
