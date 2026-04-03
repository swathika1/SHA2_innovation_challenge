# test_pdf_upload.py
import io
import sys
import os
import pytest
import pdfplumber
from unittest.mock import patch, MagicMock

# ── Pure logic tests (no Flask needed) ────────────────────────────────────────

def _make_pdf_bytes(text: str) -> bytes:
    """Build a minimal in-memory PDF with the given text using reportlab."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.save()
    return buf.getvalue()

def _make_empty_pdf_bytes() -> bytes:
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.save()
    return buf.getvalue()

def test_pdfplumber_extracts_text():
    pdf_bytes = _make_pdf_bytes("Type 2 Diabetes onset 2015")
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
    assert "Diabetes" in text

def test_empty_pdf_returns_empty_text():
    pdf_bytes = _make_empty_pdf_bytes()
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

def test_result_filters_empty_required_fields():
    """Filtering logic: items with empty required fields are excluded for all categories."""
    def _cs(v): return str(v).strip() if v is not None else None
    def _ci(v):
        try: return int(v)
        except: return None

    extracted = {
        "conditions": [{"name": "", "onset_year": None, "notes": None}, {"name": "Diabetes", "onset_year": 2015, "notes": None}],
        "surgeries": [{"procedure": "", "body_region": None}, {"procedure": "ACL Reconstruction", "body_region": "Right Knee"}],
        "injuries": [{"body_region": "", "injury_date": None}, {"body_region": "Left Knee", "injury_date": None}],
        "medications": [{"drug_name": "", "indication": None}, {"drug_name": "Metformin", "indication": "Diabetes"}],
        "family_history": [{"condition": "", "relation": None}, {"condition": "Osteoporosis", "relation": "Mother"}],
    }
    conditions = [c for c in extracted["conditions"] if c.get("name")]
    surgeries = [s for s in extracted["surgeries"] if s.get("procedure")]
    injuries = [i for i in extracted["injuries"] if i.get("body_region")]
    medications = [m for m in extracted["medications"] if m.get("drug_name")]
    family_history = [f for f in extracted["family_history"] if f.get("condition")]

    assert len(conditions) == 1 and conditions[0]["name"] == "Diabetes"
    assert len(surgeries) == 1 and surgeries[0]["procedure"] == "ACL Reconstruction"
    assert len(injuries) == 1 and injuries[0]["body_region"] == "Left Knee"
    assert len(medications) == 1 and medications[0]["drug_name"] == "Metformin"
    assert len(family_history) == 1 and family_history[0]["condition"] == "Osteoporosis"

# ── HTTP-level endpoint tests ──────────────────────────────────────────────────

def _get_app():
    """Import the Flask app with test config."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')
    os.environ.setdefault('GROQ_API_KEY', 'test-key')
    from main import app as flask_app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    return flask_app

def _authed_client(flask_app):
    """Return a test client with a patient session set."""
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 999
        sess['role'] = 'patient'
        sess['user_name'] = 'Test Patient'
    return client

def test_endpoint_requires_auth():
    """Unauthenticated request is redirected (login_required)."""
    flask_app = _get_app()
    client = flask_app.test_client()
    resp = client.post('/patient/medical-history/upload-pdf')
    # login_required redirects to login page
    assert resp.status_code in (302, 401)

def test_endpoint_returns_400_if_no_pdf_field():
    """Missing pdf field returns 400."""
    flask_app = _get_app()
    client = _authed_client(flask_app)
    resp = client.post('/patient/medical-history/upload-pdf', data={}, content_type='multipart/form-data')
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['error'] == 'no_file'

def test_endpoint_returns_413_if_file_too_large():
    """File > 5MB returns 413."""
    flask_app = _get_app()
    client = _authed_client(flask_app)
    big_bytes = b'%PDF-1.4 ' + b'x' * (5 * 1024 * 1024 + 1)
    resp = client.post(
        '/patient/medical-history/upload-pdf',
        data={'pdf': (io.BytesIO(big_bytes), 'big.pdf')},
        content_type='multipart/form-data'
    )
    assert resp.status_code == 413
    data = resp.get_json()
    assert data['error'] == 'too_large'

