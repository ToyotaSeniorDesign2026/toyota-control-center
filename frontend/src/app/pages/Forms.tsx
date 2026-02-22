import { useState } from "react";
import { useNavigate } from "react-router";
import { Database, FileSpreadsheet } from "lucide-react";
import { Button } from "../components/ui/button";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";

export default function Forms() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const navigate = useNavigate();

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

          <div className="rounded-lg border border-red-200 bg-red-50 shadow-sm">
            <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#ed0923]">
                  <FileSpreadsheet className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">Excel Report Job</h2>
                  <p className="mt-1 text-sm text-gray-600">
                    Use the guided form to create recurring Excel report jobs.
                  </p>
                </div>
              </div>
              <Button
                onClick={() => navigate("/excel-report")}
                className="gap-2 bg-[#ed0923] text-white hover:bg-[#d10820]"
              >
                Open Excel Form
              </Button>
            </div>
          </div>

          <div className="rounded-lg border border-red-200 bg-red-50 shadow-sm">
            <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#ed0923]">
                  <Database className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">SQL Job</h2>
                  <p className="mt-1 text-sm text-gray-600">
                    Use the guided form to schedule recurring SQL jobs.
                  </p>
                </div>
              </div>
              <Button
                onClick={() => navigate("/sql-job")}
                className="gap-2 bg-[#ed0923] text-white hover:bg-[#d10820]"
              >
                Open SQL Form
              </Button>
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
