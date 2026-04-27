import { useState, useEffect, useRef } from "react";
import { X, Plus, Trash2 } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Checkbox } from "./ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";

type JobType = "Airflow" | "Excel" | "PowerPoint";

interface UniversalFields {
  job_name: string;
  description: string;
  owner: string;
  environment: string;
  schedule: string;
  approval_required: boolean;
  tags: string[];
  run_type: string;
}

interface AirflowDetails {
  dag_name: string;
  tasks: string[];
  dependencies_between_tasks: string;
  scripts_sql: string;
  data_sources: string;
  data_destinations: string;
  retry_policy: string;
  execution_timeout: string;
}

interface ExcelDetails {
  input_data_sources: string;
  transformations: string;
  filters: string;
  pivot_tables: boolean;
  formulas: string;
  output_file_name: string;
  file_location: string;
}

interface PowerPointDetails {
  data_source: string;
  slide_template: string;
  metrics_to_include: string;
  charts: string;
  text_summary_placeholder: string;
  branding_theme: string;
  output_location: string;
}

interface CreateJobInputs {
  universal: UniversalFields;
  job_type: JobType;
  job_details: AirflowDetails | ExcelDetails | PowerPointDetails;
}

interface CreateJobFormProps {
  onSubmit?: (jobData: CreateJobInputs) => void;
  onCancel?: () => void;
  draftData?: Record<string, any>;
  onDraftDataChange?: (data: Record<string, any>) => void;
  hideFooter?: boolean;
}

