import React from "react";
import { Clock, Info } from "lucide-react";

export type ScheduleCadence = "on-demand" | "daily" | "weekly" | "monthly";
export type ScheduleStopCondition = "never" | "on-date" | "after-runs";

type StructuredScheduleFieldsProps = {
  scheduleType: ScheduleCadence;
  scheduleDay: string;
  scheduleTime: string;
  weeklyDays: string[];
  startDate: string;
  stopCondition: ScheduleStopCondition;
  endDate: string;
  maxRuns: string;
  summaryPrefix: string;
  onFieldChange: (field: string, value: string) => void;
  onWeeklyDayToggle: (day: string) => void;
  scheduleTimeError?: string;
};

const weekdayOptions = [
  { label: "Sun", value: "0" },
  { label: "Mon", value: "1" },
  { label: "Tue", value: "2" },
  { label: "Wed", value: "3" },
  { label: "Thu", value: "4" },
  { label: "Fri", value: "5" },
  { label: "Sat", value: "6" },
];

function ordinalSuffix(value: string) {
  const day = Number.parseInt(value, 10);
  if (Number.isNaN(day)) return value;
  const remainder = day % 10;
  const teen = day % 100;
  if (teen >= 11 && teen <= 13) return `${day}th`;
  if (remainder === 1) return `${day}st`;
  if (remainder === 2) return `${day}nd`;
  if (remainder === 3) return `${day}rd`;
  return `${day}th`;
}

function buildScheduleSummary(props: StructuredScheduleFieldsProps) {
  const {
    scheduleType,
    scheduleDay,
    scheduleTime,
    weeklyDays,
    stopCondition,
    endDate,
    maxRuns,
    summaryPrefix,
  } = props;

  if (scheduleType === "on-demand") {
    return `${summaryPrefix} will only run when manually triggered`;
  }

  const stopSummary =
    stopCondition === "on-date" && endDate
      ? ` and stop on ${endDate}`
      : stopCondition === "after-runs" && maxRuns
        ? ` and stop after ${maxRuns} runs`
        : "";

  if (scheduleType === "daily") {
    return `${summaryPrefix} will run daily at ${scheduleTime}${stopSummary}`;
  }

  if (scheduleType === "weekly") {
    const dayLabels = weekdayOptions
      .filter((option) => weeklyDays.includes(option.value))
      .map((option) => option.label)
      .join(", ");
    return `${summaryPrefix} will run weekly on ${dayLabels || "selected days"} at ${scheduleTime}${stopSummary}`;
  }

  return `${summaryPrefix} will run on the ${ordinalSuffix(scheduleDay)} of every month at ${scheduleTime}${stopSummary}`;
}

