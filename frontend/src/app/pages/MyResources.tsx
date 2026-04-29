import { useMemo, useState } from "react";
import { CheckCircle } from "lucide-react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { JobDetailModal } from "../components/JobDetailModal";
import {
  formatJobDate,
  getJobTypeColor,
  getJobStatusColor,
} from "./jobsData";
import { useJobRuns } from "../contexts/JobRunContext";
import { buildUserJobs, type UserJobViewModel } from "../lib/jobRunViewModels";

export default function MyJobs() {
  const { resources, runs, loading, error } = useJobRuns();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<UserJobViewModel | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const jobs = useMemo(() => buildUserJobs(resources, runs), [resources, runs]);

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
        activeSubPage="My Jobs"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">My Jobs</h1>
            <p className="mt-1 text-sm text-gray-600">
              View all jobs you created and inspect details for each item.
            </p>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 bg-gray-50 px-5 py-4">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-green-600" />
                <h3 className="font-semibold text-gray-900">My Jobs</h3>
              </div>
              <p className="mt-1 text-xs text-gray-600">{jobs.length} total jobs</p>
            </div>
            <div className="divide-y divide-gray-200">
              {loading && jobs.length === 0 ? (
                <div className="p-6 text-sm text-gray-600">Loading live jobs...</div>
              ) : error ? (
                <div className="p-6 text-sm text-red-700">Unable to load live jobs: {error}</div>
              ) : jobs.length === 0 ? (
                <div className="p-6 text-sm text-gray-600">No jobs in the database right now.</div>
              ) : (
                jobs.map((job) => (
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
                      <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${getJobStatusColor(job.status)}`}>
                        {job.status}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">{formatJobDate(job.createdAt)}</span>
                      {job.environment && (
                        <span className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">
                          {job.environment}
                        </span>
                      )}
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