def test_endpoint_returns_422_for_empty_pdf():
    """PDF with no extractable text returns 422."""
    flask_app = _get_app()
    client = _authed_client(flask_app)
    empty_pdf = _make_empty_pdf_bytes()
    resp = client.post(
        '/patient/medical-history/upload-pdf',
        data={'pdf': (io.BytesIO(empty_pdf), 'empty.pdf')},
        content_type='multipart/form-data'
    )
    assert resp.status_code == 422
    data = resp.get_json()
    assert data['error'] == 'no_text'

def test_endpoint_returns_500_on_groq_failure():
    """Groq API failure returns 500 with llm_error."""
    flask_app = _get_app()
    client = _authed_client(flask_app)
    pdf_bytes = _make_pdf_bytes("Patient has diabetes")

    with patch('groq.Groq') as mock_groq_cls:
        mock_groq_cls.return_value.chat.completions.create.side_effect = Exception("API down")
        resp = client.post(
            '/patient/medical-history/upload-pdf',
            data={'pdf': (io.BytesIO(pdf_bytes), 'test.pdf')},
            content_type='multipart/form-data'
        )
    assert resp.status_code == 500
    data = resp.get_json()
    assert data['error'] == 'llm_error'

def test_endpoint_happy_path_returns_structured_json():
    """Valid PDF + Groq success returns structured JSON with all 5 keys."""
    flask_app = _get_app()
    client = _authed_client(flask_app)
    pdf_bytes = _make_pdf_bytes("Patient has Type 2 Diabetes since 2015. Medications: Metformin.")

    mock_llm_response = '{"conditions":[{"name":"Type 2 Diabetes","onset_year":2015,"notes":null}],"surgeries":[],"injuries":[],"medications":[{"drug_name":"Metformin","indication":null,"active":true}],"family_history":[]}'

    with patch('groq.Groq') as mock_groq_cls:
        mock_instance = MagicMock()
        mock_groq_cls.return_value = mock_instance
        mock_instance.chat.completions.create.return_value.choices[0].message.content = mock_llm_response

        resp = client.post(
            '/patient/medical-history/upload-pdf',
            data={'pdf': (io.BytesIO(pdf_bytes), 'test.pdf')},
            content_type='multipart/form-data'
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert set(data.keys()) == {'conditions', 'surgeries', 'injuries', 'medications', 'family_history'}
    assert data['conditions'][0]['name'] == 'Type 2 Diabetes'
    assert data['conditions'][0]['onset_year'] == 2015
    assert data['medications'][0]['drug_name'] == 'Metformin'

def test_endpoint_maps_description_to_injury_description():
    """LLM 'description' field is mapped to 'injury_description' in response."""
    flask_app = _get_app()
    client = _authed_client(flask_app)
    pdf_bytes = _make_pdf_bytes("Patient had a knee injury in 2020.")

    mock_llm_response = '{"conditions":[],"surgeries":[],"injuries":[{"body_region":"Left Knee","injury_date":"2020-01-01","description":"MCL sprain","related_to_current":false,"recovery_complete":false,"recurrence":false}],"medications":[],"family_history":[]}'

    with patch('groq.Groq') as mock_groq_cls:
        mock_instance = MagicMock()
        mock_groq_cls.return_value = mock_instance
        mock_instance.chat.completions.create.return_value.choices[0].message.content = mock_llm_response

        resp = client.post(
            '/patient/medical-history/upload-pdf',
            data={'pdf': (io.BytesIO(pdf_bytes), 'test.pdf')},
            content_type='multipart/form-data'
        )

    assert resp.status_code == 200
    data = resp.get_json()
    injury = data['injuries'][0]
    assert 'injury_description' in injury
    assert injury['injury_description'] == 'MCL sprain'
    assert 'description' not in injury
