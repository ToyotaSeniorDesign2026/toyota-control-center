import React, { useEffect, useState, ChangeEvent, FormEvent } from 'react';
import { useNavigate } from "react-router";
import { 
  Calendar, 
  Upload, 
  Mail, 
  AlertCircle, 
  CheckCircle, 
  Info,
  Clock,
  Presentation,
  Image,
  BarChart3
} from 'lucide-react';

interface FormData {
  jobName: string;
  description: string;
  owner: string;
  scheduleType: 'daily' | 'weekly' | 'monthly' | 'on-demand';
  scheduleDay: string;
  scheduleTime: string;
  templateFile: File | null;
  presentationType: string;
  dataSource: string;
  includeTables: boolean;
  includeCharts: boolean;
  includeImages: boolean;
  outputFormat: 'pptx' | 'pdf';
  emailRecipients: string;
  dataSensitivity: 'public' | 'internal' | 'confidential';
}

interface FormErrors {
  [key: string]: string;
}

interface PresentationTemplate {
  id: string;
  name: string;
  description: string;
  slides: number;
}

const presentationTemplates: PresentationTemplate[] = [
  {
    id: 'executive_dashboard',
    name: 'Executive Dashboard',
    description: 'High-level KPIs, trends, and key metrics for leadership',
    slides: 8
  },
  {
    id: 'monthly_review',
    name: 'Monthly Business Review',
    description: 'Monthly performance summary with department breakdowns',
    slides: 12
  },
  {
    id: 'quarterly_board',
    name: 'Quarterly Board Deck',
    description: 'Comprehensive quarterly results for board meetings',
    slides: 15
  },
  {
    id: 'sales_pipeline',
    name: 'Sales Pipeline Report',
    description: 'Current opportunities, win rates, and forecast',
    slides: 10
  },
  {
    id: 'customer_insights',
    name: 'Customer Insights',
    description: 'Customer behavior, satisfaction scores, and trends',
    slides: 8
  },
  {
    id: 'financial_summary',
    name: 'Financial Summary',
    description: 'Revenue, expenses, profit margins, and projections',
    slides: 10
  }
];

interface PowerPointFormProps {
  initialData?: Record<string, unknown>;
  aiPrompt?: string;
}

