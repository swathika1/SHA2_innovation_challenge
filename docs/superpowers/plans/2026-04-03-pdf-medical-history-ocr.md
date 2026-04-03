# PDF Medical History Import (OCR) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow patients to upload a PDF of their medical history and have it auto-extracted via pdfplumber + Groq LLM, pre-filling the medical history form for review before saving.

**Architecture:** A single new Flask endpoint extracts PDF text and calls Groq for structured JSON extraction. Frontend adds an "Import from PDF" button on both the signup medical history page (row-based auto-fill) and the patient profile page (confirmation panel with bulk save). No DB writes happen until the patient explicitly confirms.

**Tech Stack:** Flask, pdfplumber (already installed), Groq API (already integrated), vanilla JS fetch + FormData

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `main.py` | Modify | Add `POST /patient/medical-history/upload-pdf` endpoint (~60 lines, inserted before `signup_medical_history` at line 3176) |
| `templates/patient/medical_history_signup.html` | Modify | Add "Import from PDF" button + hidden file input + `mhAutoFill()` + `mhPdfUpload()` JS |
| `templates/patient/profile.html` | Modify | Add "Import from PDF" button + confirmation panel + `mhAutoFill()` + `mhSaveExtracted()` JS |

---

## Task 1: Backend — PDF upload and extraction endpoint

**Files:**
- Modify: `main.py` (insert before line 3176, the `signup_medical_history` route)

- [ ] **Step 1: Write the failing test**

Create `test_pdf_upload.py` in the project root:

```python
# test_pdf_upload.py
import io
import pytest
import pdfplumber
from unittest.mock import patch, MagicMock

# We test the logic in isolation — no Flask app needed for unit tests.

def _make_pdf_bytes(text: str) -> bytes:
    """Build a minimal in-memory PDF with the given text using reportlab."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.save()
    return buf.getvalue()

def test_pdfplumber_extracts_text():
    pdf_bytes = _make_pdf_bytes("Type 2 Diabetes onset 2015")
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
    assert "Diabetes" in text

def test_empty_pdf_returns_empty_text():
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.save()
    pdf_bytes = buf.getvalue()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
    assert text.strip() == ''

def test_clean_str():
    def _clean_str(v):
        return str(v).strip() if v is not None else None
    assert _clean_str("  hello  ") == "hello"
    assert _clean_str(None) is None
    assert _clean_str(123) == "123"

def test_clean_int():
    def _clean_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    assert _clean_int("2015") == 2015
    assert _clean_int(None) is None
    assert _clean_int("abc") is None

def test_result_filters_empty_names():
    def _clean_str(v):
        return str(v).strip() if v is not None else None
    def _clean_int(v):
        try: return int(v)
        except: return None
    extracted = {"conditions": [{"name": "", "onset_year": None, "notes": None}, {"name": "Diabetes", "onset_year": 2015, "notes": None}]}
    result_conditions = [
        {'name': _clean_str(c.get('name')), 'onset_year': _clean_int(c.get('onset_year')), 'notes': _clean_str(c.get('notes'))}
        for c in extracted.get('conditions', []) if c.get('name')
    ]
    assert len(result_conditions) == 1
    assert result_conditions[0]['name'] == 'Diabetes'
    assert result_conditions[0]['onset_year'] == 2015
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd "/Users/hrithikkannankrishnan/Desktop/Innovation Challenge /SHA2_innovation_challenge"
python -m pytest test_pdf_upload.py -v
```

Expected: tests about `_clean_str` / `_clean_int` / `_result_filters` pass immediately (pure logic). `test_pdfplumber_extracts_text` and `test_empty_pdf_returns_empty_text` should pass if pdfplumber + reportlab are available, or fail with ImportError — that's acceptable; they confirm the library works.

- [ ] **Step 3: Add the endpoint to `main.py`**

Insert the following block in `main.py` immediately before the line:
```
@app.route('/signup/medical-history', methods=['GET', 'POST'])
```
(currently at line 3176)

