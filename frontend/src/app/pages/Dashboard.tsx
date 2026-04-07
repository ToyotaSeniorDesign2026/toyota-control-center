import { MetricsBar } from "../components/MetricsBar";
import { JobsTable } from "../components/JobsTable";
import { ActivityFeed } from "../components/ActivityFeed";
import { ScheduledJobs } from "../components/ScheduledJobs";

export default function Dashboard() {
  return (
    <>
      {/* Metrics Bar */}
      <div className="mb-8">
        <MetricsBar />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Column - 70% */}
        <div className="space-y-6 lg:col-span-2">
          {/* Jobs Table */}
          <JobsTable />
          
          {/* Scheduled Jobs */}
          <ScheduledJobs />
        </div>

        {/* Right Column - 30% */}
        <div className="space-y-6 lg:col-span-1">
          {/* Activity Feed */}
          <ActivityFeed />
        </div>
      </div>
    </>
  );
}