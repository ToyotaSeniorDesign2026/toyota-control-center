import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import {
  getVisibleRequiredActions,
  requiredActionStateBadge,
} from "./requiredActionsData";

export default function RequiredActions() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [visibleActions, setVisibleActions] = useState(() => getVisibleRequiredActions());
  const navigate = useNavigate();
  const location = useLocation();

  const successMessage = (location.state as { successMessage?: string } | null)?.successMessage;

  useEffect(() => {
    setVisibleActions(getVisibleRequiredActions());
  }, []);

  const pendingItemCount = useMemo(
    () => visibleActions.filter((item) => item.state === "pending").length,
    [visibleActions]
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation activePage="Required Actions" onProfileClick={() => setIsProfileOpen(true)} />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          {successMessage && (
            <div className="rounded-lg border border-green-200 bg-green-50 px-5 py-3 text-sm font-medium text-green-800">
              {successMessage}
            </div>
          )}
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Required Actions</h1>
            <p className="mt-1 text-sm text-gray-600">
              Task instances awaiting your input or requiring follow-up from earlier runs.
            </p>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 p-5">
              <h2 className="text-lg font-semibold text-gray-900">Action Queue</h2>
              <p className="mt-1 text-sm text-gray-600">
                Pending items: {pendingItemCount}. Click a pending subject to submit input.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50">
                  <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                    <th className="px-5 py-3 font-semibold">State</th>
                    <th className="px-5 py-3 font-semibold">Subject</th>
                    <th className="px-5 py-3 font-semibold">Run After</th>
                    <th className="px-5 py-3 font-semibold">Map Index</th>
                    <th className="px-5 py-3 font-semibold">Responded At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {visibleActions.map((item) => (
                    <tr key={item.id} className="align-top">
                      <td className="px-5 py-4">
                        <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${requiredActionStateBadge(item.state)}`}>
                          {item.state}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <button
                          onClick={() =>
                            navigate(`/required-actions/${item.id}`, {
                              state: { task: item },
                            })
                          }
                          className={`text-left text-sm font-medium ${
                            item.state === "pending"
                              ? "text-[#ed0923] hover:underline"
                              : "text-gray-800 hover:underline"
                          }`}
                        >
                          {item.subject}
                        </button>
                      </td>
                      <td className="px-5 py-4 text-gray-600">{item.runAfter}</td>
                      <td className="px-5 py-4 text-gray-600">{item.mapIndex}</td>
                      <td className="px-5 py-4 text-gray-600">{item.respondedAt}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {visibleActions.length === 0 && (
                <div className="border-t border-gray-200 px-5 py-6 text-sm text-gray-500">
                  No required actions are waiting on you right now.
                </div>
              )}
              <div className="border-t border-gray-200 bg-gray-50 px-5 py-3 text-xs text-gray-600">
                Selecting a pending subject opens the action form to provide input and continue execution.
              </div>
            </div>
          </div>
        </div>
      </main>
      <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
    </div>
  );
}
