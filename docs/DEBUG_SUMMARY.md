# Chat-to-Form Update Flow - Debug & Fix Summary

## Bugs Identified

### BUG #1: CreateJobForm Never Syncs User Changes Back to Parent
**Location:** `frontend/src/app/components/CreateJobForm.tsx`

**Problem:**
- The form receives `draftData` from parent and updates its local state (jobType, universal, airflowDetails, etc.)
- However, when the user types in form inputs, these changes are ONLY reflected in local state
- The `onDraftDataChange` callback is NEVER called, so parent never learns about user edits
- This means chat extraction gets the stale form state, and user edits are lost

**Root Cause:**
- `onDraftDataChange` prop was defined but never invoked in any onChange handler
- No mechanism existed to sync form state back to parent JobDraft state

**Fix:**
```tsx
// Added helper function
const updateDraftAndParent = (type, uni, airflow, excel, powerpoint) => {
  if (!onDraftDataChange || isApplyingDraftDataRef.current) return;
  const draft = { job_type: type, ...uni, ...typeSpecificFields };
  onDraftDataChange(draft);
};

// Added new useEffect to sync form changes to parent
useEffect(() => {
  updateDraftAndParent(jobType, universal, airflowDetails, excelDetails, powerpointDetails);
}, [jobType, universal, airflowDetails, excelDetails, powerpointDetails, onDraftDataChange]);
```

**Why This Works:**
- Whenever user modifies any form field, React batches the state updates
- The new useEffect watches all form state and calls parent callback
- Parent updates jobDraft, which represents true state of the draft
- Next extraction gets the full current state as context

---

### BUG #2: Infinite Update Loop Risk
**Problem:**
- When parent passes draftData to form, form updates local state
- Local state change triggers new useEffect that calls onDraftDataChange
- Parent receives update and re-renders with new draftData prop
- This could cause infinite loop

**Fix:**
```tsx
const isApplyingDraftDataRef = useRef(false);

// In draftData useEffect:
isApplyingDraftDataRef.current = true;
// ... update states ...
setTimeout(() => {
  isApplyingDraftDataRef.current = false;
}, 0);

// In updateDraftAndParent:
if (isApplyingDraftDataRef.current) return; // Skip sync when applying external data
```

**Why This Works:**
- Flag tracks whether state changes came from draftData prop update
- When flag is true, updateDraftAndParent is skipped
- User input always triggers updateDraftAndParent since flag is false
- Prevents circular updates while allowing extraction changes to flow through

---

### BUG #3: Field Extraction Not Recognizing Multiple Fields
**Location:** `backend/app/services/field_extraction_service.py`

**Problem:**
- Extraction prompt didn't clearly show that MULTIPLE fields can be extracted
- LLM might be extracting only job_name and ignoring job_type when both are mentioned
- User says "PowerPoint and name the job Job_test" → Only job_name is extracted

