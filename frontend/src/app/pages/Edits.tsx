import { useState } from "react";
import { Edit, XCircle } from "lucide-react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { Button } from "../components/ui/button";
import { RevisionModal } from "../components/RevisionModal";
import {
  formatPromotionDate,
  getPromotionTypeColor,
  mockRejectedPromotions,
  type PromotionJob,
} from "./promotionsData";

export default function Edits() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [revisionJob, setRevisionJob] = useState<PromotionJob | null>(null);
  const [isRevisionModalOpen, setIsRevisionModalOpen] = useState(false);

  const handleRevise = (job: PromotionJob) => {
    setRevisionJob(job);
    setIsRevisionModalOpen(true);
  };

  const handleCloseRevisionModal = () => {
    setIsRevisionModalOpen(false);
    setTimeout(() => setRevisionJob(null), 300);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="Promotions & Edits"
        activeSubPage="Edits"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Edits</h1>
            <p className="mt-1 text-sm text-gray-600">
              Review rejected promotion requests and submit revised jobs.
            </p>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
              <div className="flex items-center gap-2">
                <XCircle className="h-5 w-5 text-red-600" />
                <h3 className="font-semibold text-gray-900">Rejected Promotions</h3>
              </div>
              <p className="mt-1 text-xs text-gray-600">{mockRejectedPromotions.length} need revision</p>
            </div>
            <div className="divide-y divide-gray-200">
              {mockRejectedPromotions.map((job) => (
                <div key={job.id} className="p-4">
                  <div className="mb-2">
                    <div className="mb-1 text-sm font-medium text-gray-900">{job.name}</div>
                    <div className={`text-xs font-medium ${getPromotionTypeColor(job.type)}`}>{job.type}</div>
                  </div>
                  {job.rejectionReason && (
                    <div className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3">
                      <p className="text-xs text-red-800">
                        <span className="font-semibold">Reason: </span>
                        {job.rejectionReason}
                      </p>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <div className="text-xs text-gray-500">
                      Rejected: {formatPromotionDate(job.lastModified || job.createdAt)}
                    </div>
                    <Button
                      onClick={() => handleRevise(job)}
                      variant="outline"
                      size="sm"
                      className="gap-2 border-[#ed0923] text-[#ed0923] hover:bg-red-50"
                    >
                      <Edit className="h-3 w-3" />
                      Revise
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>

      <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
      <RevisionModal
        job={revisionJob}
        isOpen={isRevisionModalOpen}
        onClose={handleCloseRevisionModal}
      />
    </div>
  );
}
