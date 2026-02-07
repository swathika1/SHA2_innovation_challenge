from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# ==================== PATIENT ROUTES ====================

@app.route('/')
def landing():
    """Landing / Login Page"""
    return render_template('landing.html')

@app.route('/patient/dashboard')
def patient_dashboard():
    """Patient Home Dashboard"""
    return render_template('patient/dashboard.html')

@app.route('/patient/session')
def rehab_session():
    """Rehab Session Screen (Core Screen)"""
    return render_template('patient/session.html')

@app.route('/patient/checkin')
def pain_checkin():
    """Pain & Effort Check-In Screen"""
    return render_template('patient/checkin.html')

@app.route('/patient/summary')
def session_summary():
    """Session Summary Screen"""
    return render_template('patient/summary.html')

@app.route('/patient/progress')
def progress_history():
    """Progress & History Screen"""
    return render_template('patient/progress.html')

# ==================== CLINICIAN ROUTES ====================

@app.route('/clinician/dashboard')
def clinician_dashboard():
    """Clinician Dashboard"""
    return render_template('clinician/dashboard.html')

@app.route('/clinician/patient/<patient_id>')
def patient_detail(patient_id):
    """Patient Detail View"""
    return render_template('clinician/patient_detail.html', patient_id=patient_id)

@app.route('/clinician/plan-editor')
def plan_editor():
    """Rehab Plan Editor"""
    return render_template('clinician/plan_editor.html')

@app.route('/clinician/consultation')
def consultation():
    """Consultation & Scheduling Screen"""
    return render_template('clinician/consultation.html')

# ==================== CAREGIVER ROUTES ====================

@app.route('/caregiver/dashboard')
def caregiver_dashboard():
    """Caregiver Dashboard"""
    return render_template('caregiver/dashboard.html')

# ==================== ROLE SELECTION ====================

@app.route('/select-role')
def select_role():
    """Role Selection Screen"""
    return render_template('role_select.html')

if __name__ == '__main__':
    app.run(debug=True)