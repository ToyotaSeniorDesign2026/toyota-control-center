import { useState } from "react";
import { useNavigate } from "react-router";
import { Database, FileSpreadsheet, Presentation, Search } from "lucide-react";
import { Button } from "../components/ui/button";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";

type FormType = "Excel" | "SQL" | "PowerPoint";

type PreBuiltForm = {
  id: string;
  title: string;
  description: string;
  type: FormType;
  route: string;
};

const preBuiltForms: PreBuiltForm[] = [
  {
    id: "excel",
    title: "Excel Report Job",
    description: "Use the guided form to create recurring Excel report jobs.",
    type: "Excel",
    route: "/excel-report",
  },
  {
    id: "sql",
    title: "SQL Job",
    description: "Use the guided form to schedule recurring SQL jobs.",
    type: "SQL",
    route: "/sql-job",
  },
  {
    id: "powerpoint",
    title: "PowerPoint Job",
    description: "Use the guided form to generate scheduled presentations.",
    type: "PowerPoint",
    route: "/powerpoint",
  },
];

function formIcon(type: FormType) {
  if (type === "Excel") return <FileSpreadsheet className="h-5 w-5 text-white" />;
  if (type === "SQL") return <Database className="h-5 w-5 text-white" />;
  return <Presentation className="h-5 w-5 text-white" />;
}

export default function PreBuiltForms() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<"All" | FormType>("All");
  const navigate = useNavigate();
  const filteredForms = preBuiltForms.filter((form) => {
    const search = searchQuery.trim().toLowerCase();
    const matchesSearch =
      search.length === 0 ||
      form.title.toLowerCase().includes(search) ||
      form.description.toLowerCase().includes(search) ||
      form.type.toLowerCase().includes(search);
    const matchesType = typeFilter === "All" || form.type === typeFilter;
    return matchesSearch && matchesType;
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="Forms"
        activeSubPage="Pre Built Forms"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Pre Built Forms</h1>
            <p className="mt-1 text-sm text-gray-600">
              Open one of the standard forms for common job types.
            </p>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="relative w-full lg:max-w-md">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search forms by name or type..."
                  className="h-10 w-full rounded-lg border border-gray-200 bg-white pl-10 pr-4 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                {(["All", "SQL", "Excel", "PowerPoint"] as const).map((type) => (
                  <button
                    key={type}
                    onClick={() => setTypeFilter(type)}
                    className={`rounded-full px-3 py-1.5 text-xs font-semibold ${
                      typeFilter === type
                        ? "bg-[#ed0923] text-white"
                        : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {filteredForms.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center shadow-sm">
              <p className="text-sm font-medium text-gray-900">No forms match your search</p>
              <p className="mt-1 text-xs text-gray-600">Try a different keyword or clear the type filter.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredForms.map((form) => (
                <div key={form.id} className="rounded-lg border border-red-200 bg-red-50 shadow-sm">
                  <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#ed0923]">
                        {formIcon(form.type)}
                      </div>
                      <div>
                        <h2 className="text-xl font-semibold text-gray-900">{form.title}</h2>
                        <p className="mt-1 text-sm text-gray-600">{form.description}</p>
                      </div>
                    </div>
                    <Button
                      onClick={() => navigate(form.route)}
                      className="gap-2 bg-[#ed0923] text-white hover:bg-[#d10820]"
                    >
                      Open {form.type} Form
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
      <UserProfilePanel
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
      />
    </div>
  );
}
