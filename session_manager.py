from sqlalchemy import create_engine, Column, String, Text, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()
engine = create_engine("sqlite:///database/patient_profiles.db")


class PatientProfile(Base):
    __tablename__ = "patients"
    patient_id    = Column(String, primary_key=True)
    name          = Column(String)
    age           = Column(String)
    conditions    = Column(Text)
    medications   = Column(Text)
    exercise_plan = Column(Text)
    language_pref = Column(String, default="en")


class SessionLog(Base):
    __tablename__ = "sessions"
    id            = Column(String, primary_key=True)
    patient_id    = Column(String)
    timestamp     = Column(DateTime, default=datetime.utcnow)
    summary       = Column(Text)
    pain_reported = Column(Text)
    risk_score    = Column(Float)


Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def get_patient_context(patient_id: str) -> str:
    db = Session()
    patient = db.query(PatientProfile).filter_by(patient_id=patient_id).first()
    recent_sessions = (
        db.query(SessionLog)
        .filter_by(patient_id=patient_id)
        .order_by(SessionLog.timestamp.desc())
        .limit(3)
        .all()
    )
    db.close()

    if not patient:
        return "New patient - no history available."

    context = f"""
    Name: {patient.name} | Age: {patient.age}
    Known Conditions: {patient.conditions}
    Current Medications: {patient.medications}
    Exercise Plan: {patient.exercise_plan}

    Recent Sessions (last 3):
    """
    for s in recent_sessions:
        context += f"\n- [{s.timestamp.date()}] Summary: {s.summary} | Pain reported: {s.pain_reported}"

    return context
