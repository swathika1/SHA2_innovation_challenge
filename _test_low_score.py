"""Test low-score PDF to verify center-visit recommendation."""
from report_generator import generate_session_report

session_data = {
    'quality_score': 12.0, 'completed_perc': 30, 'pain_before': 6,
    'pain_after': 7, 'effort_level': 3, 'started_at': '2025-01-15T10:30:00',
    'completed_at': '2025-01-15T10:45:00',
}
exercises = [
    {'exercise_name': 'Lifting of Arms', 'quality_score': 12.0,
     'completion_perc': 30, 'sets_required': {'1': 10}, 'sets_completed': {'1': 3},
     'duration_seconds': 300},
]
frames = []
for i in range(50):
    frames.append({
        'exercise_name': 'Lifting of Arms', 'score': 5 + (i % 10),
        'status': 'WRONG',
        'rep_count': i // 15, 'set_count': 1, 'program': 'general',
    })

pdf = generate_session_report('John', 'General Rehab', session_data, exercises, frames, 900)
with open('/tmp/test_report_low.pdf', 'wb') as f:
    f.write(pdf)
print(f'Generated {len(pdf)} bytes -> /tmp/test_report_low.pdf')

try:
    import fitz
    doc = fitz.open('/tmp/test_report_low.pdf')
    print(f'\nTotal pages: {len(doc)}')
    for i, page in enumerate(doc):
        text = page.get_text()
        for kw in ['Action Required', 'center', 'visit', 'appointment', 'supervised', 'Needs Improvement', 'Poor']:
            if kw.lower() in text.lower():
                idx = text.lower().index(kw.lower())
                snippet = text[idx:idx+140].replace('\n', ' ').strip()
                print(f'  Page {i+1}: "{kw}" -> {snippet}')
except ImportError:
    print('(PyMuPDF not installed, open /tmp/test_report_low.pdf manually)')
