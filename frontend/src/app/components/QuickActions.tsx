import { ArrowUpCircle, FileText, Play, Terminal } from "lucide-react";
import { Button } from "./ui/button";

interface QuickAction {
  id: string;
  label: string;
  icon: React.ReactNode;
  primary?: boolean;
}

const quickActions: QuickAction[] = [
  {
    id: "2",
    label: "Run Job",
    icon: <Play className="h-4 w-4" />,
    primary: true,
  },
  {
    id: "3",
    label: "Promote to Next Environment",
    icon: <ArrowUpCircle className="h-4 w-4" />,
  },
  {
    id: "4",
    label: "View Logs",
    icon: <FileText className="h-4 w-4" />,
  },
  {
    id: "5",
    label: "Copy CLI Command",
    icon: <Terminal className="h-4 w-4" />,
  },
];

export function QuickActions() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-200 p-5">
        <h2 className="text-lg font-semibold text-gray-900">Quick Actions</h2>
      </div>
      <div className="p-5">
        <div className="space-y-2">
          {quickActions.map((action) => (
            <Button
              key={action.id}
              variant={action.primary ? "default" : "outline"}
              className={`w-full justify-start gap-3 h-11 text-sm font-medium transition-all ${
                action.primary
                  ? "bg-[#ed0923] hover:bg-[#d10820] text-white border-0 shadow-sm"
                  : "border-gray-200 bg-white hover:bg-gray-50 text-gray-700 hover:text-gray-900 hover:border-gray-300"
              }`}
            >
              <span className={action.primary ? "text-white" : "text-gray-500"}>
                {action.icon}
              </span>
              <span>{action.label}</span>
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
}