```python
@app.route('/patient/medical-history/upload-pdf', methods=['POST'])
@login_required
@role_required('patient')
def patient_medical_history_upload_pdf():
    """Extract structured medical history from an uploaded PDF using pdfplumber + Groq."""
    import io as _io
    import json as _json
    import pdfplumber as _pdfplumber

    if 'pdf' not in request.files:
        return jsonify({'error': 'no_file', 'message': 'No PDF file provided.'}), 400

    pdf_file = request.files['pdf']
    pdf_bytes = pdf_file.read()

    if len(pdf_bytes) > 5 * 1024 * 1024:
        return jsonify({'error': 'too_large', 'message': 'File too large. Maximum size is 5MB.'}), 413

    # Extract text from PDF
    try:
        with _pdfplumber.open(_io.BytesIO(pdf_bytes)) as _pdf:
            _text = '\n'.join(_page.extract_text() or '' for _page in _pdf.pages)
    except Exception:
        return jsonify({'error': 'parse_failed', 'message': 'Could not read PDF. Please try a different file.'}), 500

    if not _text.strip():
        return jsonify({
            'error': 'no_text',
            'message': 'This PDF appears to be scanned or image-based. Please enter your history manually.'
        }), 422

    _system_prompt = (
        "You are a medical data extraction assistant. Extract structured medical history from the provided text. "
        "Return ONLY valid JSON matching the exact schema below. Do not infer or hallucinate — only extract what is explicitly stated. "
        "Use null for any field not mentioned. Return empty arrays [] for categories with no data found. "
        "Dates must be in YYYY-MM-DD format; if only a year is given, use YYYY-01-01. "
        "The boolean fields related_to_current, recovery_complete, and recurrence default to false unless clearly indicated.\n\n"
        "Required JSON schema:\n"
        '{"conditions":[{"name":"string","onset_year":null,"notes":null}],'
        '"surgeries":[{"procedure":"string","body_region":null,"surgery_date":null,"outcome":null,"notes":null}],'
        '"injuries":[{"body_region":"string","injury_date":null,"description":null,"related_to_current":false,"recovery_complete":false,"recurrence":false}],'
        '"medications":[{"drug_name":"string","indication":null,"active":true}],'
        '"family_history":[{"condition":"string","relation":null,"notes":null}]}'
    )
    _user_msg = f"Extract medical history from the following document text:\n\n<document>\n{_text[:8000]}\n</document>"

    try:
        from groq import Groq as _Groq
        _groq_client = _Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        _resp = _groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": _system_prompt},
                {"role": "user", "content": _user_msg},
            ],
            response_format={"type": "json_object"},
            max_tokens=1500,
        )
        _raw = _resp.choices[0].message.content.strip()
    except Exception:
        return jsonify({'error': 'llm_error', 'message': 'Extraction service unavailable. Please try again or enter manually.'}), 500

    try:
        _extracted = _json.loads(_raw)
    except _json.JSONDecodeError:
        return jsonify({'error': 'parse_failed', 'message': 'Extraction failed. Please enter your history manually.'}), 500

    def _cs(v):
        return str(v).strip() if v is not None else None

    def _ci(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    _result = {
        'conditions': [
            {'name': _cs(c.get('name')), 'onset_year': _ci(c.get('onset_year')), 'notes': _cs(c.get('notes'))}
            for c in _extracted.get('conditions', []) if c.get('name')
        ],
        'surgeries': [
            {'procedure': _cs(s.get('procedure')), 'body_region': _cs(s.get('body_region')),
             'surgery_date': _cs(s.get('surgery_date')), 'outcome': _cs(s.get('outcome')), 'notes': _cs(s.get('notes'))}
            for s in _extracted.get('surgeries', []) if s.get('procedure')
        ],
        'injuries': [
            {'body_region': _cs(i.get('body_region')), 'injury_date': _cs(i.get('injury_date')),
             'injury_description': _cs(i.get('description')),
             'related_to_current': bool(i.get('related_to_current', False)),
             'recovery_complete': bool(i.get('recovery_complete', False)),
             'recurrence': bool(i.get('recurrence', False))}
            for i in _extracted.get('injuries', []) if i.get('body_region')
        ],
        'medications': [
            {'drug_name': _cs(m.get('drug_name')), 'indication': _cs(m.get('indication')),
             'active': bool(m.get('active', True))}
            for m in _extracted.get('medications', []) if m.get('drug_name')
        ],
        'family_history': [
            {'condition': _cs(f.get('condition')), 'relation': _cs(f.get('relation')), 'notes': _cs(f.get('notes'))}
            for f in _extracted.get('family_history', []) if f.get('condition')
        ],
    }

    return jsonify(_result)

```

- [ ] **Step 4: Run the tests**