const PowerPointForm: React.FC<PowerPointFormProps> = ({ initialData, aiPrompt }) => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<FormData>({
    jobName: '',
    description: '',
    owner: '',
    scheduleType: 'monthly',
    scheduleDay: '1',
    scheduleTime: '08:00',
    templateFile: null,
    presentationType: '',
    dataSource: 'sales_database',
    includeTables: true,
    includeCharts: true,
    includeImages: false,
    outputFormat: 'pptx',
    emailRecipients: '',
    dataSensitivity: 'internal'
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [showSuccess, setShowSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAIPrefill, setShowAIPrefill] = useState(false);

  const selectedTemplate = presentationTemplates.find(t => t.id === formData.presentationType);

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
    const { name, value, type } = e.target;
    const checked = (e.target as HTMLInputElement).checked;
    
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));

    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setFormData(prev => ({ ...prev, templateFile: file }));
    if (errors.templateFile) {
      setErrors(prev => ({ ...prev, templateFile: '' }));
    }
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
    if (!formData.templateFile && !formData.presentationType) {
      newErrors.templateFile = 'Please upload a template or select a presentation type';
    }
    if (formData.scheduleType !== 'on-demand' && !formData.scheduleTime) {
      newErrors.scheduleTime = 'Schedule time is required';
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
      setIsSubmitting(false);
      setShowSuccess(true);
      
      setTimeout(() => {
        setShowSuccess(false);
        setFormData({
          jobName: '',
          description: '',
          owner: '',
          scheduleType: 'monthly',
          scheduleDay: '1',
          scheduleTime: '08:00',
          templateFile: null,
          presentationType: '',
          dataSource: 'sales_database',
          includeTables: true,
          includeCharts: true,
          includeImages: false,
          outputFormat: 'pptx',
          emailRecipients: '',
          dataSensitivity: 'internal'
        });
      }, 3000);
    }, 1500);
  };

  return (
    <div style={styles.container}>
      <div style={styles.formWrapper}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.iconWrapper}>
            <Presentation size={32} color="#EB0A1E" />
          </div>
          <h1 style={styles.title}>Create PowerPoint Job</h1>
          <p style={styles.subtitle}>
            Automate presentation generation from your data
          </p>
        </div>

        {/* Success Message */}
        {showSuccess && (
          <div style={styles.successBanner}>
            <CheckCircle size={20} color="#10B981" />
            <span>Job created successfully! Redirecting to dashboard...</span>
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
                placeholder="e.g., Monthly Executive Dashboard"
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
                <span>Give your presentation job a clear, descriptive name</span>
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleInputChange}
                placeholder="What is this presentation for? Who receives it?"
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

          {/* Template Selection Section */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <Presentation size={20} color="#EB0A1E" style={{ marginRight: '8px' }} />
              Presentation Template
            </h2>

            <div style={styles.formGroup}>
              <label style={styles.label}>Choose Template Type</label>
              <select
                name="presentationType"
                value={formData.presentationType}
                onChange={handleInputChange}
                style={styles.select}
              >
                <option value="">-- Use pre-built template --</option>
                {presentationTemplates.map(template => (
                  <option key={template.id} value={template.id}>
                    {template.name} ({template.slides} slides)
                  </option>
                ))}
              </select>
              <div style={styles.helpText}>
                <Info size={14} />
                <span>Select a pre-built template or upload your own below</span>
              </div>
            </div>

            {selectedTemplate && (
              <div style={styles.templateInfo}>
                <div style={styles.templateInfoHeader}>
                  <CheckCircle size={18} color="#10B981" />
                  <strong>{selectedTemplate.name}</strong>
                </div>
                <p style={styles.templateDescription}>{selectedTemplate.description}</p>
                <p style={styles.templateSlides}>Slides: {selectedTemplate.slides}</p>
              </div>
            )}

            <div style={styles.divider}>
              <span style={styles.dividerText}>OR</span>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Upload Custom Template</label>
              <div style={styles.fileUpload}>
                <input
                  type="file"
                  accept=".pptx"
                  onChange={handleFileChange}
                  style={styles.fileInput}
                  id="fileUpload"
                />
                <label htmlFor="fileUpload" style={styles.fileLabel}>
                  <Upload size={20} />
                  <span>
                    {formData.templateFile 
                      ? formData.templateFile.name 
                      : 'Choose PowerPoint file or drag here'}
                  </span>
                </label>
              </div>
              {errors.templateFile && (
                <div style={styles.errorMessage}>
                  <AlertCircle size={14} />
                  <span>{errors.templateFile}</span>
                </div>
              )}
              <div style={styles.helpText}>
                <Info size={14} />
                <span>Upload your branded PowerPoint template with placeholders</span>
              </div>
            </div>
          </div>

          {/* Data Configuration Section */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <BarChart3 size={20} color="#EB0A1E" style={{ marginRight: '8px' }} />
              Data Configuration
            </h2>

            <div style={styles.formGroup}>
              <label style={styles.label}>Data Source</label>
              <select
                name="dataSource"
                value={formData.dataSource}
                onChange={handleInputChange}
                style={styles.select}
              >
                <option value="sales_database">Sales Database</option>
                <option value="analytics_database">Analytics Database</option>
                <option value="financial_database">Financial Database</option>
                <option value="customer_database">Customer Database</option>
                <option value="excel_file">Excel File</option>
              </select>
              <div style={styles.helpText}>
                <Info size={14} />
                <span>Select where your data comes from</span>
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Include in Presentation</label>
              
              <div style={styles.checkboxGroup}>
                <label style={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    name="includeTables"
                    checked={formData.includeTables}
                    onChange={handleInputChange}
                    style={styles.checkbox}
                  />
                  <span>Data Tables</span>
                </label>
                <div style={styles.checkboxHelpText}>
                  Display data in formatted tables on slides
                </div>
              </div>

              <div style={styles.checkboxGroup}>
                <label style={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    name="includeCharts"
                    checked={formData.includeCharts}
                    onChange={handleInputChange}
                    style={styles.checkbox}
                  />
                  <span>Charts & Graphs</span>
                </label>
                <div style={styles.checkboxHelpText}>
                  Generate visualizations from your data
                </div>
              </div>

              <div style={styles.checkboxGroup}>
                <label style={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    name="includeImages"
                    checked={formData.includeImages}
                    onChange={handleInputChange}
                    style={styles.checkbox}
                  />
                  <span>Dynamic Images</span>
                </label>
                <div style={styles.checkboxHelpText}>
                  Include product images, logos, or photos
                </div>
              </div>
            </div>
          </div>

          {/* Schedule Section */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <Clock size={20} color="#EB0A1E" style={{ marginRight: '8px' }} />
              Schedule
            </h2>

            <div style={styles.formGroup}>
              <label style={styles.label}>Run Frequency</label>
              <select
                name="scheduleType"
                value={formData.scheduleType}
                onChange={handleInputChange}
                style={styles.select}
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="on-demand">On-Demand Only</option>
              </select>
            </div>

            {formData.scheduleType !== 'on-demand' && (
              <div style={styles.formRow}>
                {formData.scheduleType === 'monthly' && (
                  <div style={styles.formGroup}>
                    <label style={styles.label}>Day of Month</label>
                    <select
                      name="scheduleDay"
                      value={formData.scheduleDay}
                      onChange={handleInputChange}
                      style={styles.select}
                    >
                      {Array.from({ length: 28 }, (_, i) => i + 1).map(day => (
                        <option key={day} value={day}>{day}</option>
                      ))}
                    </select>
                  </div>
                )}

                <div style={styles.formGroup}>
                  <label style={styles.label}>Time</label>
                  <input
                    type="time"
                    name="scheduleTime"
                    value={formData.scheduleTime}
                    onChange={handleInputChange}
                    style={styles.input}
                  />
                </div>
              </div>
            )}

            <div style={styles.infoBox}>
              <Info size={16} color="#EB0A1E" />
              <span>
                {formData.scheduleType === 'monthly' 
                  ? `This presentation will be generated on the ${formData.scheduleDay}${getOrdinalSuffix(parseInt(formData.scheduleDay))} of every month at ${formData.scheduleTime}`
                  : formData.scheduleType === 'on-demand'
                  ? 'This presentation will only be generated when you manually trigger it'
                  : `This presentation will be generated ${formData.scheduleType} at ${formData.scheduleTime}`}
              </span>
            </div>
          </div>

          {/* Output & Delivery Section */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <Mail size={20} color="#EB0A1E" style={{ marginRight: '8px' }} />
              Output & Delivery
            </h2>

            <div style={styles.formGroup}>
              <label style={styles.label}>Output Format</label>
              <select
                name="outputFormat"
                value={formData.outputFormat}
                onChange={handleInputChange}
                style={styles.select}
              >
                <option value="pptx">PowerPoint (.pptx)</option>
                <option value="pdf">PDF (.pdf)</option>
              </select>
              <div style={styles.helpText}>
                <Info size={14} />
                <span>PDF is read-only, PowerPoint can be edited</span>
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Email Recipients</label>
              <input
                type="text"
                name="emailRecipients"
                value={formData.emailRecipients}
                onChange={handleInputChange}
                placeholder="executive@toyota.com, team@toyota.com"
                style={styles.input}
              />
              <div style={styles.helpText}>
                <Info size={14} />
                <span>Separate multiple emails with commas</span>
              </div>
            </div>

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
              onClick={() => navigate("/forms")}
              style={styles.cancelButton}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                ...styles.submitButton,
                ...(isSubmitting ? styles.submitButtonDisabled : {})
              }}
            >
              {isSubmitting ? 'Creating Job...' : 'Create Presentation Job'}
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

// Toyota-branded styles
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
  checkbox: {
    width: '18px',
    height: '18px',
    marginRight: '8px',
    cursor: 'pointer',
    accentColor: '#EB0A1E',
  },
  checkboxLabel: {
    display: 'flex',
    alignItems: 'center',
    fontSize: '14px',
    fontWeight: '600',
    color: '#333333',
    cursor: 'pointer',
  },
  checkboxGroup: {
    marginBottom: '16px',
  },
  checkboxHelpText: {
    fontSize: '12px',
    color: '#777777',
    marginLeft: '26px',
    marginTop: '4px',
  },
  fileUpload: {
    position: 'relative' as const,
  },
  fileInput: {
    position: 'absolute' as const,
    width: '1px',
    height: '1px',
    opacity: 0,
    overflow: 'hidden',
  },
  fileLabel: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '12px',
    padding: '20px',
    border: '2px dashed #DDDDDD',
    borderRadius: '4px',
    backgroundColor: '#F9F9F9',
    cursor: 'pointer',
    transition: 'all 0.2s',
    fontSize: '14px',
    color: '#666666',
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
    marginBottom: '16px',
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
  templateSlides: {
    fontSize: '12px',
    color: '#15803D',
    margin: 0,
    fontStyle: 'italic' as const,
  },
  divider: {
    display: 'flex',
    alignItems: 'center',
    margin: '24px 0',
  },
  dividerText: {
    padding: '0 16px',
    fontSize: '12px',
    fontWeight: '600',
    color: '#999999',
    backgroundColor: '#FFFFFF',
    position: 'relative' as const,
    zIndex: 1,
  },
  buttonGroup: {
    display: 'flex',
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

export default PowerPointForm;