export function CreateJobForm({
  onSubmit,
  onCancel,
  draftData,
  onDraftDataChange,
  hideFooter = false,
}: CreateJobFormProps) {
  const [jobType, setJobType] = useState<JobType>("Airflow");
  const [currentTag, setCurrentTag] = useState("");

  // Universal Fields
  const [universal, setUniversal] = useState<UniversalFields>({
    job_name: "",
    description: "",
    owner: "",
    environment: "dev",
    schedule: "",
    approval_required: false,
    tags: [],
    run_type: "manual",
  });

  // Airflow Details
  const [airflowDetails, setAirflowDetails] = useState<AirflowDetails>({
    dag_name: "",
    tasks: [],
    dependencies_between_tasks: "",
    scripts_sql: "",
    data_sources: "",
    data_destinations: "",
    retry_policy: "",
    execution_timeout: "",
  });

  const [currentTask, setCurrentTask] = useState("");

  // Excel Details
  const [excelDetails, setExcelDetails] = useState<ExcelDetails>({
    input_data_sources: "",
    transformations: "",
    filters: "",
    pivot_tables: false,
    formulas: "",
    output_file_name: "",
    file_location: "",
  });

  // PowerPoint Details
  const [powerpointDetails, setPowerpointDetails] = useState<PowerPointDetails>({
    data_source: "",
    slide_template: "",
    metrics_to_include: "",
    charts: "",
    text_summary_placeholder: "[AI will generate text summary here]",
    branding_theme: "",
    output_location: "",
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const isApplyingDraftDataRef = useRef(false);

  // Helper function to build the current draft object and notify parent
  const updateDraftAndParent = (
    type: JobType,
    uni: UniversalFields,
    airflow: AirflowDetails,
    excel: ExcelDetails,
    powerpoint: PowerPointDetails
  ) => {
    if (!onDraftDataChange || isApplyingDraftDataRef.current) return;

    const draft: Record<string, any> = {
      job_type: type,
      ...uni,
    };

    if (type === "Airflow") {
      draft.dag_name = airflow.dag_name;
      draft.tasks = airflow.tasks;
      draft.dependencies_between_tasks = airflow.dependencies_between_tasks;
      draft.scripts_sql = airflow.scripts_sql;
      // Convert comma-separated strings back to arrays
      if (airflow.data_sources) draft.data_sources = airflow.data_sources.split(",").map(s => s.trim()).filter(s => s);
      if (airflow.data_destinations) draft.data_destinations = airflow.data_destinations.split(",").map(s => s.trim()).filter(s => s);
      draft.retry_policy = airflow.retry_policy;
      draft.execution_timeout = airflow.execution_timeout;
    } else if (type === "Excel") {
      draft.input_data_sources = excel.input_data_sources;
      draft.transformations = excel.transformations;
      draft.filters = excel.filters;
      draft.pivot_tables = excel.pivot_tables;
      draft.formulas = excel.formulas;
      draft.output_file_name = excel.output_file_name;
      draft.file_location = excel.file_location;
    } else if (type === "PowerPoint") {
      draft.data_source = powerpoint.data_source;
      draft.slide_template = powerpoint.slide_template;
      draft.metrics_to_include = powerpoint.metrics_to_include;
      draft.charts = powerpoint.charts;
      draft.text_summary = powerpoint.text_summary_placeholder;
      draft.branding_theme = powerpoint.branding_theme;
      draft.output_location = powerpoint.output_location;
    }

    onDraftDataChange(draft);
  };

  // Sync draft data into form fields when draftData changes
  useEffect(() => {
    if (!draftData) return;
    
    isApplyingDraftDataRef.current = true;
    
    // Update job_type if provided
    if (draftData.job_type && ["Airflow", "Excel", "PowerPoint"].includes(draftData.job_type)) {
      setJobType(draftData.job_type);
    }
    
    // Update universal fields
    setUniversal((prev) => ({
      ...prev,
      ...(draftData.job_name !== undefined && { job_name: draftData.job_name }),
      ...(draftData.description !== undefined && { description: draftData.description }),
      ...(draftData.owner !== undefined && { owner: draftData.owner }),
      ...(draftData.environment !== undefined && { environment: draftData.environment }),
      ...(draftData.schedule !== undefined && { schedule: draftData.schedule }),
      ...(draftData.approval_required !== undefined && { approval_required: draftData.approval_required }),
      ...(draftData.tags && Array.isArray(draftData.tags) && { tags: draftData.tags }),
      ...(draftData.run_type !== undefined && { run_type: draftData.run_type }),
    }));
    
    // Update type-specific fields
    if (draftData.job_type === "Airflow") {
      setAirflowDetails((prev) => ({
        ...prev,
        ...(draftData.dag_name !== undefined && { dag_name: draftData.dag_name }),
        ...(draftData.tasks && Array.isArray(draftData.tasks) && { tasks: draftData.tasks }),
        ...(draftData.dependencies_between_tasks !== undefined && { dependencies_between_tasks: draftData.dependencies_between_tasks }),
        ...(draftData.scripts_sql !== undefined && { scripts_sql: draftData.scripts_sql }),
        ...(draftData.data_sources && Array.isArray(draftData.data_sources) && { data_sources: draftData.data_sources.join(", ") }),
        ...(draftData.data_destinations && Array.isArray(draftData.data_destinations) && { data_destinations: draftData.data_destinations.join(", ") }),
        ...(draftData.retry_policy !== undefined && { retry_policy: draftData.retry_policy }),
        ...(draftData.execution_timeout !== undefined && { execution_timeout: draftData.execution_timeout }),
      }));
    } else if (draftData.job_type === "Excel") {
      setExcelDetails((prev) => ({
        ...prev,
        ...(draftData.input_data_sources !== undefined && { input_data_sources: draftData.input_data_sources }),
        ...(draftData.transformations !== undefined && { transformations: draftData.transformations }),
        ...(draftData.filters !== undefined && { filters: draftData.filters }),
        ...(draftData.pivot_tables !== undefined && { pivot_tables: draftData.pivot_tables }),
        ...(draftData.formulas !== undefined && { formulas: draftData.formulas }),
        ...(draftData.output_file_name !== undefined && { output_file_name: draftData.output_file_name }),
        ...(draftData.file_location !== undefined && { file_location: draftData.file_location }),
      }));
    } else if (draftData.job_type === "PowerPoint") {
      setPowerpointDetails((prev) => ({
        ...prev,
        ...(draftData.data_source !== undefined && { data_source: draftData.data_source }),
        ...(draftData.slide_template !== undefined && { slide_template: draftData.slide_template }),
        ...(draftData.metrics_to_include !== undefined && { metrics_to_include: draftData.metrics_to_include }),
        ...(draftData.charts !== undefined && { charts: draftData.charts }),
        ...(draftData.text_summary !== undefined && { text_summary_placeholder: draftData.text_summary }),
        ...(draftData.branding_theme !== undefined && { branding_theme: draftData.branding_theme }),
        ...(draftData.output_location !== undefined && { output_location: draftData.output_location }),
      }));
    }
    
    // Reset flag after state updates
    setTimeout(() => {
      isApplyingDraftDataRef.current = false;
    }, 0);
  }, [draftData]);

  // Sync form state changes back to parent (but only when user makes changes, not when draftData is applied)
  useEffect(() => {
    updateDraftAndParent(jobType, universal, airflowDetails, excelDetails, powerpointDetails);
  }, [jobType, universal, airflowDetails, excelDetails, powerpointDetails, onDraftDataChange]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!universal.job_name.trim()) {
      newErrors.job_name = "Job name is required";
    }
    if (!universal.owner.trim()) {
      newErrors.owner = "Owner is required";
    }
    if (!universal.schedule.trim()) {
      newErrors.schedule = "Schedule is required";
    }

    if (jobType === "Airflow" && !airflowDetails.dag_name.trim()) {
      newErrors.dag_name = "DAG name is required";
    }
    if (jobType === "Excel" && !excelDetails.output_file_name.trim()) {
      newErrors.output_file_name = "Output file name is required";
    }
    if (jobType === "PowerPoint" && !powerpointDetails.slide_template.trim()) {
      newErrors.slide_template = "Slide template is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleAddTag = () => {
    if (currentTag.trim() && !universal.tags.includes(currentTag.trim())) {
      setUniversal({
        ...universal,
        tags: [...universal.tags, currentTag.trim()],
      });
      setCurrentTag("");
    }
  };

  const handleRemoveTag = (tag: string) => {
    setUniversal({
      ...universal,
      tags: universal.tags.filter((t) => t !== tag),
    });
  };

  const handleAddTask = () => {
    if (currentTask.trim() && !airflowDetails.tasks.includes(currentTask.trim())) {
      setAirflowDetails({
        ...airflowDetails,
        tasks: [...airflowDetails.tasks, currentTask.trim()],
      });
      setCurrentTask("");
    }
  };

  const handleRemoveTask = (task: string) => {
    setAirflowDetails({
      ...airflowDetails,
      tasks: airflowDetails.tasks.filter((t) => t !== task),
    });
  };

  const handleSubmit = () => {
    if (!validateForm()) {
      return;
    }

    let jobDetails: AirflowDetails | ExcelDetails | PowerPointDetails;

    if (jobType === "Airflow") {
      jobDetails = airflowDetails;
    } else if (jobType === "Excel") {
      jobDetails = excelDetails;
    } else {
      jobDetails = powerpointDetails;
    }

    const payload: CreateJobInputs = {
      universal,
      job_type: jobType,
      job_details: jobDetails,
    };

    if (onSubmit) {
      onSubmit(payload);
    }

    // Reset form
    handleClose();
  };

  const handleClose = () => {
    setUniversal({
      job_name: "",
      description: "",
      owner: "",
      environment: "dev",
      schedule: "",
      approval_required: false,
      tags: [],
      run_type: "manual",
    });
    setAirflowDetails({
      dag_name: "",
      tasks: [],
      dependencies_between_tasks: "",
      scripts_sql: "",
      data_sources: "",
      data_destinations: "",
      retry_policy: "",
      execution_timeout: "",
    });
    setExcelDetails({
      input_data_sources: "",
      transformations: "",
      filters: "",
      pivot_tables: false,
      formulas: "",
      output_file_name: "",
      file_location: "",
    });
    setPowerpointDetails({
      data_source: "",
      slide_template: "",
      metrics_to_include: "",
      charts: "",
      text_summary_placeholder: "[AI will generate text summary here]",
      branding_theme: "",
      output_location: "",
    });
    setCurrentTask("");
    setCurrentTag("");
    setErrors({});
    setJobType("Airflow");
    if (onCancel) {
      onCancel();
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-white">
      {/* Header - Fixed */}
      <div className="flex-shrink-0 px-4 py-6 border-b border-gray-200 sm:px-6 lg:px-8">
        <div className="w-full">
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-gray-900">Create New Job</h1>
          <p className="mt-1 text-sm text-gray-600">
            Set up a new job with universal configuration and job-type specific details.
          </p>
        </div>
      </div>

      {/* Form Content - Scrollable, Responsive */}
      <div className="flex-1 overflow-y-auto w-full">
        <div className="w-full h-full flex flex-col">
          <div className="w-full px-4 py-6 sm:px-6 lg:px-8">
            {/* Main form container - centered with max-width */}
            <div className="w-full max-w-4xl mx-auto space-y-8">
              {/* Universal Details Section */}
              <div className="space-y-6 pb-6 border-b border-gray-200">
                <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide">
                  Universal Details
                </h3>

                {/* Job Name */}
                <div className="space-y-2">
                  <Label htmlFor="job_name" className="text-sm font-medium text-gray-700">
                    Job Name *
                  </Label>
                  <Input
                    id="job_name"
                    placeholder="e.g., Monthly Sales Report"
                    value={universal.job_name}
                    onChange={(e) =>
                      setUniversal({ ...universal, job_name: e.target.value })
                    }
                    className={`w-full ${errors.job_name ? "border-red-500" : ""}`}
                  />
                  {errors.job_name && (
                    <p className="text-xs text-red-600">{errors.job_name}</p>
                  )}
                </div>

                {/* Description */}
                <div className="space-y-2">
                  <Label htmlFor="description" className="text-sm font-medium text-gray-700">
                    Description
                  </Label>
                  <textarea
                    id="description"
                    placeholder="Provide details about this job"
                    value={universal.description}
                    onChange={(e) =>
                      setUniversal({ ...universal, description: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                    rows={3}
                  />
                </div>

                {/* Two-Column Responsive Layout: Owner & Environment */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Owner */}
                  <div className="space-y-2">
                    <Label htmlFor="owner" className="text-sm font-medium text-gray-700">
                      Owner *
                    </Label>
                    <Input
                      id="owner"
                      placeholder="e.g., John Doe"
                      value={universal.owner}
                      onChange={(e) =>
                        setUniversal({ ...universal, owner: e.target.value })
                      }
                      className={`w-full ${errors.owner ? "border-red-500" : ""}`}
                    />
                    {errors.owner && (
                      <p className="text-xs text-red-600">{errors.owner}</p>
                    )}
                  </div>

                  {/* Environment */}
                  <div className="space-y-2">
                    <Label htmlFor="environment" className="text-sm font-medium text-gray-700">
                      Environment
                    </Label>
                    <Select value={universal.environment} onValueChange={(value) =>
                      setUniversal({ ...universal, environment: value })
                    }>
                      <SelectTrigger id="environment" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="dev">Development</SelectItem>
                        <SelectItem value="staging">Staging</SelectItem>
                        <SelectItem value="production">Production</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Two-Column Responsive Layout: Schedule & Run Type */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Schedule */}
                  <div className="space-y-2">
                    <Label htmlFor="schedule" className="text-sm font-medium text-gray-700">
                      Schedule *
                    </Label>
                    <Input
                      id="schedule"
                      placeholder="e.g., Daily at 08:00 AM"
                      value={universal.schedule}
                      onChange={(e) =>
                        setUniversal({ ...universal, schedule: e.target.value })
                      }
                      className={`w-full ${errors.schedule ? "border-red-500" : ""}`}
                    />
                    {errors.schedule && (
                      <p className="text-xs text-red-600">{errors.schedule}</p>
                    )}
                  </div>

                  {/* Run Type */}
                  <div className="space-y-2">
                    <Label htmlFor="run_type" className="text-sm font-medium text-gray-700">
                      Run Type
                    </Label>
                    <Select value={universal.run_type} onValueChange={(value) =>
                      setUniversal({ ...universal, run_type: value })
                    }>
                      <SelectTrigger id="run_type" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="manual">Manual</SelectItem>
                        <SelectItem value="scheduled">Scheduled</SelectItem>
                        <SelectItem value="triggered">Triggered</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Approval Required */}
                <div className="flex items-center gap-3 py-2">
                  <Checkbox
                    id="approval_required"
                    checked={universal.approval_required}
                    onCheckedChange={(checked) =>
                      setUniversal({
                        ...universal,
                        approval_required: checked === true,
                      })
                    }
                  />
                  <Label
                    htmlFor="approval_required"
                    className="text-sm font-medium text-gray-700 cursor-pointer"
                  >
                    Approval Required
                  </Label>
                </div>

                {/* Tags */}
                <div className="space-y-2">
                  <Label className="text-sm font-medium text-gray-700">Tags</Label>
                  <div className="flex flex-col sm:flex-row gap-2 mb-2">
                    <Input
                      placeholder="Add tag and press Enter or click +"
                      value={currentTag}
                      onChange={(e) => setCurrentTag(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          handleAddTag();
                        }
                      }}
                      className="w-full sm:flex-1"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleAddTag}
                      className="px-3 w-full sm:w-auto"
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                  {universal.tags.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {universal.tags.map((tag) => (
                        <div
                          key={tag}
                          className="inline-flex items-center gap-2 px-2.5 py-1 bg-[#ed0923]/10 text-[#ed0923] rounded-full text-xs font-medium"
                        >
                          {tag}
                          <button
                            onClick={() => handleRemoveTag(tag)}
                            className="hover:text-[#d10820]"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Job Type Selector */}
              <div className="space-y-4 pb-6 border-b border-gray-200">
                <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide">
                  Job Type Details
                </h3>

                <div className="space-y-2">
                  <Label className="text-sm font-medium text-gray-700">Job Type</Label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {(["Airflow", "Excel", "PowerPoint"] as const).map((type) => (
                      <button
                        key={type}
                        onClick={() => setJobType(type)}
                        className={`py-2.5 px-4 rounded-lg font-medium text-sm transition ${
                          jobType === type
                            ? "bg-[#ed0923] text-white"
                            : "border border-gray-300 text-gray-700 hover:bg-gray-50"
                        }`}
                      >
                        {type}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Airflow Specific Fields */}
              {jobType === "Airflow" && (
                <div className="space-y-6 mt-6 pt-6 border-t border-gray-100">
                  {/* DAG Name */}
                  <div className="space-y-2">
                    <Label htmlFor="dag_name" className="text-sm font-medium text-gray-700">
                      DAG Name *
                    </Label>
                    <Input
                      id="dag_name"
                      placeholder="e.g., daily_sales_etl"
                      value={airflowDetails.dag_name}
                      onChange={(e) =>
                        setAirflowDetails({
                          ...airflowDetails,
                          dag_name: e.target.value,
                        })
                      }
                      className={`w-full ${errors.dag_name ? "border-red-500" : ""}`}
                    />
                    {errors.dag_name && (
                      <p className="text-xs text-red-600">{errors.dag_name}</p>
                    )}
                  </div>

                  {/* Tasks */}
                  <div className="space-y-2">
                    <Label className="text-sm font-medium text-gray-700">Tasks</Label>
                    <div className="flex flex-col sm:flex-row gap-2 mb-2">
                      <Input
                        placeholder="Add task name"
                        value={currentTask}
                        onChange={(e) => setCurrentTask(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            handleAddTask();
                          }
                        }}
                        className="w-full sm:flex-1"
                      />
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleAddTask}
                        className="px-3 w-full sm:w-auto"
                      >
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>
                    {airflowDetails.tasks.length > 0 && (
                      <div className="space-y-1.5 mt-2">
                        {airflowDetails.tasks.map((task) => (
                          <div
                            key={task}
                            className="flex items-center justify-between p-2 bg-gray-50 rounded-lg border border-gray-200"
                          >
                            <span className="text-sm text-gray-700 truncate">{task}</span>
                            <button
                              onClick={() => handleRemoveTask(task)}
                              className="p-1 hover:bg-gray-200 rounded text-gray-500 hover:text-gray-700 transition flex-shrink-0"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Dependencies Between Tasks & Retry Policy - Two Column */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Dependencies Between Tasks */}
                    <div className="space-y-2">
                      <Label htmlFor="dependencies" className="text-sm font-medium text-gray-700">
                        Dependencies Between Tasks
                      </Label>
                      <textarea
                        id="dependencies"
                        placeholder="e.g., task_a → task_b → task_c"
                        value={airflowDetails.dependencies_between_tasks}
                        onChange={(e) =>
                          setAirflowDetails({
                            ...airflowDetails,
                            dependencies_between_tasks: e.target.value,
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                        rows={3}
                      />
                    </div>

                    {/* Retry Policy */}
                    <div className="space-y-2">
                      <Label htmlFor="retry_policy" className="text-sm font-medium text-gray-700">
                        Retry Policy
                      </Label>
                      <textarea
                        id="retry_policy"
                        placeholder="e.g., 3 retries with 5 minute backoff"
                        value={airflowDetails.retry_policy}
                        onChange={(e) =>
                          setAirflowDetails({
                            ...airflowDetails,
                            retry_policy: e.target.value,
                          })
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                        rows={3}
                      />
                    </div>
                  </div>

                  {/* Scripts / SQL */}
                  <div className="space-y-2">
                    <Label htmlFor="scripts_sql" className="text-sm font-medium text-gray-700">
                      Scripts / SQL
                    </Label>
                    <textarea
                      id="scripts_sql"
                      placeholder="Paste your SQL queries or script references"
                      value={airflowDetails.scripts_sql}
                      onChange={(e) =>
                        setAirflowDetails({
                          ...airflowDetails,
                          scripts_sql: e.target.value,
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      rows={3}
                    />
                  </div>

                  {/* Data Sources + Data Destinations */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label htmlFor="data_sources" className="text-sm font-medium text-gray-700">
                        Data Sources
                      </Label>
                      <Input
                        id="data_sources"
                        placeholder="e.g., S3 bucket, Database, API endpoint"
                        value={airflowDetails.data_sources}
                        onChange={(e) =>
                          setAirflowDetails({
                            ...airflowDetails,
                            data_sources: e.target.value,
                          })
                        }
                        className="w-full"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="data_destinations" className="text-sm font-medium text-gray-700">
                        Data Destinations
                      </Label>
                      <Input
                        id="data_destinations"
                        placeholder="e.g., Warehouse, Data Lake, S3"
                        value={airflowDetails.data_destinations}
                        onChange={(e) =>
                          setAirflowDetails({
                            ...airflowDetails,
                            data_destinations: e.target.value,
                          })
                        }
                        className="w-full"
                      />
                    </div>
                  </div>

                  {/* Execution Timeout */}
                  <div className="space-y-2">
                    <Label htmlFor="execution_timeout" className="text-sm font-medium text-gray-700">
                      Execution Timeout
                    </Label>
                    <Input
                      id="execution_timeout"
                      placeholder="e.g., 3600 seconds (1 hour)"
                      value={airflowDetails.execution_timeout}
                      onChange={(e) =>
                        setAirflowDetails({
                          ...airflowDetails,
                          execution_timeout: e.target.value,
                        })
                      }
                      className="w-full"
                    />
                  </div>
              </div>
            )}

            {/* Excel Specific Fields */}
            {jobType === "Excel" && (
              <div className="space-y-6 mt-6 pt-6 border-t border-gray-200">
                {/* Input Data Sources + Transformations */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="input_data_sources" className="text-sm font-medium text-gray-700">
                      Input Data Sources
                    </Label>
                    <textarea
                      id="input_data_sources"
                      placeholder="e.g., Database query, CSV file, API endpoint"
                      value={excelDetails.input_data_sources}
                      onChange={(e) =>
                        setExcelDetails({
                          ...excelDetails,
                          input_data_sources: e.target.value,
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      rows={3}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="transformations" className="text-sm font-medium text-gray-700">
                      Transformations
                    </Label>
                    <textarea
                      id="transformations"
                      placeholder="Describe data transformations to apply"
                      value={excelDetails.transformations}
                      onChange={(e) =>
                        setExcelDetails({
                          ...excelDetails,
                          transformations: e.target.value,
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      rows={3}
                    />
                  </div>
                </div>

                {/* Filters */}
                <div className="space-y-2">
                  <Label htmlFor="filters" className="text-sm font-medium text-gray-700">
                    Filters
                  </Label>
                  <Input
                    id="filters"
                    placeholder="e.g., Region = 'US', Date >= 2024-01-01"
                    value={excelDetails.filters}
                    onChange={(e) =>
                      setExcelDetails({
                        ...excelDetails,
                        filters: e.target.value,
                      })
                    }
                    className="w-full"
                  />
                </div>

                {/* Pivot Tables */}
                <div className="flex items-center gap-3 py-2">
                  <Checkbox
                    id="pivot_tables"
                    checked={excelDetails.pivot_tables}
                    onCheckedChange={(checked) =>
                      setExcelDetails({
                        ...excelDetails,
                        pivot_tables: checked === true,
                      })
                    }
                  />
                  <Label
                    htmlFor="pivot_tables"
                    className="text-sm font-medium text-gray-700 cursor-pointer"
                  >
                    Include Pivot Tables
                  </Label>
                </div>

                {/* Formulas */}
                <div className="space-y-2">
                  <Label htmlFor="formulas" className="text-sm font-medium text-gray-700">
                    Formulas
                  </Label>
                  <textarea
                    id="formulas"
                    placeholder="e.g., SUM, AVERAGE, VLOOKUP formulas to include"
                    value={excelDetails.formulas}
                    onChange={(e) =>
                      setExcelDetails({
                        ...excelDetails,
                        formulas: e.target.value,
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                    rows={3}
                  />
                </div>

                {/* Output File Name + File Location */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="output_file_name" className="text-sm font-medium text-gray-700">
                      Output File Name *
                    </Label>
                    <Input
                      id="output_file_name"
                      placeholder="e.g., Sales_Report_2024.xlsx"
                      value={excelDetails.output_file_name}
                      onChange={(e) =>
                        setExcelDetails({
                          ...excelDetails,
                          output_file_name: e.target.value,
                        })
                      }
                      className={`w-full ${errors.output_file_name ? "border-red-500" : ""}`}
                    />
                    {errors.output_file_name && (
                      <p className="text-xs text-red-600">{errors.output_file_name}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="file_location" className="text-sm font-medium text-gray-700">
                      File Location
                    </Label>
                    <Input
                      id="file_location"
                      placeholder="e.g., /reports/sales/ or S3://bucket/path/"
                      value={excelDetails.file_location}
                      onChange={(e) =>
                        setExcelDetails({
                          ...excelDetails,
                          file_location: e.target.value,
                        })
                      }
                      className="w-full"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* PowerPoint Specific Fields */}
            {jobType === "PowerPoint" && (
              <div className="space-y-6 mt-6 pt-6 border-t border-gray-200">
                {/* Data Source + Slide Template */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="data_source" className="text-sm font-medium text-gray-700">
                      Data Source
                    </Label>
                    <Input
                      id="data_source"
                      placeholder="e.g., Analytics Dashboard, Database, API"
                      value={powerpointDetails.data_source}
                      onChange={(e) =>
                        setPowerpointDetails({
                          ...powerpointDetails,
                          data_source: e.target.value,
                        })
                      }
                      className="w-full"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="slide_template" className="text-sm font-medium text-gray-700">
                      Slide Template *
                    </Label>
                    <Select
                      value={powerpointDetails.slide_template}
                      onValueChange={(value) =>
                        setPowerpointDetails({
                          ...powerpointDetails,
                          slide_template: value,
                        })
                      }
                    >
                      <SelectTrigger id="slide_template" className={`w-full ${errors.slide_template ? "border-red-500" : ""}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="executive_summary">Executive Summary</SelectItem>
                        <SelectItem value="detailed_analysis">Detailed Analysis</SelectItem>
                        <SelectItem value="dashboard">Dashboard</SelectItem>
                        <SelectItem value="financial">Financial Report</SelectItem>
                        <SelectItem value="custom">Custom</SelectItem>
                      </SelectContent>
                    </Select>
                    {errors.slide_template && (
                      <p className="text-xs text-red-600">{errors.slide_template}</p>
                    )}
                  </div>
                </div>

                {/* Metrics to Include + Charts */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="metrics_to_include" className="text-sm font-medium text-gray-700">
                      Metrics to Include
                    </Label>
                    <textarea
                      id="metrics_to_include"
                      placeholder="e.g., Revenue, Growth %, Market Share, YoY Change"
                      value={powerpointDetails.metrics_to_include}
                      onChange={(e) =>
                        setPowerpointDetails({
                          ...powerpointDetails,
                          metrics_to_include: e.target.value,
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      rows={3}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="charts" className="text-sm font-medium text-gray-700">
                      Charts
                    </Label>
                    <textarea
                      id="charts"
                      placeholder="e.g., Line chart, Bar chart, Pie chart"
                      value={powerpointDetails.charts}
                      onChange={(e) =>
                        setPowerpointDetails({
                          ...powerpointDetails,
                          charts: e.target.value,
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      rows={3}
                    />
                  </div>
                </div>

                {/* Text Summary (Read-only) */}
                <div className="space-y-2">
                  <Label htmlFor="text_summary" className="text-sm font-medium text-gray-700">
                    Text Summary (AI-Generated)
                  </Label>
                  <div className="p-3 bg-gray-50 rounded-md border border-gray-300 text-sm text-gray-600 italic">
                    {powerpointDetails.text_summary_placeholder}
                  </div>
                  <p className="text-xs text-gray-500">
                    AI will automatically generate a text summary based on your metrics and data.
                  </p>
                </div>

                {/* Branding Theme + Output Location */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="branding_theme" className="text-sm font-medium text-gray-700">
                      Branding Theme
                    </Label>
                    <Select
                      value={powerpointDetails.branding_theme}
                      onValueChange={(value) =>
                        setPowerpointDetails({
                          ...powerpointDetails,
                          branding_theme: value,
                        })
                      }
                    >
                      <SelectTrigger id="branding_theme" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="toyota_standard">Toyota Standard</SelectItem>
                        <SelectItem value="executive">Executive</SelectItem>
                        <SelectItem value="minimal">Minimal</SelectItem>
                        <SelectItem value="vibrant">Vibrant</SelectItem>
                        <SelectItem value="modern">Modern</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="output_location" className="text-sm font-medium text-gray-700">
                      Output Location
                    </Label>
                    <Input
                      id="output_location"
                      placeholder="e.g., /presentations/ or S3://bucket/ppts/"
                      value={powerpointDetails.output_location}
                      onChange={(e) =>
                        setPowerpointDetails({
                          ...powerpointDetails,
                          output_location: e.target.value,
                        })
                      }
                      className="w-full"
                    />
                  </div>
                </div>
              </div>
            )}
            </div>
          </div>
        </div>
      </div>

      {!hideFooter && (
        <div className="flex-shrink-0 border-t border-gray-200 bg-white px-4 py-4 sm:px-6 lg:px-8 flex gap-3">
          <Button
            variant="outline"
            onClick={handleClose}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            className="flex-1 bg-[#ed0923] hover:bg-[#d10820] text-white"
          >
            Create Job
          </Button>
        </div>
      )}
    </div>
  );
}
