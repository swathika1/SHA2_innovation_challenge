# PDF Medical History Import (OCR) — Design Spec

**Date:** 2026-04-03  
**Branch:** feature/patient-medical-history (or new feature branch)  
**Approach:** pdfplumber text extraction + Groq/Gemini LLM structured parsing

---

## Overview

Patients can optionally upload a PDF of their medical history during the post-signup step or from their profile page. The system extracts text from the PDF using `pdfplumber`, sends it to the existing LLM (Groq or Gemini) with a strict JSON schema prompt, and auto-fills the medical history form fields. The patient reviews and edits before saving. No data is written to the database until the patient explicitly submits.

---

## Backend

### New Endpoint

`POST /patient/medical-history/upload-pdf`

- **Auth:** Requires patient session (`@login_required`, role = `patient`)
- **Input:** `multipart/form-data` with field `pdf` (PDF file)
- **Output:** JSON object with 5 keys: `conditions`, `surgeries`, `injuries`, `medications`, `family_history`

### Processing Flow

1. Validate `pdf` field present in `request.files` — return 400 if missing
2. Reject files > 5MB — return 413 with message "File too large (max 5MB)"
3. Read file bytes into memory — no disk writes
4. Open with `pdfplumber.open(io.BytesIO(bytes))`, concatenate text from all pages
5. If extracted text is empty or whitespace-only:
   - Return HTTP 422 `{"error": "no_text", "message": "This PDF appears to be scanned or image-based. Please enter your history manually."}`
6. Build prompt (see Prompt Design section) with extracted text
7. Call existing Groq client (fallback: Gemini) to get structured JSON response
8. Validate returned JSON: check expected keys exist, strip unknown fields, coerce types
9. If LLM returns malformed JSON or validation fails — return 500 with user-friendly message
10. Return cleaned JSON to frontend — **no DB write**

### No Schema Changes

This feature requires no new database tables or migrations. All DB writes continue through the existing endpoints:
- Signup: `POST /signup/medical-history` (bulk)
- Profile: `POST/PUT /patient/medical-history/<category>` (per-item)

---

## Frontend

### Upload Widget (shared behavior)

Both entry points use identical UX:

- **Button:** "Import from PDF" (document icon), positioned above the 5 accordion/section forms
- **On click:** Opens native file picker filtered to `.pdf` only
- **On file selected:** Send to `/patient/medical-history/upload-pdf` via `fetch` with `FormData`
- **While loading:** Spinner replaces button; button disabled
- **On success:** Call `mhAutoFill(data)` to populate form rows (see below)
- **On error:** Show dismissible banner with error message; re-enable button

### `mhAutoFill(data)` Function

- Iterates each category in the returned JSON
- For each item in the array, creates a new form row using the existing row template (same as clicking "Add")
- Pre-fills the row fields with extracted values
- Skips categories where the array is empty — does not add blank rows
- Additive: does not clear existing saved records; only pre-fills the add-forms
- Displays notice banner: "Review the extracted data below before saving — fields may need correction."

### Entry Points

**`templates/patient/medical_history_signup.html`:**
- "Import from PDF" button above the 5 `<details>` accordion sections
- On fill, rows appear inside the accordion sections ready for review
- Patient submits the whole form as usual via existing `submitHistory()`

**`templates/patient/profile.html`:**
- "Import from PDF" button at the top of the Medical History card
- On fill, pre-populates the inline add-forms for each section
- Patient saves per-category using existing per-item save buttons

---

## LLM Prompt Design

### System Prompt

```
You are a medical data extraction assistant. Extract structured medical history from the provided text.
Return ONLY valid JSON matching the schema below. Do not infer or hallucinate — only extract what is explicitly stated.
Use null for any field not mentioned. Return empty arrays [] for categories with no data found.
Dates must be in YYYY-MM-DD format. If only a year is mentioned, use YYYY-01-01.
The boolean fields related_to_current, recovery_complete, and recurrence default to false unless clearly indicated.
```

### JSON Schema (required response shape)

```json
{
  "conditions": [
    { "name": "string", "onset_year": "integer or null", "notes": "string or null" }
  ],
  "surgeries": [
    {
      "procedure": "string",
      "body_region": "string or null",
      "surgery_date": "YYYY-MM-DD or null",
      "outcome": "string or null",
      "notes": "string or null"
    }
  ],
  "injuries": [
    {
      "body_region": "string",
      "injury_date": "YYYY-MM-DD or null",
      "description": "string or null",
      "related_to_current": false,
      "recovery_complete": false,
      "recurrence": false
    }
  ],
  "medications": [
    { "drug_name": "string", "indication": "string or null", "active": true }
  ],
  "family_history": [
    { "condition": "string", "relation": "string or null", "notes": "string or null" }
  ]
}
```

### User Message

```
Extract medical history from the following document text:

<document>
{extracted_text}
</document>
```

---

## Error Handling

| Condition | HTTP | Response |
|-----------|------|----------|
| No `pdf` field in request | 400 | `{"error": "no_file"}` |
| File > 5MB | 413 | `{"error": "too_large", "message": "Max 5MB"}` |
| PDF has no extractable text | 422 | `{"error": "no_text", "message": "Scanned PDF — enter manually"}` |
| LLM returns invalid JSON | 500 | `{"error": "parse_failed", "message": "Extraction failed — enter manually"}` |
| LLM API error / timeout | 500 | `{"error": "llm_error", "message": "Service unavailable — try again"}` |

All errors surface as dismissible banners in the UI. The patient can always close and enter history manually.

---

## Dependencies

No new Python packages required. `pdfplumber` is already in `requirements.txt`.

LLM client: use whichever of Groq/Gemini is already initialised and has a valid API key at runtime. Groq preferred (faster, cheaper for text tasks).

---

## Out of Scope

- Scanned/image PDFs (no pytesseract — return 422 with clear message)
- DOCX or image file formats
- Automatic saving without patient review
- De-duplication of extracted records against existing saved records
