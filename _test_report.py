"""Quick smoke test for report_generator.py"""
from report_generator import generate_session_report

session_data = {
    'quality_score': 35.2, 'completed_perc': 87, 'pain_before': 5,
    'pain_after': 3, 'effort_level': 7, 'started_at': '2025-01-15T10:30:00',
    'completed_at': '2025-01-15T10:55:00',
}
exercises = [
    {'exercise_name': 'Forward Flexion', 'quality_score': 38.5,
     'completion_perc': 90, 'sets_required': {'1': 10}, 'sets_completed': {'1': 9},
     'duration_seconds': 420},
    {'exercise_name': 'Torso Rotation', 'quality_score': 32.0,
     'completion_perc': 80, 'sets_required': {'1': 10}, 'sets_completed': {'1': 8},
     'duration_seconds': 360},
]
frames = []
for i in range(100):
    frames.append({
        'exercise_name': 'forward_flexion', 'score': 30 + (i % 15),
        'status': 'CORRECT' if (30 + i % 15) > 35 else 'WRONG',
        'rep_count': i // 10, 'set_count': 1, 'program': 'low_back_pain',
    })
for i in range(80):
    frames.append({
        'exercise_name': 'torso_rotation', 'score': 25 + (i % 20),
        'status': 'CORRECT' if (25 + i % 20) > 35 else 'WRONG',
        'rep_count': i // 10, 'set_count': 1, 'program': 'low_back_pain',
    })

pdf = generate_session_report(
    patient_name='Test Patient',
    patient_condition='Low Back Pain',
    session_data=session_data,
    exercises=exercises,
    frames=frames,
    overall_duration=1500,
)
with open('/tmp/test_report.pdf', 'wb') as f:
    f.write(pdf)
print(f'Generated {len(pdf)} bytes -> /tmp/test_report.pdf')
