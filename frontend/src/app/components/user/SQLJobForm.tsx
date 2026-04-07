import React, { useEffect, useState, ChangeEvent, FormEvent } from 'react';
import { useNavigate } from "react-router";
import { createJobFromForm, saveDraft, saveTemplate } from "../../lib/userDashboardStore";
import { StructuredScheduleFields } from "./StructuredScheduleFields";
import { 
  Calendar, 
  Database, 
  Mail, 
  AlertCircle, 
  CheckCircle, 
  Info,
  Clock,
  FileText,
  Filter
} from 'lucide-react';

interface FormData {
  jobName: string;
  description: string;
  owner: string;
  scheduleType: 'daily' | 'weekly' | 'monthly' | 'on-demand';
  scheduleDay: string;
  scheduleTime: string;
  weeklyDays: string[];
  startDate: string;
  stopCondition: 'never' | 'on-date' | 'after-runs';
  endDate: string;
  maxRuns: string;
  reportTemplate: string;
  dateRange: string;
  regionFilter: string;
  departmentFilter: string;
  minAmount: string;
  outputDestination: 'table' | 'csv' | 'email';
  emailRecipients: string;
  dataSensitivity: 'public' | 'internal' | 'confidential';
}

interface FormErrors {
  [key: string]: string;
}

interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  parameters: string[];
}

const reportTemplates: ReportTemplate[] = [
  {
    id: 'daily_sales',
    name: 'Daily Sales Summary',
    description: 'Total sales by region and product category',
    category: 'Sales',
    parameters: ['dateRange', 'regionFilter']
  },
  {
    id: 'customer_metrics',
    name: 'Customer Activity Report',
    description: 'Customer counts, new signups, and engagement metrics',
    category: 'Customer',
    parameters: ['dateRange', 'regionFilter']
  },
  {
    id: 'dealer_performance',
    name: 'Dealer Performance Dashboard',
    description: 'Sales, inventory, and customer satisfaction by dealer',
    category: 'Dealer',
    parameters: ['dateRange', 'regionFilter', 'minAmount']
  },
  {
    id: 'revenue_breakdown',
    name: 'Monthly Revenue Breakdown',
    description: 'Revenue by product, region, and sales channel',
    category: 'Finance',
    parameters: ['dateRange', 'departmentFilter']
  },
  {
    id: 'inventory_status',
    name: 'Inventory Status Report',
    description: 'Current stock levels, low inventory alerts, and turnover rates',
    category: 'Operations',
    parameters: ['regionFilter']
  },
  {
    id: 'loan_portfolio',
    name: 'Loan Portfolio Summary',
    description: 'Active loans, delinquency rates, and portfolio health',
    category: 'Finance',
    parameters: ['dateRange', 'minAmount']
  }
];

interface SQLTemplateFormProps {
  initialData?: Record<string, unknown>;
  aiPrompt?: string;
  embedded?: boolean;
  onCancel?: () => void;
  onDraftSaved?: () => void;
  onTemplateSaved?: () => void;
  onJobCreated?: (job: Record<string, unknown>) => void;
}

