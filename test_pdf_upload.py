# test_pdf_upload.py
import io
import pytest
import pdfplumber
from unittest.mock import patch, MagicMock

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