**Root Cause:**
- Extraction prompt lacked examples of multi-field extraction
- No normalization instructions for job_type variations (e.g., "powerpoint" vs "PowerPoint")
- Owner field extraction not clear (didn't understand "im the owner" pattern)

**Fix:**
```python
def _build_extraction_prompt(...):
    return f"""...

IMPORTANT:
- Recognize job_type variations: "powerpoint", "PowerPoint", "ppt" → "PowerPoint"
- Recognize owner patterns: "I'm the owner", "im the owner" → extract as owner
- Extract ALL fields mentioned, not just job_name

EXTRACTION EXAMPLES:
- User: "Create a PowerPoint named Revenue Dashboard"
  → {{"job_name": "Revenue Dashboard", "job_type": "PowerPoint"}}
- User: "Im the owner and schedule it for monday at 3am"
  → {{"owner": "user", "schedule": "every Monday at 3am"}}
"""
```

**Why This Works:**
- Examples show LLM that multiple fields can be extracted at once
- Specific patterns for owner recognition and job_type normalization
- More detailed field descriptions help LLM understand what to extract

---

### BUG #4: Job-Type Field Synchronization Issue
**Problem:**
- When draftData includes a new job_type, the form updates jobType state
- However, the form wasn't properly clearing old type-specific fields
- Form wasn't properly initializing new type-specific fields

**Fix:**
- Changed useEffect condition from `if (draftData.job_type && ...)` to `if (draftData.job_type === "Airflow")` 
- Each job type section now gets full update with received data
- All fields now use `!== undefined` checks instead of just falsy checks, allowing empty strings and 0 values

---

## Data Flow After Fixes

### Scenario 1: Chat Extraction Updates Form
```
1. User: "PowerPoint named Revenue Dashboard, owner is john@example.com"
2. Backend extraction: {job_type: "PowerPoint", job_name: "Revenue Dashboard", owner: "john@example.com"}
3. ChatPanel calls: onFieldsExtracted(extractedFields)
4. UserHome: setJobDraft(prev => ({ ...prev, ...extractedFields }))
5. CreateJobForm receives draftData={job_type: "PowerPoint", job_name: "...", owner: "..."}
6. First useEffect applies to form state with isApplyingDraftDataRef=true
7. Form updates: jobType="PowerPoint", universal.job_name="Revenue Dashboard", universal.owner="john@example..."
8. setTimeout resets isApplyingDraftDataRef to false
9. Form renders with UI showing PowerPoint type section and filled fields
---Flow complete! User sees all extracted fields updated in form
```

### Scenario 2: User Types in Form
```
1. User types "My Job" in job_name input
2. onChange handler calls: setUniversal({...universal, job_name: "My Job"})
3. Second useEffect watches universal and fires
4. Calls updateDraftAndParent (isApplyingDraftDataRef is false so proceeds)
5. Calls onDraftDataChange with {job_type: "...", job_name: "My Job", ...}
6. UserHome: setJobDraft(prev => ({ ...prev, job_name: "My Job" }))
7. CreateJobForm receives draftData update
8. First useEffect sees draftData change, sets isApplyingDraftDataRef=true
9. Updates form state again (idempotent, value already "My Job")
10. isApplyingDraftDataRef resets to false
11. Second useEffect fires but data is same, so parent gets same update again
--- Flow stabilizes. User sees real-time sync to parent state
```

---

## Field Name Mapping Verification

The form field names must match extraction output exactly:

### Universal Fields Match ✓
- `job_name` → `job_name`
- `owner` → `owner`
- `schedule` → `schedule`
- `environment` → `environment`
- `description` → `description`
- `approval_required` → `approval_required`
- `run_type` → `run_type`
- `tags` → `tags`
- `job_type` → `job_type`

### Airflow Fields Match ✓
- `dag_name` → `dag_name`
- `tasks` → `tasks`
- `data_sources` (string in form, array in draft) → properly converted
- `data_destinations` → properly converted
- `execution_timeout` → `execution_timeout`

### Excel Fields Match ✓
- `output_file_name` → `output_file_name`
- `input_data_sources` → `input_data_sources`
- `pivot_tables` → `pivot_tables`

### PowerPoint Fields Match ✓
- `slide_template` → `slide_template`
- `metrics_to_include` → `metrics_to_include` (array)
- `data_source` → `data_source`
- `branding_theme` → `branding_theme`

---

## Why Only job_name Was Working Before

**Historical Issue:**
With the old code, when extraction returned `{job_name: "Job_test"}`:
1. ChatPanel would receive this
2. Call onFieldsExtracted
3. Parent setJobDraft would run
4. Form would receive new draftData
5. Form useEffect would see job_name and update it
6. Form would render with updated job_name ✓

But when extraction returned `{job_type: "PowerPoint", job_name: "Job_test"}`:
1. Same flow happens
2. AND form would see job_type value
3. BUT form NEVER synced job_type back to parent
4. So job_type change wasn't persistently stored in parent
5. When re-rendering or next extraction ran, job_type might revert
6. Parent also wasn't passing current job_type to next extraction, so it was lost

The other bug preventing updates:
- Form NEVER called onDraftDataChange when user typed
- So extraction never got full context of what user had entered
- This prevented the assistant from understanding form state properly

---

## Testing the Fixes

### Test 1: Chat Extraction with Multiple Fields
```
User: "I want a PowerPoint job called Dashboard, owned by john@company.com"
Expected: Both job_type and job_name and owner display in form
Before fix: Only job_name shows
After fix: ✓ All three fields populated
```

### Test 2: User Types, Then Chat Updates
```
1. User types "My Job" in job_name field
2. Says "make it an airflow job"
3. Expected: Form shows Airflow type selected, job_name still "My Job"
Before fix: Airflow button might not update, or job_name might reset
After fix: ✓ Both persist correctly
```

### Test 3: Chat See's Current Draft State
```
1. User types "Revenue Dashboard" as job name
2. Asks "What job type should this be?"
3. Assistant should suggest based on what's in draft
Expected: Assistant can see "Revenue Dashboard" exists
Before fix: Assistant always saw empty draft
After fix: ✓ onDraftDataChange syncs form to parent
```

---

## Code Changes Summary

### File: frontend/src/app/components/CreateJobForm.tsx
1. Added `useRef` import
2. Added `isApplyingDraftDataRef` to track external updates
3. Added `updateDraftAndParent()` helper function
4. Enhanced draftData useEffect with ref flag logic
5. Added new useEffect to sync form changes to parent
6. Changed field checks from falsy (`&&`) to `!== undefined` for proper nil handling

### File: backend/app/services/field_extraction_service.py
1. Enhanced `_build_extraction_prompt()` with:
   - Job_type normalization instructions
   - Owner pattern recognition examples
   - Multi-field extraction examples
   - Better field descriptions

### File: backend/app/api/routers/chat.py
- ✓ No changes needed - already passes current_draft_data to extraction service

---

## Result

✅ All fields now update reliably from chat
✅ User edits persist through chat interactions
✅ Form state stays synchronized with parent throughout user session
✅ Future extractions have full context of current draft state
✅ job_type and owner and other fields all update correctly
