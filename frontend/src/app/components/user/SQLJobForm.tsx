import React, { useEffect, useState, ChangeEvent, FormEvent } from 'react';
import { useNavigate } from "react-router";
import { createJob, createJobRun, type JobCreatePayload, type RunCreatePayload } from "../../lib/controlCenterApi";
import { StructuredScheduleFields } from "./StructuredScheduleFields";
import {
  Database,
  AlertCircle,
  CheckCircle,
  Info,
  Play,
  Eye,
  EyeOff,
  Code,
  Server,
} from 'lucide-react';

interface FormData {
  jobName: string;
  description: string;
  query: string;
  db_driver: 'postgresql' | 'sqlite' | 'snowflake';
  database: string;
  host: string;
  port: string;
  username: string;
  password: string;
  timezone: string;
  environment: 'dev' | 'semi-prod' | 'prod';
  dataSensitivity: 'low' | 'internal' | 'confidential';
  scheduleType: 'on-demand' | 'daily' | 'weekly' | 'monthly';
  scheduleDay: string;
  scheduleTime: string;
  weeklyDays: string[];
  startDate: string;
  stopCondition: 'never' | 'on-date' | 'after-runs';
  endDate: string;
  maxRuns: string;
}

interface FormErrors {
  [key: string]: string;
}

interface SQLTemplateFormProps {
  initialData?: Record<string, unknown>;
  aiPrompt?: string;
  embedded?: boolean;
  onCancel?: () => void;
  onDraftSaved?: () => void;
  onTemplateSaved?: () => void;
  onJobCreated?: (job: Record<string, unknown>) => void;
}

function buildCronExpression(formData: FormData): string {
  if (formData.scheduleType === 'on-demand') return '';
  const parts = formData.scheduleTime.split(':');
  const hour = parseInt(parts[0] ?? '9', 10);
  const minute = parseInt(parts[1] ?? '0', 10);
  if (formData.scheduleType === 'daily') {
    return `${minute} ${hour} * * *`;
  }
  if (formData.scheduleType === 'weekly') {
    const days = formData.weeklyDays.length > 0 ? formData.weeklyDays.join(',') : '1';
    return `${minute} ${hour} * * ${days}`;
  }
  if (formData.scheduleType === 'monthly') {
    return `${minute} ${hour} ${formData.scheduleDay || '1'} * *`;
  }
  return '';
}