export function StructuredScheduleFields(props: StructuredScheduleFieldsProps) {
  const summary = buildScheduleSummary(props);

  return (
    <div style={styles.section}>
      <h2 style={styles.sectionTitle}>
        <Clock size={20} color="#EB0A1E" style={{ marginRight: "8px" }} />
        Schedule
      </h2>

      <div style={styles.schedulerCard}>
        <div style={styles.schedulerHeader}>
          <div>
            <label style={styles.schedulerLabel}>Run cadence</label>
            <p style={styles.schedulerHint}>Set how often this form should create a scheduled job.</p>
          </div>
          <div style={styles.summaryBadge}>{summary}</div>
        </div>

        <div style={styles.cadenceGrid}>
          {[
            { label: "On Demand", value: "on-demand" },
            { label: "Daily", value: "daily" },
            { label: "Weekly", value: "weekly" },
            { label: "Monthly", value: "monthly" },
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => props.onFieldChange("scheduleType", option.value)}
              style={{
                ...styles.cadenceButton,
                ...(props.scheduleType === option.value ? styles.cadenceButtonActive : {}),
              }}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div style={styles.scheduleGrid}>
          <div style={styles.formGroup}>
            <label style={styles.label}>Start Date</label>
            <input
              type="date"
              value={props.startDate}
              onChange={(e) => props.onFieldChange("startDate", e.target.value)}
              style={styles.input}
            />
          </div>

          {props.scheduleType !== "on-demand" && (
            <div style={styles.formGroup}>
              <label style={styles.label}>Run Time</label>
              <input
                type="time"
                value={props.scheduleTime}
                onChange={(e) => props.onFieldChange("scheduleTime", e.target.value)}
                style={{
                  ...styles.input,
                  ...(props.scheduleTimeError ? styles.inputError : {}),
                }}
              />
              {props.scheduleTimeError && <div style={styles.errorText}>{props.scheduleTimeError}</div>}
            </div>
          )}

          {props.scheduleType === "monthly" && (
            <div style={styles.formGroup}>
              <label style={styles.label}>Day of Month</label>
              <select
                value={props.scheduleDay}
                onChange={(e) => props.onFieldChange("scheduleDay", e.target.value)}
                style={styles.select}
              >
                {Array.from({ length: 31 }, (_, index) => `${index + 1}`).map((day) => (
                  <option key={day} value={day}>
                    Day {day}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {props.scheduleType === "weekly" && (
          <div style={styles.weekdayBlock}>
            <label style={styles.schedulerLabel}>Days of week</label>
            <div style={styles.weekdayRow}>
              {weekdayOptions.map((day) => (
                <button
                  key={day.value}
                  type="button"
                  onClick={() => props.onWeeklyDayToggle(day.value)}
                  style={{
                    ...styles.weekdayButton,
                    ...(props.weeklyDays.includes(day.value) ? styles.weekdayButtonActive : {}),
                  }}
                >
                  {day.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div style={styles.stopBlock}>
          <label style={styles.schedulerLabel}>Stop running</label>
          <div style={styles.stopGrid}>
            <button
              type="button"
              onClick={() => props.onFieldChange("stopCondition", "never")}
              style={{
                ...styles.stopCard,
                ...(props.stopCondition === "never" ? styles.stopCardActive : {}),
              }}
            >
              <div style={styles.stopCardTitle}>Never</div>
              <div style={styles.stopCardText}>Keep running until someone pauses or retires it.</div>
            </button>
            <button
              type="button"
              onClick={() => props.onFieldChange("stopCondition", "on-date")}
              style={{
                ...styles.stopCard,
                ...(props.stopCondition === "on-date" ? styles.stopCardActive : {}),
              }}
            >
              <div style={styles.stopCardTitle}>On Date</div>
              <div style={styles.stopCardText}>Choose a specific date to stop future runs.</div>
            </button>
            <button
              type="button"
              onClick={() => props.onFieldChange("stopCondition", "after-runs")}
              style={{
                ...styles.stopCard,
                ...(props.stopCondition === "after-runs" ? styles.stopCardActive : {}),
              }}
            >
              <div style={styles.stopCardTitle}>After N Runs</div>
              <div style={styles.stopCardText}>Stop automatically after a set number of runs.</div>
            </button>
          </div>
        </div>

        {props.stopCondition === "on-date" && (
          <div style={styles.formGroup}>
            <label style={styles.label}>End Date</label>
            <input
              type="date"
              value={props.endDate}
              onChange={(e) => props.onFieldChange("endDate", e.target.value)}
              style={styles.input}
            />
          </div>
        )}

        {props.stopCondition === "after-runs" && (
          <div style={styles.formGroup}>
            <label style={styles.label}>Maximum Runs</label>
            <input
              type="number"
              min="1"
              value={props.maxRuns}
              onChange={(e) => props.onFieldChange("maxRuns", e.target.value)}
              style={styles.input}
            />
          </div>
        )}

        <div style={styles.infoBox}>
          <Info size={16} color="#EB0A1E" />
          <span>{summary}</span>
        </div>
      </div>
    </div>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  section: {
    backgroundColor: "white",
    borderRadius: "12px",
    padding: "24px",
    boxShadow: "0 1px 3px rgba(0, 0, 0, 0.1)",
    marginBottom: "24px",
  },
  sectionTitle: {
    display: "flex",
    alignItems: "center",
    fontSize: "20px",
    fontWeight: 600,
    color: "#1F2937",
    marginBottom: "24px",
  },
  schedulerCard: {
    border: "1px solid #E5E7EB",
    borderRadius: "14px",
    backgroundColor: "#F9FAFB",
    padding: "18px",
  },
  schedulerHeader: {
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "space-between",
    gap: "12px",
    marginBottom: "18px",
  },
  schedulerLabel: {
    display: "block",
    fontSize: "11px",
    fontWeight: 700,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "#6B7280",
    marginBottom: "6px",
  },
  schedulerHint: {
    fontSize: "12px",
    color: "#6B7280",
    margin: 0,
  },
  summaryBadge: {
    backgroundColor: "white",
    borderRadius: "999px",
    padding: "8px 12px",
    fontSize: "11px",
    fontWeight: 600,
    lineHeight: 1.5,
    color: "#374151",
    maxWidth: "360px",
    overflowWrap: "anywhere",
  },
  cadenceGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: "8px",
    marginBottom: "18px",
  },
  cadenceButton: {
    borderRadius: "10px",
    border: "1px solid #D1D5DB",
    backgroundColor: "white",
    padding: "12px 14px",
    fontSize: "14px",
    fontWeight: 600,
    color: "#374151",
    cursor: "pointer",
  },
  cadenceButtonActive: {
    border: "1px solid #EB0A1E",
    backgroundColor: "#FFF5F5",
    color: "#EB0A1E",
  },
  scheduleGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: "16px",
  },
  weekdayBlock: {
    marginTop: "18px",
  },
  weekdayRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
  },
  weekdayButton: {
    borderRadius: "999px",
    border: "1px solid #D1D5DB",
    backgroundColor: "white",
    padding: "10px 14px",
    fontSize: "13px",
    fontWeight: 600,
    color: "#374151",
    cursor: "pointer",
  },
  weekdayButtonActive: {
    border: "1px solid #EB0A1E",
    backgroundColor: "#EB0A1E",
    color: "white",
  },
  stopBlock: {
    marginTop: "18px",
  },
  stopGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "12px",
  },
  stopCard: {
    borderRadius: "12px",
    border: "1px solid #D1D5DB",
    backgroundColor: "white",
    padding: "14px",
    textAlign: "left",
    cursor: "pointer",
  },
  stopCardActive: {
    border: "1px solid #EB0A1E",
    backgroundColor: "#FFF5F5",
  },
  stopCardTitle: {
    fontSize: "14px",
    fontWeight: 700,
    color: "#111827",
    marginBottom: "4px",
  },
  stopCardText: {
    fontSize: "12px",
    color: "#6B7280",
    lineHeight: 1.4,
  },
  formGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    marginTop: "16px",
  },
  label: {
    fontSize: "14px",
    fontWeight: 500,
    color: "#374151",
  },
  input: {
    width: "100%",
    padding: "12px 14px",
    border: "1px solid #D1D5DB",
    borderRadius: "10px",
    fontSize: "14px",
    outline: "none",
    boxSizing: "border-box",
    backgroundColor: "white",
  },
  select: {
    width: "100%",
    padding: "12px 14px",
    border: "1px solid #D1D5DB",
    borderRadius: "10px",
    fontSize: "14px",
    outline: "none",
    boxSizing: "border-box",
    backgroundColor: "white",
  },
  infoBox: {
    display: "flex",
    alignItems: "flex-start",
    gap: "8px",
    backgroundColor: "#FEF2F2",
    border: "1px solid #FECACA",
    borderRadius: "8px",
    padding: "12px 16px",
    fontSize: "13px",
    color: "#7F1D1D",
    marginTop: "18px",
  },
  inputError: {
    border: "1px solid #EF4444",
  },
  errorText: {
    fontSize: "12px",
    color: "#DC2626",
  },
};
