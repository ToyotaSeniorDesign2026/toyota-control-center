import React, { useState, ChangeEvent, FormEvent } from 'react';
import { useNavigate } from "react-router";
import { 
  Calendar, 
  Database, 
  Mail, 
  AlertCircle, 
  CheckCircle, 
  Info,
  Clock,
  FileText,
  Play
} from 'lucide-react';

interface FormData {
  jobName: string;
  description: string;
  owner: string;
  scheduleType: 'daily' | 'weekly' | 'monthly' | 'on-demand';
  scheduleDay: string;
  scheduleTime: string;
  databaseConnection: string;
  queryText: string;
  outputDestination: 'table' | 'csv' | 'email';
  outputLocation: string;
  emailRecipients: string;
  queryTimeout: string;
  dataSensitivity: 'public' | 'internal' | 'confidential';
}

interface FormErrors {
  [key: string]: string;
}

const SQLJobForm: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<FormData>({
    jobName: '',
    description: '',
    owner: '',
    scheduleType: 'daily',
    scheduleDay: '1',
    scheduleTime: '06:00',
    databaseConnection: 'production',
    queryText: '',
    outputDestination: 'table',
    outputLocation: '',
    emailRecipients: '',
    queryTimeout: '300',
    dataSensitivity: 'internal'
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [showSuccess, setShowSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isTestingQuery, setIsTestingQuery] = useState(false);

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
    if (!formData.queryText.trim()) {
      newErrors.queryText = 'SQL query is required';
    }
    if (!formData.outputLocation.trim()) {
      newErrors.outputLocation = 'Output location is required';
    }
    if (formData.scheduleType !== 'on-demand' && !formData.scheduleTime) {
      newErrors.scheduleTime = 'Schedule time is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleTestQuery = async () => {
    if (!formData.queryText.trim()) {
      setErrors(prev => ({ ...prev, queryText: 'Enter a query to test' }));
      return;
    }

    setIsTestingQuery(true);
    
    // Simulate API call to test query
    setTimeout(() => {
      setIsTestingQuery(false);
      alert('Query test successful! Returns 1,250 rows.');
    }, 1500);
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    
    // Simulate API call
    setTimeout(() => {
      setIsSubmitting(false);
      setShowSuccess(true);
      
      // Reset form after success
      setTimeout(() => {
        setShowSuccess(false);
        setFormData({
          jobName: '',
          description: '',
          owner: '',
          scheduleType: 'daily',
          scheduleDay: '1',
          scheduleTime: '06:00',
          databaseConnection: 'production',
          queryText: '',
          outputDestination: 'table',
          outputLocation: '',
          emailRecipients: '',
          queryTimeout: '300',
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
            <Database size={32} color="#EB0A1E" />
          </div>
          <h1 style={styles.title}>Create SQL Job</h1>
          <p style={styles.subtitle}>
            Schedule recurring SQL queries for data extraction and reporting
          </p>
        </div>

        {/* Success Message */}
        {showSuccess && (
          <div style={styles.successBanner}>
            <CheckCircle size={20} color="#10B981" />
            <span>Job created successfully! Redirecting to dashboard...</span>
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
                placeholder="e.g., Daily Sales Summary Report"
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
                <span>Give your job a clear, descriptive name</span>
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleInputChange}
                placeholder="What data does this query extract? Who uses it?"
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
                  ? `This job will run on the ${formData.scheduleDay}${getOrdinalSuffix(parseInt(formData.scheduleDay))} of every month at ${formData.scheduleTime}`
                  : formData.scheduleType === 'on-demand'
                  ? 'This job will only run when manually triggered'
                  : `This job will run ${formData.scheduleType} at ${formData.scheduleTime}`}
              </span>
            </div>
          </div>

          {/* Database & Query Section */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <Database size={20} color="#EB0A1E" style={{ marginRight: '8px' }} />
              Database & Query
            </h2>

            <div style={styles.formGroup}>
              <label style={styles.label}>Database Connection</label>
              <select
                name="databaseConnection"
                value={formData.databaseConnection}
                onChange={handleInputChange}
                style={styles.select}
              >
                <option value="production">Production Database</option>
                <option value="analytics">Analytics Database</option>
                <option value="reporting">Reporting Database</option>
                <option value="staging">Staging Database</option>
              </select>
              <div style={styles.helpText}>
                <Info size={14} />
                <span>Select the database where your query will run</span>
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>
                SQL Query <span style={styles.required}>*</span>
              </label>
              <textarea
                name="queryText"
                value={formData.queryText}
                onChange={handleInputChange}
                placeholder="SELECT customer_id, SUM(amount) as total_sales&#10;FROM transactions&#10;WHERE date >= CURRENT_DATE - INTERVAL '30 days'&#10;GROUP BY customer_id&#10;ORDER BY total_sales DESC"
                rows={8}
                style={{
                  ...styles.textarea,
                  ...styles.codeTextarea,
                  ...(errors.queryText ? styles.inputError : {})
                }}
              />
              {errors.queryText && (
                <div style={styles.errorMessage}>
                  <AlertCircle size={14} />
                  <span>{errors.queryText}</span>
                </div>
              )}
              <div style={styles.queryActions}>
                <button
                  type="button"
                  onClick={handleTestQuery}
                  disabled={isTestingQuery}
                  style={styles.testButton}
                >
                  <Play size={16} />
                  <span>{isTestingQuery ? 'Testing...' : 'Test Query'}</span>
                </button>
                <div style={styles.helpText}>
                  <Info size={14} />
                  <span>Test your query before scheduling</span>
                </div>
              </div>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Query Timeout (seconds)</label>
              <input
                type="number"
                name="queryTimeout"
                value={formData.queryTimeout}
                onChange={handleInputChange}
                min="30"
                max="3600"
                style={styles.input}
              />
              <div style={styles.helpText}>
                <Info size={14} />
                <span>Maximum time allowed for query execution (30-3600 seconds)</span>
              </div>
            </div>
          </div>

          {/* Output Configuration Section */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <FileText size={20} color="#EB0A1E" style={{ marginRight: '8px' }} />
              Output Configuration
            </h2>

            <div style={styles.formGroup}>
              <label style={styles.label}>Output Destination</label>
              <select
                name="outputDestination"
                value={formData.outputDestination}
                onChange={handleInputChange}
                style={styles.select}
              >
                <option value="table">Database Table</option>
                <option value="csv">CSV File</option>
                <option value="email">Email Report</option>
              </select>
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>
                Output Location <span style={styles.required}>*</span>
              </label>
              <input
                type="text"
                name="outputLocation"
                value={formData.outputLocation}
                onChange={handleInputChange}
                placeholder={
                  formData.outputDestination === 'table' 
                    ? 'e.g., analytics.daily_sales_summary'
                    : formData.outputDestination === 'csv'
                    ? 'e.g., /reports/daily_sales.csv'
                    : 'Not required for email output'
                }
                disabled={formData.outputDestination === 'email'}
                style={{
                  ...styles.input,
                  ...(errors.outputLocation ? styles.inputError : {})
                }}
              />
              {errors.outputLocation && (
                <div style={styles.errorMessage}>
                  <AlertCircle size={14} />
                  <span>{errors.outputLocation}</span>
                </div>
              )}
              <div style={styles.helpText}>
                <Info size={14} />
                <span>
                  {formData.outputDestination === 'table' 
                    ? 'Full table name including schema'
                    : formData.outputDestination === 'csv'
                    ? 'File path where CSV will be saved'
                    : 'Email recipients will receive query results'}
                </span>
              </div>
            </div>

            {formData.outputDestination === 'email' && (
              <div style={styles.formGroup}>
                <label style={styles.label}>Email Recipients</label>
                <input
                  type="text"
                  name="emailRecipients"
                  value={formData.emailRecipients}
                  onChange={handleInputChange}
                  placeholder="user1@toyota.com, user2@toyota.com"
                  style={styles.input}
                />
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
              onClick={() => navigate("/user-home")}
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
              {isSubmitting ? 'Creating Job...' : 'Create Job'}
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
  codeTextarea: {
    fontFamily: 'Monaco, Menlo, "Courier New", monospace',
    fontSize: '13px',
    lineHeight: '1.6',
    backgroundColor: '#F8F8F8',
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
  queryActions: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    marginTop: '12px',
  },
  testButton: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 16px',
    fontSize: '13px',
    fontWeight: '600',
    color: '#EB0A1E',
    backgroundColor: '#FFFFFF',
    border: '2px solid #EB0A1E',
    borderRadius: '4px',
    cursor: 'pointer',
    transition: 'all 0.2s',
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

export default SQLJobForm;
