import { useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { markRequiredActionResolved, requiredActionItems } from "./requiredActionsData";

type ActionTask = {
  id: string;
  state: string;
  subject: string;
  runAfter: string;
  mapIndex: number;
  respondedAt: string;
};

const fallbackTasks: Record<string, ActionTask> = Object.fromEntries(
  requiredActionItems.map((item) => [item.id, item])
) as Record<string, ActionTask>;

export default function RequiredActionForm() {
  const navigate = useNavigate();
  const location = useLocation();
  const { actionId } = useParams();
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const fromState = (location.state as { task?: ActionTask } | null)?.task;
  const task = useMemo(() => {
    if (fromState) return fromState;
    if (actionId && fallbackTasks[actionId]) return fallbackTasks[actionId];
    return null;
  }, [fromState, actionId]);

  const [decision, setDecision] = useState("provide-input");
  const [notes, setNotes] = useState("");
  const [submittedAt, setSubmittedAt] = useState<string | null>(null);

  if (!task) {
    return (
      <div className="min-h-screen bg-gray-50">
        <UserNavigation activePage="Required Actions" onProfileClick={() => setIsProfileOpen(true)} />
        <main className="mx-auto max-w-[900px] px-6 py-8">
          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <h1 className="text-2xl font-bold text-gray-900">Action Not Found</h1>
            <p className="mt-2 text-sm text-gray-600">The requested action task could not be loaded.</p>
            <Button className="mt-4 bg-[#ed0923] text-white hover:bg-[#d10820]" onClick={() => navigate("/user-home")}>Back to Dashboard</Button>
          </div>
        </main>
        <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
      </div>
    );
  }

  const handleSubmit = () => {
    const now = new Date();
    const formattedTimestamp = now.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
    setSubmittedAt(formattedTimestamp);
    markRequiredActionResolved(task.id);
    navigate("/required-actions", {
      state: {
        successMessage: "Resolved successfully.",
      },
      replace: true,
    });
  };

  const isPending = task.state === "pending";

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation activePage="Required Actions" onProfileClick={() => setIsProfileOpen(true)} />
      <main className="mx-auto max-w-[900px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Action Form</h1>
            <p className="mt-1 text-sm text-gray-600">
              Submit input for this task instance so the workflow can continue execution.
            </p>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">State</p>
                <p className="mt-1 text-sm font-medium text-gray-900">{task.state}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Run After</p>
                <p className="mt-1 text-sm text-gray-900">{task.runAfter}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Map Index</p>
                <p className="mt-1 text-sm text-gray-900">{task.mapIndex}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Responded At</p>
                <p className="mt-1 text-sm text-gray-900">{submittedAt || task.respondedAt}</p>
              </div>
            </div>

            <div className="mt-4 border-t border-gray-200 pt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Subject</p>
              <p className="mt-1 text-sm font-semibold text-gray-900">{task.subject}</p>
            </div>

            {isPending ? (
              <>
                <div className="mt-6">
                  <p className="text-sm font-semibold text-gray-900">Response Type</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      variant={decision === "provide-input" ? "default" : "outline"}
                      className={decision === "provide-input" ? "bg-[#ed0923] text-white hover:bg-[#d10820]" : "border-gray-300"}
                      onClick={() => setDecision("provide-input")}
                    >
                      Provide Input
                    </Button>
                    <Button
                      variant={decision === "request-changes" ? "default" : "outline"}
                      className={decision === "request-changes" ? "bg-[#ed0923] text-white hover:bg-[#d10820]" : "border-gray-300"}
                      onClick={() => setDecision("request-changes")}
                    >
                      Request Changes
                    </Button>
                    <Button
                      variant={decision === "escalate-admin" ? "default" : "outline"}
                      className={decision === "escalate-admin" ? "bg-[#ed0923] text-white hover:bg-[#d10820]" : "border-gray-300"}
                      onClick={() => setDecision("escalate-admin")}
                    >
                      Escalate to Admin
                    </Button>
                  </div>
                </div>

                <div className="mt-4">
                  <p className="mb-2 text-sm font-semibold text-gray-900">Response Notes</p>
                  <Textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    rows={5}
                    placeholder="Provide action details for this task instance..."
                  />
                </div>

                <div className="mt-4 flex gap-2">
                  <Button
                    onClick={handleSubmit}
                    className="bg-[#ed0923] text-white hover:bg-[#d10820]"
                    disabled={!notes.trim()}
                  >
                    Resolve Action
                  </Button>
                  <Button variant="outline" className="border-gray-300" onClick={() => navigate("/user-home")}>Back to Dashboard</Button>
                </div>
              </>
            ) : (
              <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700">
                This task already has a recorded response. Review details above.
              </div>
            )}
          </div>
        </div>
      </main>
      <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
    </div>
  );
}
