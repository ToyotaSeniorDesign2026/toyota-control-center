import { useMemo, useState } from "react";
import { PlayCircle } from "lucide-react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { JobDetailModal } from "../components/JobDetailModal";
import { formatJobDate, getJobTypeColor } from "./jobsData";
import { useJobRuns } from "../contexts/JobRunContext";
import { buildRunningJobs, type UserJobViewModel } from "../lib/jobRunViewModels";

export default function RunningJobs() {
  const { jobs: jobRecords, runs, loading, error } = useJobRuns();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<UserJobViewModel | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const runningJobs = useMemo(() => buildRunningJobs(jobRecords, runs), [jobRecords, runs]);

  const handleJobClick = (job: UserJobViewModel) => {
    setSelectedJob(job);
    setIsDetailModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsDetailModalOpen(false);
    setTimeout(() => setSelectedJob(null), 300);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="Jobs"
        activeSubPage="Running Jobs"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Running Jobs</h1>
            <p className="mt-1 text-sm text-gray-600">
              Jobs actively running right now across environments.
            </p>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 bg-gray-50 px-5 py-4">
              <div className="flex items-center gap-2">
                <PlayCircle className="h-5 w-5 text-blue-600" />
                <h3 className="font-semibold text-gray-900">Running Jobs</h3>
              </div>
              <p className="mt-1 text-xs text-gray-600">{runningJobs.length} currently active</p>
            </div>
            <div className="divide-y divide-gray-200">
              {loading && runningJobs.length === 0 ? (
                <div className="p-6 text-sm text-gray-600">Loading live runs...</div>
              ) : error ? (
                <div className="p-6 text-sm text-red-700">Unable to load live runs: {error}</div>
              ) : runningJobs.length === 0 ? (
                <div className="p-6 text-sm text-gray-600">No active runs in the database right now.</div>
              ) : (
                runningJobs.map((job) => (
                  <div
                    key={job.id}
                    className="cursor-pointer p-4 transition-colors hover:bg-gray-50"
                    onClick={() => handleJobClick(job)}
                  >
                    <div className="mb-2 flex items-start justify-between">
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900">{job.name}</div>
                        <div className={`mt-1 text-xs font-medium ${getJobTypeColor(job.type)}`}>
                          {job.type}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">{formatJobDate(job.createdAt)}</span>
                      <div className="flex items-center gap-2">
                        {job.environment && (
                          <span className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">
                            {job.environment}
                          </span>
                        )}
                        <div className="flex items-center gap-1">
                          <div className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
                          <span className="text-xs font-medium text-blue-700">Running</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </main>

      <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
      <JobDetailModal
        job={selectedJob}
        isOpen={isDetailModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  );
}