const SQLTemplateForm: React.FC<SQLTemplateFormProps> = ({
  initialData,
  aiPrompt,
  embedded = false,
  onCancel,
  onJobCreated,
}) => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<FormData>({
    jobName: '',
    description: '',
    query: '',
    db_driver: 'postgresql',
    database: '',
    host: '',
    port: '5432',
    username: '',
    password: '',
    timezone: 'UTC',
    environment: 'dev',
    dataSensitivity: 'internal',
    scheduleType: 'on-demand',
    scheduleDay: '1',
    scheduleTime: '09:00',
    weeklyDays: ['1'],
    startDate: new Date().toISOString().slice(0, 10),
    stopCondition: 'never',
    endDate: '',
    maxRuns: '12',
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [showSuccess, setShowSuccess] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAIPrefill, setShowAIPrefill] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (!initialData) return;
    setFormData((prev) => ({ ...prev, ...initialData }));
    setShowAIPrefill(true);
  }, [initialData]);

  const handleInputChange = (
    e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }));
    }
  };

  const handleWeeklyDayToggle = (dayValue: string) => {
    setFormData((prev) => {
      const alreadySelected = prev.weeklyDays.includes(dayValue);
      const nextDays = alreadySelected
        ? prev.weeklyDays.filter((d) => d !== dayValue)
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
    if (!formData.query.trim()) {
      newErrors.query = 'SQL query is required';
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

  const getAuthToken = () =>
    typeof window !== 'undefined'
      ? (window.localStorage.getItem('control-center-auth-token') ?? 'u_analyst')
      : 'u_analyst';

  const buildJobPayload = (): JobCreatePayload => {
    const schedule = buildCronExpression(formData);
    return {
      name: formData.jobName.trim(),
      kind: 'runtime',
      type: 'sql',
      connector: 'sql-mcp',
      environment: formData.environment,
      data_sensitivity: formData.dataSensitivity,
      tags: [],
      config: {
        query: formData.query.trim(),
        db_driver: formData.db_driver,
        ...(formData.database.trim() ? { database: formData.database.trim() } : {}),
        ...(schedule ? { schedule } : {}),
        ...(schedule ? { timezone: formData.timezone || 'UTC' } : {}),
      },
    };
  };

  const buildRunPayload = (): RunCreatePayload => ({
    action: 'run',
    target_environment: formData.environment,
    params: {
      query: formData.query.trim(),
      ...(formData.host.trim() ? { host: formData.host.trim() } : {}),
      ...(formData.port.trim() && formData.port !== '5432'
        ? { port: parseInt(formData.port, 10) }
        : {}),
      ...(formData.username.trim() ? { username: formData.username.trim() } : {}),
      ...(formData.password ? { password: formData.password } : {}),
    },
    mcp_config: {
      server_names: ['sql-mcp'],
      allow_auto_selection: false,
    },
  });

  const handleSubmit = async (e: FormEvent<HTMLFormElement>, runAfter = false) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsSubmitting(true);
    setSubmitError('');
    try {
      const token = getAuthToken();
      const job = await createJob(buildJobPayload(), token);

      if (runAfter) {
        await createJobRun(job.id, buildRunPayload(), token);
        setSuccessMessage(`Job "${job.name}" created and run started!`);
      } else {
        setSuccessMessage(`Job "${job.name}" created successfully!`);
      }

      setShowSuccess(true);
      setTimeout(() => {
        if (embedded) {
          onJobCreated?.(job as unknown as Record<string, unknown>);
        } else {
          navigate('/user-home');
        }
      }, 1500);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to create job. Check your connection and try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ ...styles.container, minHeight: embedded ? 'auto' : '100vh', padding: embedded ? '0' : '40px 20px', backgroundColor: embedded ? 'transparent' : '#F5F5F5' }}>
      <div style={styles.formWrapper}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.iconWrapper}>
            <Database size={32} color="#EB0A1E" />
          </div>
          <h1 style={styles.title}>Create SQL Job</h1>
          <p style={styles.subtitle}>
            Define and schedule a SQL query job against your database
          </p>
        </div>

        {showSuccess && (
          <div style={styles.successBanner}>
            <CheckCircle size={20} color="#10B981" />
            <span>{successMessage}</span>
          </div>
        )}

        {submitError && (
          <div style={styles.errorBanner}>
            <AlertCircle size={20} color="#EB0A1E" />
            <span>{submitError}</span>
          </div>
        )}

        {showAIPrefill && (
          <div style={styles.infoBox}>
            <Info size={16} color="#EB0A1E" />
            <span>
              AI prefilled this form{aiPrompt ? ` from prompt: "${aiPrompt}"` : ''}. Review and adjust before submit.
            </span>
          </div>
        )}

        <form onSubmit={(e) => handleSubmit(e, false)} style={styles.form}>
          {/* Basic Information */}
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
                placeholder="e.g., Daily Active Users Report"
                style={{ ...styles.input, ...(errors.jobName ? styles.inputError : {}) }}
              />
              {errors.jobName && (
                <div style={styles.errorMessage}><AlertCircle size={14} /><span>{errors.jobName}</span></div>
              )}
            </div>

            <div style={styles.formGroup}>
              <label style={styles.label}>Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleInputChange}
                placeholder="What does this query do? Who uses it?"
                rows={2}
                style={styles.textarea}
              />
            </div>

            <div style={styles.formRow}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Environment</label>
                <select name="environment" value={formData.environment} onChange={handleInputChange} style={styles.select}>
                  <option value="dev">Development</option>
                  <option value="semi-prod">Staging</option>
                  <option value="prod">Production</option>
                </select>
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Data Sensitivity</label>
                <select name="dataSensitivity" value={formData.dataSensitivity} onChange={handleInputChange} style={styles.select}>
                  <option value="low">Low — Public</option>
                  <option value="internal">Internal — Employees only</option>
                  <option value="confidential">Confidential — Restricted</option>
                </select>
              </div>
            </div>
          </div>

          {/* SQL Query */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <Code size={20} color="#EB0A1E" style={{ marginRight: '8px' }} />
              SQL Query
            </h2>

            <div style={styles.formGroup}>
              <label style={styles.label}>
                Query <span style={styles.required}>*</span>
              </label>
              <textarea
                name="query"
                value={formData.query}
                onChange={handleInputChange}
                placeholder="SELECT * FROM users WHERE active = true LIMIT 100;"
                rows={6}
                style={{
                  ...styles.textarea,
                  fontFamily: 'monospace',
                  fontSize: '13px',
                  ...(errors.query ? styles.inputError : {}),
                }}
              />
              {errors.query && (
                <div style={styles.errorMessage}><AlertCircle size={14} /><span>{errors.query}</span></div>
              )}
              <div style={styles.helpText}>
                <Info size={14} />
                <span>Enter the SQL statement to execute. Run-time overrides are supported.</span>
              </div>
            </div>
          </div>

          {/* Database Connection */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>
              <Server size={20} color="#EB0A1E" style={{ marginRight: '8px' }} />
              Database Connection
            </h2>

            <div style={styles.formRow}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Database Driver</label>
                <select name="db_driver" value={formData.db_driver} onChange={handleInputChange} style={styles.select}>
                  <option value="postgresql">PostgreSQL</option>
                  <option value="sqlite">SQLite</option>
                  <option value="snowflake">Snowflake</option>
                </select>
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Database Name</label>
                <input
                  type="text"
                  name="database"
                  value={formData.database}
                  onChange={handleInputChange}
                  placeholder={formData.db_driver === 'sqlite' ? '/path/to/db.sqlite' : 'my_database'}
                  style={styles.input}
                />
                <div style={styles.helpText}>
                  <Info size={14} />
                  <span>{formData.db_driver === 'sqlite' ? 'File path to SQLite database' : 'Database name on the server'}</span>
                </div>
              </div>
            </div>

            <div style={styles.formRow}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Host</label>
                <input
                  type="text"
                  name="host"
                  value={formData.host}
                  onChange={handleInputChange}
                  placeholder="db.example.com"
                  style={styles.input}
                />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Port</label>
                <input
                  type="number"
                  name="port"
                  value={formData.port}
                  onChange={handleInputChange}
                  placeholder="5432"
                  min={1}
                  max={65535}
                  style={styles.input}
                />
              </div>
            </div>

            <div style={styles.formRow}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Username</label>
                <input
                  type="text"
                  name="username"
                  value={formData.username}
                  onChange={handleInputChange}
                  placeholder="db_user"
                  style={styles.input}
                  autoComplete="off"
                />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Password</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="text"
                    name="password"
                    value={formData.password}
                    onChange={handleInputChange}
                    placeholder="••••••••"
                    style={{ ...styles.input, paddingRight: '40px', ...(showPassword ? {} : { WebkitTextSecurity: 'disc' }) }}
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((p) => !p)}
                    style={styles.passwordToggle}
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <div style={styles.helpText}>
                  <Info size={14} />
                  <span>Ephemeral — never stored. Passed only at run time.</span>
                </div>
              </div>
            </div>

            {formData.scheduleType !== 'on-demand' && (
              <div style={styles.formGroup}>
                <label style={styles.label}>Timezone</label>
                <input
                  type="text"
                  name="timezone"
                  value={formData.timezone}
                  onChange={handleInputChange}
                  placeholder="UTC"
                  style={styles.input}
                />
                <div style={styles.helpText}>
                  <Info size={14} />
                  <span>IANA timezone for scheduled runs (e.g. America/New_York)</span>
                </div>
              </div>
            )}
          </div>

          {/* Schedule */}
          <StructuredScheduleFields
            scheduleType={formData.scheduleType}
            scheduleDay={formData.scheduleDay}
            scheduleTime={formData.scheduleTime}
            weeklyDays={formData.weeklyDays}
            startDate={formData.startDate}
            stopCondition={formData.stopCondition}
            endDate={formData.endDate}
            maxRuns={formData.maxRuns}
            summaryPrefix="This job"
            scheduleTimeError={errors.scheduleTime}
            onFieldChange={(field, value) =>
              setFormData((prev) => ({ ...prev, [field]: value }))
            }
            onWeeklyDayToggle={handleWeeklyDayToggle}
          />

          {/* Buttons */}
          <div style={styles.buttonGroup}>
            <button
              type="button"
              onClick={() => (embedded ? onCancel?.() : navigate('/user-home'))}
              style={styles.cancelButton}
            >
              Cancel
            </button>

            <button
              type="button"
              disabled={isSubmitting}
              onClick={async (e) => {
                e.preventDefault();
                if (!validateForm()) return;
                const syntheticEvent = { preventDefault: () => {} } as FormEvent<HTMLFormElement>;
                await handleSubmit(syntheticEvent, true);
              }}
              style={{
                ...styles.runButton,
                ...(isSubmitting ? styles.submitButtonDisabled : {}),
              }}
            >
              <Play size={14} style={{ marginRight: '6px' }} />
              {isSubmitting ? 'Working...' : 'Create & Run Now'}
            </button>

            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                ...styles.submitButton,
                ...(isSubmitting ? styles.submitButtonDisabled : {}),
              }}
            >
              {isSubmitting ? 'Creating...' : 'Create Job'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

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
  errorBanner: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '16px',
    backgroundColor: '#FEE2E2',
    color: '#991B1B',
    borderLeft: '4px solid #EB0A1E',
    margin: '20px 40px',
    borderRadius: '4px',
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
    margin: '12px 40px 0',
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
  passwordToggle: {
    position: 'absolute',
    right: '10px',
    top: '50%',
    transform: 'translateY(-50%)',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: '#777777',
    display: 'flex',
    alignItems: 'center',
    padding: '0',
  },
  buttonGroup: {
    display: 'flex',
    flexWrap: 'wrap' as const,
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
  },
  runButton: {
    display: 'flex',
    alignItems: 'center',
    padding: '12px 24px',
    fontSize: '14px',
    fontWeight: '600',
    color: '#EB0A1E',
    backgroundColor: '#FFF5F5',
    border: '1px solid #F6B5BC',
    borderRadius: '4px',
    cursor: 'pointer',
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
  },
  submitButtonDisabled: {
    opacity: 0.6,
    cursor: 'not-allowed',
  },
};

export default SQLTemplateForm;