```bash
cd "/Users/hrithikkannankrishnan/Desktop/Innovation Challenge /SHA2_innovation_challenge"
python -m pytest test_pdf_upload.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Smoke-test the endpoint manually**

Start the Flask app, then in a separate terminal:

```bash
# Create a test PDF with text (requires reportlab):
python3 -c "
from reportlab.pdfgen import canvas; import io
buf = open('/tmp/test_mh.pdf', 'wb')
c = canvas.Canvas(buf)
c.drawString(72, 720, 'Patient has Type 2 Diabetes since 2015.')
c.drawString(72, 700, 'Medications: Metformin 500mg for diabetes (active).')
c.drawString(72, 680, 'Family history: Mother has osteoporosis.')
c.save()
"

# Upload as a logged-in patient (replace SESSION_COOKIE with a real value from browser):
curl -s -X POST http://localhost:5001/patient/medical-history/upload-pdf \
  -H "Cookie: session=<YOUR_SESSION_COOKIE>" \
  -F "pdf=@/tmp/test_mh.pdf" | python3 -m json.tool
```

Expected response:
```json
{
  "conditions": [{"name": "Type 2 Diabetes", "onset_year": 2015, "notes": null}],
  "surgeries": [],
  "injuries": [],
  "medications": [{"drug_name": "Metformin 500mg", "indication": "diabetes", "active": true}],
  "family_history": [{"condition": "osteoporosis", "relation": "Mother", "notes": null}]
}
```

- [ ] **Step 6: Commit**

```bash
cd "/Users/hrithikkannankrishnan/Desktop/Innovation Challenge /SHA2_innovation_challenge"
git add main.py test_pdf_upload.py
git commit -m "feat: add PDF medical history upload and extraction endpoint"
```

---

## Task 2: Frontend — Signup page (`medical_history_signup.html`)

**Files:**
- Modify: `templates/patient/medical_history_signup.html`

- [ ] **Step 1: Add CSS for the upload button and notice banner**

In `medical_history_signup.html`, locate the closing `</style>` tag (after `.btn-skip:hover { color:#333; }`). Insert these styles immediately before `</style>`:

```css
.pdf-upload-btn {
    display:inline-flex; align-items:center; gap:8px; padding:10px 20px;
    background:#fff; color:#6366f1; border:2px solid #6366f1;
    border-radius:10px; font-size:.92rem; font-weight:700; cursor:pointer;
    transition:background .15s, color .15s; margin-bottom:20px;
}
.pdf-upload-btn:hover { background:#eef3ff; }
.pdf-upload-btn:disabled { opacity:.5; cursor:not-allowed; }
.pdf-fill-notice {
    background:#f0fdf4; border:1px solid #86efac; border-radius:8px;
    padding:12px 16px; font-size:.85rem; color:#166534; margin-bottom:20px;
    display:none; gap:8px; align-items:flex-start;
}
```

- [ ] **Step 2: Add the upload button and hidden input to the HTML**

In `medical_history_signup.html`, locate the paragraph that reads:
```html
<p style="color:#666;margin:0 0 20px;font-size:.97rem;">This helps your care team personalise your rehab plan. All fields are optional.</p>
```

Add the following block immediately after that `<p>` tag (before the `<div class="mh-notice">`):

```html
    <!-- PDF Import -->
    <input type="file" id="pdf-input" accept=".pdf" style="display:none" onchange="mhPdfUpload(this)">
    <button type="button" class="pdf-upload-btn" id="pdf-upload-btn" onclick="document.getElementById('pdf-input').click()">
        <i class="fa-solid fa-file-medical"></i> Import from PDF
    </button>
    <div class="pdf-fill-notice" id="pdf-fill-notice">
        <i class="fa-solid fa-circle-check" style="flex-shrink:0;margin-top:2px;"></i>
        <span>Medical history extracted from your PDF. Review the fields below and edit if needed before saving.</span>
    </div>
    <div id="pdf-error-banner" style="display:none;background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:12px 16px;font-size:.85rem;color:#991b1b;margin-bottom:16px;">
        <i class="fa-solid fa-triangle-exclamation"></i> <span id="pdf-error-msg"></span>
        <button onclick="document.getElementById('pdf-error-banner').style.display='none'" style="float:right;background:none;border:none;cursor:pointer;color:#991b1b;">✕</button>
    </div>
```

- [ ] **Step 3: Add `mhPdfUpload()` and `mhAutoFill()` functions to the `<script>` block**

In `medical_history_signup.html`, locate the closing `</script>` tag at the very end of the file. Insert the following functions immediately before `</script>`:

```javascript
async function mhPdfUpload(input) {
    const file = input.files[0];
    if (!file) return;
    const btn = document.getElementById('pdf-upload-btn');
    const errBanner = document.getElementById('pdf-error-banner');
    const errMsg = document.getElementById('pdf-error-msg');
    errBanner.style.display = 'none';
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Extracting...';

    const formData = new FormData();
    formData.append('pdf', file);

    try {
        const res = await fetch('/patient/medical-history/upload-pdf', {method: 'POST', body: formData});
        const data = await res.json();
        if (!res.ok) {
            errMsg.textContent = data.message || 'Extraction failed. Please enter manually.';
            errBanner.style.display = 'block';
        } else {
            mhAutoFill(data);
        }
    } catch (e) {
        errMsg.textContent = 'Network error. Please try again.';
        errBanner.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-file-medical"></i> Import from PDF';
        input.value = '';
    }
}

function mhAutoFill(data) {
    const sectionCfg = {
        conditions: {
            listId: 'conditions-list',
            template: 'conditions',
            fields: ['name', 'onset_year', 'notes'],
            checkboxes: []
        },
        surgeries: {
            listId: 'surgeries-list',
            template: 'surgeries',
            fields: ['procedure', 'body_region', 'surgery_date', 'outcome', 'notes'],
            checkboxes: []
        },
        injuries: {
            listId: 'injuries-list',
            template: 'injuries',
            fields: ['body_region', 'injury_date', 'injury_description'],
            checkboxes: ['related_to_current', 'recovery_complete', 'recurrence']
        },
        medications: {
            listId: 'medications-list',
            template: 'medications',
            fields: ['drug_name', 'indication'],
            checkboxes: ['active']
        },
        family_history: {
            listId: 'family_history-list',
            template: 'family_history',
            fields: ['condition', 'relation', 'notes'],
            checkboxes: []
        }
    };

    let totalAdded = 0;

    for (const [section, cfg] of Object.entries(sectionCfg)) {
        const items = data[section] || [];
        if (!items.length) continue;
        const list = document.getElementById(cfg.listId);
        if (!list) continue;

        for (const item of items) {
            addRow(cfg.template);
            const lastRow = list.lastElementChild;
            if (!lastRow) continue;

            for (const fieldName of cfg.fields) {
                const el = lastRow.querySelector(`[name="${fieldName}"]`);
                if (el && item[fieldName] != null) el.value = item[fieldName];
            }
            for (const cbName of cfg.checkboxes) {
                const el = lastRow.querySelector(`[name="${cbName}"]`);
                if (el) el.checked = !!item[cbName];
            }
            totalAdded++;
        }

        // Auto-open the accordion
        const details = list.closest('details');
        if (details) details.open = true;
    }

    if (totalAdded > 0) {
        document.getElementById('pdf-fill-notice').style.display = 'flex';
        window.scrollTo({top: 0, behavior: 'smooth'});
    }
}
```

- [ ] **Step 4: Manually verify in browser**

1. Start the Flask app
2. Create a new patient account → land on the medical history signup page
3. Click "Import from PDF", select a medical PDF
4. Verify form rows are added and pre-filled with extracted data
5. Verify the green notice banner appears
6. Verify you can still edit/delete rows before saving
7. Click "Save & Continue" — verify data saves and redirects to dashboard

- [ ] **Step 5: Test error cases**

- Upload a file > 5MB → expect red error banner "File too large..."
- Upload a PDF with no text (create one: `python3 -c "from reportlab.pdfgen import canvas; c=canvas.Canvas('/tmp/empty.pdf'); c.save()"`) → expect "This PDF appears to be scanned..."
- Upload a non-PDF file renamed to `.pdf` → expect "Could not read PDF..."

- [ ] **Step 6: Commit**

```bash
cd "/Users/hrithikkannankrishnan/Desktop/Innovation Challenge /SHA2_innovation_challenge"
git add templates/patient/medical_history_signup.html
git commit -m "feat: add PDF import to medical history signup page"
```

---

## Task 3: Frontend — Patient profile page (`profile.html`)

**Files:**
- Modify: `templates/patient/profile.html`

- [ ] **Step 1: Add CSS for the upload button and confirmation panel**

In `profile.html`, find the existing `<style>` block that contains `.mh-add-btn`. Add these rules at the end of that same style block (before its closing `</style>`):

```css
.pdf-upload-btn {
    display:inline-flex; align-items:center; gap:7px; padding:8px 16px;
    background:#fff; color:#6366f1; border:2px solid #6366f1;
    border-radius:9px; font-size:.85rem; font-weight:700; cursor:pointer;
    transition:background .15s; margin-bottom:14px;
}
.pdf-upload-btn:hover { background:#eef3ff; }
.pdf-upload-btn:disabled { opacity:.5; cursor:not-allowed; }
#pdf-confirm-panel {
    display:none; background:#f0fdf4; border:1px solid #86efac;
    border-radius:10px; padding:14px 16px; margin-bottom:16px; font-size:.88rem;
}
#pdf-confirm-panel h4 { margin:0 0 8px; font-size:.92rem; color:#166534; }
#pdf-confirm-list { margin:0 0 12px; padding-left:18px; color:#374151; line-height:1.8; }
.pdf-confirm-actions { display:flex; gap:10px; }
.pdf-save-btn { padding:8px 18px; background:#22c55e; color:#fff; border:none; border-radius:8px; font-weight:700; cursor:pointer; font-size:.88rem; }
.pdf-save-btn:disabled { opacity:.5; }
.pdf-cancel-btn { padding:8px 14px; background:none; border:1px solid #aaa; border-radius:8px; color:#555; cursor:pointer; font-size:.88rem; }
#pdf-profile-error { display:none; background:#fef2f2; border:1px solid #fca5a5; border-radius:8px; padding:10px 14px; font-size:.84rem; color:#991b1b; margin-bottom:12px; }
```

- [ ] **Step 2: Add the upload button and confirmation panel to the Medical History card**

In `profile.html`, locate the paragraph inside the Medical History card:
```html
            <p style="font-size:.85rem;color:#888;margin:0 0 16px;">
                Self-reported — reviewed by your clinician. Records marked
```

Insert the following block immediately before that `<p>` tag:

```html
            <!-- PDF Import -->
            <input type="file" id="pdf-profile-input" accept=".pdf" style="display:none" onchange="mhPdfUpload(this)">
            <button type="button" class="pdf-upload-btn" id="pdf-profile-btn" onclick="document.getElementById('pdf-profile-input').click()">
                <i class="fa-solid fa-file-medical"></i> Import from PDF
            </button>
            <div id="pdf-profile-error">
                <i class="fa-solid fa-triangle-exclamation"></i> <span id="pdf-profile-error-msg"></span>
                <button onclick="document.getElementById('pdf-profile-error').style.display='none'" style="float:right;background:none;border:none;cursor:pointer;color:#991b1b;">✕</button>
            </div>
            <div id="pdf-confirm-panel">
                <h4><i class="fa-solid fa-circle-check"></i> Medical history extracted from PDF</h4>
                <p style="margin:0 0 8px;color:#374151;">Review the records below, then click <strong>Save All</strong> to add them to your profile.</p>
                <ul id="pdf-confirm-list"></ul>
                <div class="pdf-confirm-actions">
                    <button class="pdf-save-btn" id="pdf-save-btn" onclick="mhSaveExtracted()">Save All</button>
                    <button class="pdf-cancel-btn" onclick="mhCancelExtracted()">Cancel</button>
                </div>
            </div>
```

- [ ] **Step 3: Add `mhPdfUpload()`, `mhAutoFill()`, `mhSaveExtracted()`, `mhCancelExtracted()` to the `<script>` block**

In `profile.html`, locate the line `mhLoad();` near the bottom of the `<script>` block (line ~863). Insert the following functions immediately before `mhLoad();`:

```javascript
async function mhPdfUpload(input) {
    const file = input.files[0];
    if (!file) return;
    const btn = document.getElementById('pdf-profile-btn');
    const errEl = document.getElementById('pdf-profile-error');
    const errMsg = document.getElementById('pdf-profile-error-msg');
    errEl.style.display = 'none';
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Extracting...';

    const formData = new FormData();
    formData.append('pdf', file);

    try {
        const res = await fetch('/patient/medical-history/upload-pdf', {method: 'POST', body: formData});
        const data = await res.json();
        if (!res.ok) {
            errMsg.textContent = data.message || 'Extraction failed. Please enter manually.';
            errEl.style.display = 'block';
        } else {
            mhAutoFill(data);
        }
    } catch (e) {
        errMsg.textContent = 'Network error. Please try again.';
        errEl.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-file-medical"></i> Import from PDF';
        input.value = '';
    }
}

function mhAutoFill(data) {
    const labels = {
        conditions:     c => c.name + (c.onset_year ? ` (${c.onset_year})` : ''),
        surgeries:      s => s.procedure + (s.body_region ? ` — ${s.body_region}` : ''),
        injuries:       i => i.body_region + (i.injury_description ? `: ${i.injury_description}` : ''),
        medications:    m => m.drug_name + (m.indication ? ` for ${m.indication}` : ''),
        family_history: f => f.condition + (f.relation ? ` (${f.relation})` : '')
    };
    const sectionNames = {
        conditions: 'Conditions', surgeries: 'Surgeries',
        injuries: 'Injuries', medications: 'Medications', family_history: 'Family History'
    };

    let total = 0;
    const listEl = document.getElementById('pdf-confirm-list');
    listEl.innerHTML = '';

    for (const [section, items] of Object.entries(data)) {
        if (!items || !items.length) continue;
        const groupLi = document.createElement('li');
        groupLi.style.fontWeight = '700';
        groupLi.textContent = sectionNames[section] || section;
        listEl.appendChild(groupLi);
        for (const item of items) {
            const li = document.createElement('li');
            li.style.marginLeft = '12px';
            li.style.fontWeight = '400';
            li.textContent = labels[section] ? labels[section](item) : JSON.stringify(item);
            listEl.appendChild(li);
            total++;
        }
    }

    if (total > 0) {
        window._pdfExtracted = data;
        document.getElementById('pdf-confirm-panel').style.display = 'block';
        document.getElementById('pdf-confirm-panel').scrollIntoView({behavior: 'smooth', block: 'nearest'});
    } else {
        const errEl = document.getElementById('pdf-profile-error');
        document.getElementById('pdf-profile-error-msg').textContent = 'No medical history found in this PDF. Please enter manually.';
        errEl.style.display = 'block';
    }
}

async function mhSaveExtracted() {
    const data = window._pdfExtracted || {};
    const btn = document.getElementById('pdf-save-btn');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    const endpointMap = {
        conditions:     '/patient/medical-history/condition',
        surgeries:      '/patient/medical-history/surgery',
        injuries:       '/patient/medical-history/injury',
        medications:    '/patient/medical-history/medication',
        family_history: '/patient/medical-history/family-history'
    };

    for (const [category, items] of Object.entries(data)) {
        const endpoint = endpointMap[category];
        if (!endpoint || !items.length) continue;
        for (const item of items) {
            await fetch(endpoint, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(item)
            });
        }
    }

    mhCancelExtracted();
    await mhLoad();
}

function mhCancelExtracted() {
    window._pdfExtracted = null;
    document.getElementById('pdf-confirm-panel').style.display = 'none';
    document.getElementById('pdf-confirm-list').innerHTML = '';
}
```

- [ ] **Step 4: Manually verify in browser**

1. Log in as a patient, go to Profile page
2. Scroll to the Medical History card — verify "Import from PDF" button appears above the existing content
3. Click the button, upload a medical PDF
4. Verify the green confirmation panel appears listing all extracted records
5. Click "Save All" — verify records appear in the medical history sections after `mhLoad()` reloads
6. Click "Cancel" — verify panel hides and no records are saved
7. Test error case: upload a scanned/image PDF → expect red error banner

- [ ] **Step 5: Commit**

```bash
cd "/Users/hrithikkannankrishnan/Desktop/Innovation Challenge /SHA2_innovation_challenge"
git add templates/patient/profile.html
git commit -m "feat: add PDF import to patient profile medical history card"
```

---

## Task 4: Final integration check and PR

- [ ] **Step 1: Run all tests**

```bash
cd "/Users/hrithikkannankrishnan/Desktop/Innovation Challenge /SHA2_innovation_challenge"
python -m pytest test_pdf_upload.py -v
```

Expected: all pass.

- [ ] **Step 2: Full end-to-end walkthrough**

Test the complete user journey:

**Signup flow:**
1. Register a new patient account
2. On the post-signup medical history page, click "Import from PDF"
3. Upload a medical PDF → verify rows auto-fill
4. Edit one field manually → verify it's editable
5. Click "Save & Continue" → verify data is in the DB and dashboard loads

**Profile flow:**
1. Log in as the same patient, go to Profile
2. Click "Import from PDF" in the Medical History card
3. Upload a different PDF
4. Confirm extracted records in the panel
5. Click "Save All" → verify records appear in the card sections

- [ ] **Step 3: Push branch and open PR**

```bash
cd "/Users/hrithikkannankrishnan/Desktop/Innovation Challenge /SHA2_innovation_challenge"
git push origin feature/patient-medical-history
```

Then open a PR from `feature/patient-medical-history` → `main` on GitHub with title: "feat: PDF medical history import with OCR extraction"
