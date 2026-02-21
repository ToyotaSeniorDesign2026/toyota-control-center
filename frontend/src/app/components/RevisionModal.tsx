import { X, Save, AlertCircle } from "lucide-react";
import { Button } from "./ui/button";
import { useState, useEffect } from "react";

interface Resource {
  id: string;
  name: string;
  type: "AI Agent" | "SQL Query" | "dbt Model" | "API Connection";
  status: string;
  currentEnvironment: string;
  targetEnvironment?: string;
  createdAt: string;
  description?: string;
  rejectionReason?: string;
}

interface RevisionModalProps {
  resource: Resource | null;
  isOpen: boolean;
  onClose: () => void;
}

export function RevisionModal({ resource, isOpen, onClose }: RevisionModalProps) {
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    notes: "",
  });

  useEffect(() => {
    if (resource) {
      setFormData({
        name: resource.name,
        description: resource.description || "",
        notes: "",
      });
    }
  }, [resource]);

  if (!isOpen || !resource) return null;

  const handleSubmit = () => {
    console.log("Resubmitting resource:", formData);
    // Handle resubmission
    handleClose();
  };

  const handleClose = () => {
    setFormData({
      name: "",
      description: "",
      notes: "",
    });
    onClose();
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case "AI Agent":
        return "text-purple-600 bg-purple-50";
      case "SQL Query":
        return "text-green-600 bg-green-50";
      case "dbt Model":
        return "text-orange-600 bg-orange-50";
      case "API Connection":
        return "text-blue-600 bg-blue-50";
      default:
        return "text-gray-600 bg-gray-50";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="relative w-full max-w-3xl max-h-[90vh] overflow-hidden rounded-lg border border-gray-200 bg-white shadow-xl">
        {/* Header */}
        <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-semibold text-gray-900">Revise Resource</h2>
                <span className={`rounded-full px-3 py-1 text-xs font-medium ${getTypeColor(resource.type)}`}>
                  {resource.type}
                </span>
              </div>
              <p className="mt-1 text-sm text-gray-600">Make necessary changes and resubmit for approval</p>
            </div>
            <button
              onClick={handleClose}
              className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="overflow-y-auto max-h-[calc(90vh-200px)] p-6 space-y-6">
          {/* Rejection Reason */}
          {resource.rejectionReason && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <h4 className="text-sm font-semibold text-red-900 mb-1">Rejection Reason</h4>
                  <p className="text-sm text-red-800">{resource.rejectionReason}</p>
                </div>
              </div>
            </div>
          )}

          {/* Resource Details */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <span className="text-xs font-medium text-gray-600">Resource ID</span>
              <p className="text-sm font-semibold text-gray-900 mt-1">{resource.id}</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <span className="text-xs font-medium text-gray-600">Current Environment</span>
              <p className="text-sm font-semibold text-gray-900 mt-1">{resource.currentEnvironment}</p>
            </div>
          </div>

          {/* Editable Fields */}
          <div className="space-y-4">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                Resource Name
              </label>
              <input
                id="name"
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
              />
            </div>

            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-2">
                Description
              </label>
              <textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={4}
                className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923] resize-none"
                placeholder="Describe what this resource does and any changes made..."
              />
            </div>

            <div>
              <label htmlFor="notes" className="block text-sm font-medium text-gray-700 mb-2">
                Revision Notes
              </label>
              <textarea
                id="notes"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                rows={3}
                className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923] resize-none"
                placeholder="Explain what changes you made to address the rejection feedback..."
              />
              <p className="mt-2 text-xs text-gray-500">
                These notes will be visible to approvers
              </p>
            </div>
          </div>

          {/* Additional Configuration Section */}
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
            <h4 className="text-sm font-semibold text-gray-900 mb-3">Additional Configuration</h4>
            <div className="space-y-3">
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-[#ed0923] focus:ring-[#ed0923]"
                />
                <span className="text-sm text-gray-700">Enable enhanced error handling</span>
              </label>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-[#ed0923] focus:ring-[#ed0923]"
                />
                <span className="text-sm text-gray-700">Add comprehensive logging</span>
              </label>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-[#ed0923] focus:ring-[#ed0923]"
                />
                <span className="text-sm text-gray-700">Run performance optimization</span>
              </label>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 bg-gray-50 px-6 py-4">
          <div className="flex justify-between">
            <Button
              onClick={handleClose}
              variant="outline"
              className="gap-2"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!formData.name.trim() || !formData.description.trim() || !formData.notes.trim()}
              className="gap-2 bg-[#ed0923] text-white hover:bg-[#d10820]"
            >
              <Save className="h-4 w-4" />
              Resubmit for Approval
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
