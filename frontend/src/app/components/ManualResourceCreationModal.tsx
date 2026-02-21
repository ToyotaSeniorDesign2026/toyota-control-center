import { X, ChevronRight, ChevronLeft } from "lucide-react";
import { Button } from "./ui/button";
import { useState } from "react";

interface ManualResourceCreationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ManualResourceCreationModal({ isOpen, onClose }: ManualResourceCreationModalProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState({
    name: "",
    type: "",
    environment: "",
    description: "",
  });

  if (!isOpen) return null;

  const totalSteps = 4;

  const handleNext = () => {
    if (currentStep < totalSteps) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSubmit = () => {
    // Handle form submission
    console.log("Form submitted:", formData);
    handleClose();
  };

  const handleClose = () => {
    setCurrentStep(1);
    setFormData({
      name: "",
      type: "",
      environment: "",
      description: "",
    });
    onClose();
  };

  const isStepValid = () => {
    switch (currentStep) {
      case 1:
        return formData.name.trim() !== "";
      case 2:
        return formData.type !== "";
      case 3:
        return formData.environment !== "";
      case 4:
        return formData.description.trim() !== "";
      default:
        return false;
    }
  };

  const resourceTypes = [
    { value: "AI Agent", label: "AI Agent", color: "purple" },
    { value: "SQL Query", label: "SQL Query", color: "green" },
    { value: "dbt Model", label: "dbt Model", color: "orange" },
    { value: "API Connection", label: "API Connection", color: "blue" },
  ];

  const environments = [
    { value: "Dev", label: "Development", description: "For testing and development" },
    { value: "Staging", label: "Staging", description: "Pre-production testing environment" },
    { value: "Production", label: "Production", description: "Live production environment" },
  ];

  const getColorClasses = (color: string, selected: boolean) => {
    const baseClasses = "border-2 transition-all";
    if (selected) {
      switch (color) {
        case "purple":
          return `${baseClasses} border-purple-500 bg-purple-50`;
        case "green":
          return `${baseClasses} border-green-500 bg-green-50`;
        case "orange":
          return `${baseClasses} border-orange-500 bg-orange-50`;
        case "blue":
          return `${baseClasses} border-blue-500 bg-blue-50`;
        default:
          return `${baseClasses} border-gray-300 bg-white`;
      }
    }
    return `${baseClasses} border-gray-200 bg-white hover:border-gray-300`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-hidden rounded-lg border border-gray-200 bg-white shadow-xl">
        {/* Header */}
        <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-gray-900">Create Resource Manually</h2>
              <p className="mt-1 text-sm text-gray-600">
                Step {currentStep} of {totalSteps}
              </p>
            </div>
            <button
              onClick={handleClose}
              className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          {/* Progress Bar */}
          <div className="mt-4 flex gap-2">
            {[...Array(totalSteps)].map((_, index) => (
              <div
                key={index}
                className={`h-2 flex-1 rounded-full transition-colors ${
                  index + 1 <= currentStep ? "bg-[#ed0923]" : "bg-gray-200"
                }`}
              />
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="overflow-y-auto max-h-[calc(90vh-240px)] p-6">
          {/* Step 1: Resource Name */}
          {currentStep === 1 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Resource Name</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Choose a unique and descriptive name for your resource
                </p>
              </div>
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                  Name
                </label>
                <input
                  id="name"
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., customer_data_analysis"
                  className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                />
                <p className="mt-2 text-xs text-gray-500">
                  Use lowercase letters, numbers, and underscores only
                </p>
              </div>
            </div>
          )}

          {/* Step 2: Resource Type */}
          {currentStep === 2 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Resource Type</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Select the type of resource you want to create
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {resourceTypes.map((type) => (
                  <button
                    key={type.value}
                    onClick={() => setFormData({ ...formData, type: type.value })}
                    className={`rounded-lg p-4 text-left ${getColorClasses(
                      type.color,
                      formData.type === type.value
                    )}`}
                  >
                    <div className="font-semibold text-gray-900">{type.label}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 3: Environment */}
          {currentStep === 3 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Environment</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Choose where this resource will be deployed
                </p>
              </div>
              <div className="space-y-3">
                {environments.map((env) => (
                  <button
                    key={env.value}
                    onClick={() => setFormData({ ...formData, environment: env.value })}
                    className={`w-full rounded-lg border-2 p-4 text-left transition-all ${
                      formData.environment === env.value
                        ? "border-[#ed0923] bg-red-50"
                        : "border-gray-200 bg-white hover:border-gray-300"
                    }`}
                  >
                    <div className="font-semibold text-gray-900">{env.label}</div>
                    <div className="text-sm text-gray-600 mt-1">{env.description}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 4: Description */}
          {currentStep === 4 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Description</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Provide a detailed description of what this resource does
                </p>
              </div>
              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-2">
                  Description
                </label>
                <textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Describe the purpose, functionality, and any important details about this resource..."
                  rows={6}
                  className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923] resize-none"
                />
                <p className="mt-2 text-xs text-gray-500">
                  Minimum 20 characters recommended
                </p>
              </div>

              {/* Summary */}
              <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4">
                <h4 className="text-sm font-semibold text-gray-900 mb-3">Summary</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Name:</span>
                    <span className="font-medium text-gray-900">{formData.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Type:</span>
                    <span className="font-medium text-gray-900">{formData.type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Environment:</span>
                    <span className="font-medium text-gray-900">{formData.environment}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 bg-gray-50 px-6 py-4">
          <div className="flex justify-between">
            <Button
              onClick={handleBack}
              disabled={currentStep === 1}
              variant="outline"
              className="gap-2"
            >
              <ChevronLeft className="h-4 w-4" />
              Back
            </Button>
            {currentStep < totalSteps ? (
              <Button
                onClick={handleNext}
                disabled={!isStepValid()}
                className="gap-2 bg-[#ed0923] text-white hover:bg-[#d10820]"
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={handleSubmit}
                disabled={!isStepValid()}
                className="bg-[#ed0923] text-white hover:bg-[#d10820]"
              >
                Create Resource
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