const SQLTemplateForm: React.FC<SQLTemplateFormProps> = ({
  initialData,
  aiPrompt,
  embedded = false,
  onCancel,
  onDraftSaved,
  onTemplateSaved,
  onJobCreated,
}) => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<FormData>({
    jobName: '',
    description: '',
    owner: '',
    scheduleType: 'daily',
    scheduleDay: '1',
    scheduleTime: '06:00',
    weeklyDays: ['1'],
    startDate: new Date().toISOString().slice(0, 10),
    stopCondition: 'never',
    endDate: '',
    maxRuns: '12',
    reportTemplate: '',
    dateRange: '30',
    regionFilter: 'all',
    departmentFilter: 'all',
    minAmount: '1000',
    outputDestination: 'email',
    emailRecipients: '',
    dataSensitivity: 'internal'
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [showSuccess, setShowSuccess] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAIPrefill, setShowAIPrefill] = useState(false);

  const selectedTemplate = reportTemplates.find(t => t.id === formData.reportTemplate);

  useEffect(() => {
    if (!initialData) return;
    setFormData((prev) => ({
      ...prev,
      ...initialData,
    }));
    setShowAIPrefill(true);
  }, [initialData]);

  const handleInputChange = (
    e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));

    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const handleWeeklyDayToggle = (dayValue: string) => {
    setFormData((prev) => {
      const alreadySelected = prev.weeklyDays.includes(dayValue);
      const nextDays = alreadySelected
        ? prev.weeklyDays.filter((day) => day !== dayValue)
        : [...prev.weeklyDays, dayValue].sort();

      return {
        ...prev,
        weeklyDays: nextDays.length > 0 ? nextDays : [dayValue],
        scheduleDay: (nextDays.length > 0 ? nextDays : [dayValue])[0],
      };
    });
  };

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.jobName.trim()) {
      newErrors.jobName = 'Job name is required';
    }
    if (!formData.owner.trim()) {
      newErrors.owner = 'Owner email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.owner)) {
      newErrors.owner = 'Please enter a valid email address';
    }
    if (!formData.reportTemplate) {
      newErrors.reportTemplate = 'Please select a report template';
    }
    if (formData.outputDestination === 'email' && !formData.emailRecipients.trim()) {
      newErrors.emailRecipients = 'Email recipients are required';
    }
    if (formData.scheduleType !== 'on-demand' && !formData.scheduleTime) {
      newErrors.scheduleTime = 'Schedule time is required';
    }
    if (formData.stopCondition === 'on-date' && !formData.endDate) {
      newErrors.endDate = 'End date is required';
    }
    if (formData.stopCondition === 'after-runs' && !formData.maxRuns.trim()) {
      newErrors.maxRuns = 'Maximum runs is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    
    setTimeout(() => {
      const createdJob = createJobFromForm("SQL", formData as unknown as Record<string, unknown>);
      setIsSubmitting(false);
      setSuccessMessage("Report submitted for approval. Opening Pending Promotions...");
      setShowSuccess(true);
      setTimeout(() => {
        if (embedded) {
          onJobCreated?.(createdJob as unknown as Record<string, unknown>);
        } else {
          navigate("/promotions");
        }
      }, 900);
    }, 1500);
  };

  const handleSaveDraft = () => {
    saveDraft("SQL", formData as unknown as Record<string, unknown>);
    if (embedded) {
      onDraftSaved?.();
    } else {
      navigate("/forms");
    }
  };

  const handleSaveTemplate = () => {
    saveTemplate("SQL", formData as unknown as Record<string, unknown>);
    if (embedded) {
      onTemplateSaved?.();
    } else {
      navigate("/forms/saved-templates");
    }
  };

  const needsParameter = (param: string): boolean => {
    return selectedTemplate?.parameters.includes(param) || false;
  };

  return (
    <div style={{ ...styles.container, minHeight: embedded ? 'auto' : '100vh', padding: embedded ? '0' : '40px 20px', backgroundColor: embedded ? 'transparent' : '#F5F5F5' }}>
      <div style={styles.formWrapper}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.iconWrapper}>
            <Database size={32} color="#EB0A1E" />
          </div>
          <h1 style={styles.title}>Create Report Job</h1>
          <p style={styles.subtitle}>
            Schedule automated reports using pre-built templates
          </p>
        </div>

        {/* Success Message */}
        {showSuccess && (
          <div style={styles.successBanner}>
            <CheckCircle size={20} color="#10B981" />
            <span>{successMessage}</span>
          </div>
        )}

        {showAIPrefill && (
          <div style={styles.infoBox}>
            <Info size={16} color="#EB0A1E" />
            <span>
              AI prefilled this form{aiPrompt ? ` from prompt: "${aiPrompt}"` : ""}. Review and adjust before submit.
            </span>
          </div>
        )}

        {showAIPrefill && (
          <div style={styles.infoBox}>
            <Info size={16} color="#EB0A1E" />
            <span>
              AI prefilled this form{aiPrompt ? ` from prompt: "${aiPrompt}"` : ""}. Review and adjust before submit.
            </span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={styles.form}>
          {/* Basic Information Section */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>Basic Information</h2>
            
            <div style={styles.formGroup}>
              <label style={styles.label}>
                Job Name <span style={styles.required}>*</span>
              </label>
              <input
                type="text"
                name="jobName"
                value={formData.jobName}
                onChange={handleInputChange}
                placeholder="e.g., Weekly Sales Report for Management"
                style={{
                  ...styles.input,
                  ...(errors.jobName ? styles.inputError : {})
                }}
              />
              {errors.jobName && (
                <div style={styles.errorMessage}>
                  <AlertCircle size={14} />
                  <span>{errors.jobName}</span>
                </div>
              )}
              <div style={styles.helpText}>
                <Info size={14} />
                <span>Give your report a clear, descriptive name</span>
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleInputChange}
                placeholder="What is this report used for? Who needs it?"
                rows={3}
                style={styles.textarea}
              />
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>
                Owner Email <span style={styles.required}>*</span>
              </label>
              <input
                type="email"
                name="owner"
                value={formData.owner}
                onChange={handleInputChange}
                placeholder="your.email@toyota.com"
                style={{
                  ...styles.input,
                  ...(errors.owner ? styles.inputError : {})
                }}
              />
              {errors.owner && (
                <div style={styles.errorMessage}>
                  <AlertCircle size={14} />
                  <span>{errors.owner}</span>
                </div>
              )}
            </div>
          </div>

          {/* Report Template Section */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <FileText size={20} color="#EB0A1E" style={{ marginRight: '8px' }} />
              Select Report Template
            </h2>

            <div style={styles.formGroup}>
              <label style={styles.label}>
                Report Type <span style={styles.required}>*</span>
              </label>
              <select
                name="reportTemplate"
                value={formData.reportTemplate}
                onChange={handleInputChange}
                style={{
                  ...styles.select,
                  ...(errors.reportTemplate ? styles.inputError : {})
                }}
              >
                <option value="">-- Choose a report template --</option>
                {reportTemplates.map(template => (
                  <option key={template.id} value={template.id}>
                    {template.name} - {template.description}
                  </option>
                ))}
              </select>
              {errors.reportTemplate && (
                <div style={styles.errorMessage}>
                  <AlertCircle size={14} />
                  <span>{errors.reportTemplate}</span>
                </div>
              )}
              <div style={styles.helpText}>
                <Info size={14} />
                <span>Choose a pre-built report template that matches your needs</span>
              </div>
            </div>

            {selectedTemplate && (
              <div style={styles.templateInfo}>
                <div style={styles.templateInfoHeader}>
                  <CheckCircle size={18} color="#10B981" />
                  <strong>Template Selected: {selectedTemplate.name}</strong>
                </div>
                <p style={styles.templateDescription}>{selectedTemplate.description}</p>
                <p style={styles.templateCategory}>Category: {selectedTemplate.category}</p>
              </div>
            )}
          </div>

          {/* Report Filters Section */}
          {selectedTemplate && (
            <div style={styles.section}>
              <h2 style={styles.sectionTitle}>
                <Filter size={20} color="#EB0A1E" style={{ marginRight: '8px' }} />
                Customize Report Filters
              </h2>

              {needsParameter('dateRange') && (
                <div style={styles.formGroup}>
                  <label style={styles.label}>Date Range</label>
                  <select
                    name="dateRange"
                    value={formData.dateRange}
                    onChange={handleInputChange}
                    style={styles.select}
                  >
                    <option value="7">Last 7 days</option>
                    <option value="30">Last 30 days</option>
                    <option value="90">Last 90 days</option>
                    <option value="365">Last year</option>
                    <option value="ytd">Year to date</option>
                  </select>
                  <div style={styles.helpText}>
                    <Info size={14} />
                    <span>Select the time period for your report</span>
                  </div>
                </div>
              )}

              {needsParameter('regionFilter') && (
                <div style={styles.formGroup}>
                  <label style={styles.label}>Region</label>
                  <select
                    name="regionFilter"
                    value={formData.regionFilter}
                    onChange={handleInputChange}
                    style={styles.select}
                  >
                    <option value="all">All Regions</option>
                    <option value="northeast">Northeast</option>
                    <option value="southeast">Southeast</option>
                    <option value="midwest">Midwest</option>
                    <option value="southwest">Southwest</option>
                    <option value="west">West</option>
                  </select>
                  <div style={styles.helpText}>
                    <Info size={14} />
                    <span>Filter by geographic region</span>
                  </div>
                </div>
              )}

              {needsParameter('departmentFilter') && (
                <div style={styles.formGroup}>
                  <label style={styles.label}>Department</label>
                  <select
                    name="departmentFilter"
                    value={formData.departmentFilter}
                    onChange={handleInputChange}
                    style={styles.select}
                  >
                    <option value="all">All Departments</option>
                    <option value="sales">Sales</option>
                    <option value="finance">Finance</option>
                    <option value="operations">Operations</option>
                    <option value="marketing">Marketing</option>
                  </select>
                  <div style={styles.helpText}>
                    <Info size={14} />
                    <span>Filter by department</span>
                  </div>
                </div>
              )}

              {needsParameter('minAmount') && (
                <div style={styles.formGroup}>
                  <label style={styles.label}>Minimum Amount ($)</label>
                  <input
                    type="number"
                    name="minAmount"
                    value={formData.minAmount}
                    onChange={handleInputChange}
                    min="0"
                    step="100"
                    style={styles.input}
                  />
                  <div style={styles.helpText}>
                    <Info size={14} />
                    <span>Only include transactions above this amount</span>
                  </div>
                </div>
              )}
            </div>
          )}

          <StructuredScheduleFields
            scheduleType={formData.scheduleType}
            scheduleDay={formData.scheduleDay}
            scheduleTime={formData.scheduleTime}
            weeklyDays={formData.weeklyDays}
            startDate={formData.startDate}
            stopCondition={formData.stopCondition}
            endDate={formData.endDate}
            maxRuns={formData.maxRuns}
            summaryPrefix="This report"
            scheduleTimeError={errors.scheduleTime}
            onFieldChange={(field, value) =>
              setFormData((prev) => ({
                ...prev,
                [field]: value,
              }))
            }
            onWeeklyDayToggle={handleWeeklyDayToggle}
          />

          {/* Delivery Section */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <Mail size={20} color="#EB0A1E" style={{ marginRight: '8px' }} />
              Delivery & Notifications
            </h2>

            <div style={styles.formGroup}>
              <label style={styles.label}>Delivery Method</label>
              <select
                name="outputDestination"
                value={formData.outputDestination}
                onChange={handleInputChange}
                style={styles.select}
              >
                <option value="email">Email Report</option>
                <option value="csv">Save as CSV File</option>
                <option value="table">Save to Database</option>
              </select>
            </div>

            {formData.outputDestination === 'email' && (
              <div style={styles.formGroup}>
                <label style={styles.label}>
                  Email Recipients <span style={styles.required}>*</span>
                </label>
                <input
                  type="text"
                  name="emailRecipients"
                  value={formData.emailRecipients}
                  onChange={handleInputChange}
                  placeholder="manager@toyota.com, team@toyota.com"
                  style={{
                    ...styles.input,
                    ...(errors.emailRecipients ? styles.inputError : {})
                  }}
                />
                {errors.emailRecipients && (
                  <div style={styles.errorMessage}>
                    <AlertCircle size={14} />
                    <span>{errors.emailRecipients}</span>
                  </div>
                )}
                <div style={styles.helpText}>
                  <Info size={14} />
                  <span>Separate multiple emails with commas</span>
                </div>
              </div>
            )}

            <div style={styles.formGroup}>
              <label style={styles.label}>Data Sensitivity</label>
              <select
                name="dataSensitivity"
                value={formData.dataSensitivity}
                onChange={handleInputChange}
                style={styles.select}
              >
                <option value="public">Public - Can be shared externally</option>
                <option value="internal">Internal - TFS employees only</option>
                <option value="confidential">Confidential - Restricted access</option>
              </select>
            </div>
          </div>

          {/* Submit Button */}
          <div style={styles.buttonGroup}>
            <button
              type="button"
              onClick={() => (embedded ? onCancel?.() : navigate("/user-home"))}
              style={styles.cancelButton}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveDraft}
              style={styles.secondaryButton}
            >
              Save Draft
            </button>
            <button
              type="button"
              onClick={handleSaveTemplate}
              style={styles.secondaryButton}
            >
              Save as Template
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                ...styles.submitButton,
                ...(isSubmitting ? styles.submitButtonDisabled : {})
              }}
            >
              {isSubmitting ? 'Submitting...' : 'Submit for Approval'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// Helper function
const getOrdinalSuffix = (day: number): string => {
  if (day > 3 && day < 21) return 'th';
  switch (day % 10) {
    case 1: return 'st';
    case 2: return 'nd';
    case 3: return 'rd';
    default: return 'th';
  }
};

// Toyota-branded styles (same as before)
const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#F5F5F5',
    padding: '40px 20px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  formWrapper: {
    maxWidth: '800px',
    margin: '0 auto',
    backgroundColor: '#FFFFFF',
    borderRadius: '8px',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
    overflow: 'hidden',
  },
  header: {
    background: 'linear-gradient(135deg, #EB0A1E 0%, #C70917 100%)',
    color: '#FFFFFF',
    padding: '40px',
    textAlign: 'center' as const,
  },
  iconWrapper: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '64px',
    height: '64px',
    backgroundColor: '#FFFFFF',
    borderRadius: '50%',
    marginBottom: '16px',
  },
  title: {
    fontSize: '28px',
    fontWeight: 'bold',
    margin: '0 0 8px 0',
  },
  subtitle: {
    fontSize: '16px',
    opacity: 0.9,
    margin: 0,
  },
  successBanner: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '16px',
    backgroundColor: '#D1FAE5',
    color: '#065F46',
    borderLeft: '4px solid #10B981',
    margin: '20px 40px',
    borderRadius: '4px',
  },
  form: {
    padding: '40px',
  },
  section: {
    marginBottom: '32px',
    paddingBottom: '32px',
    borderBottom: '1px solid #E5E5E5',
  },
  sectionTitle: {
    fontSize: '20px',
    fontWeight: 'bold',
    color: '#000000',
    marginBottom: '20px',
    display: 'flex',
    alignItems: 'center',
  },
  formGroup: {
    marginBottom: '20px',
  },
  formRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
  },
  label: {
    display: 'block',
    fontSize: '14px',
    fontWeight: '600',
    color: '#333333',
    marginBottom: '8px',
  },
  required: {
    color: '#EB0A1E',
  },
  input: {
    width: '100%',
    padding: '12px',
    fontSize: '14px',
    border: '2px solid #DDDDDD',
    borderRadius: '4px',
    outline: 'none',
    transition: 'border-color 0.2s',
    boxSizing: 'border-box' as const,
  },
  inputError: {
    borderColor: '#EB0A1E',
  },
  textarea: {
    width: '100%',
    padding: '12px',
    fontSize: '14px',
    border: '2px solid #DDDDDD',
    borderRadius: '4px',
    outline: 'none',
    resize: 'vertical' as const,
    fontFamily: 'inherit',
    boxSizing: 'border-box' as const,
  },
  select: {
    width: '100%',
    padding: '12px',
    fontSize: '14px',
    border: '2px solid #DDDDDD',
    borderRadius: '4px',
    outline: 'none',
    backgroundColor: '#FFFFFF',
    cursor: 'pointer',
    boxSizing: 'border-box' as const,
  },
  helpText: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '12px',
    color: '#777777',
    marginTop: '6px',
  },
  errorMessage: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '12px',
    color: '#EB0A1E',
    marginTop: '6px',
  },
  infoBox: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '10px',
    padding: '12px',
    backgroundColor: '#FFF5F5',
    border: '1px solid #FFDDDD',
    borderRadius: '4px',
    fontSize: '13px',
    color: '#666666',
    marginTop: '12px',
  },
  templateInfo: {
    padding: '16px',
    backgroundColor: '#F0FDF4',
    border: '1px solid #86EFAC',
    borderRadius: '6px',
    marginTop: '12px',
  },
  templateInfoHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '14px',
    fontWeight: 'bold',
    color: '#166534',
    marginBottom: '8px',
  },
  templateDescription: {
    fontSize: '13px',
    color: '#166534',
    margin: '0 0 4px 0',
  },
  templateCategory: {
    fontSize: '12px',
    color: '#15803D',
    margin: 0,
    fontStyle: 'italic' as const,
  },
  buttonGroup: {
    display: 'flex',
    flexWrap: 'wrap',
    justifyContent: 'flex-end',
    gap: '12px',
    marginTop: '32px',
    paddingTop: '32px',
    borderTop: '1px solid #E5E5E5',
  },
  cancelButton: {
    padding: '12px 24px',
    fontSize: '14px',
    fontWeight: '600',
    color: '#666666',
    backgroundColor: '#FFFFFF',
    border: '2px solid #DDDDDD',
    borderRadius: '4px',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  secondaryButton: {
    padding: '12px 24px',
    fontSize: '14px',
    fontWeight: '600',
    color: '#EB0A1E',
    backgroundColor: '#FFF5F5',
    border: '1px solid #F6B5BC',
    borderRadius: '4px',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  submitButton: {
    padding: '12px 32px',
    fontSize: '14px',
    fontWeight: '600',
    color: '#FFFFFF',
    backgroundColor: '#EB0A1E',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  submitButtonDisabled: {
    opacity: 0.6,
    cursor: 'not-allowed',
  },
};

export default SQLTemplateForm;
