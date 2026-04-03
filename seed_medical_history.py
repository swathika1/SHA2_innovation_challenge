#!/usr/bin/env python3
"""
seed_medical_history.py
-----------------------
Inserts synthetic but realistic medical history records for three patients:
  - patient@test.com     → John Patient
  - john.doe@example.com → Jack Daniels
  - saiashwin2001@gmail.com → Sai Ashwin

All records are marked self_report / unverified.
Safe to re-run: checks for existing records before inserting.
"""

import sqlite3
import sys
import os

DB_PATH = 'rehab_coach.db'


def get_patient_id(cursor, email: str) -> int | None:
    cursor.execute('SELECT id FROM users WHERE email = ? AND role = ?', (email, 'patient'))
    row = cursor.fetchone()
    return row[0] if row else None


def has_history(cursor, patient_id: int) -> bool:
    cursor.execute('SELECT COUNT(*) FROM medical_conditions WHERE patient_id = ?', (patient_id,))
    return cursor.fetchone()[0] > 0


def seed_john_patient(cursor, pid: int):
    """
    John Patient — knee replacement, well-managed diabetes.
    History shows good glycaemic control but incomplete recovery
    from a prior knee injury, raising his re-injury risk.
    """
    # Chronic conditions
    cursor.executemany(
        '''INSERT INTO medical_conditions (patient_id, name, onset_year, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Type 2 Diabetes',  2015,
             'Managed with Metformin; HbA1c 6.8% at last check. Slows tissue healing.', pid),
            (pid, 'Hypertension',     2018,
             'Controlled with Amlodipine 5mg. Blood pressure stable at ~130/85.', pid),
        ]
    )

    # Past surgeries
    cursor.executemany(
        '''INSERT INTO medical_surgeries (patient_id, procedure, surgery_date, body_region, outcome, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Total Knee Replacement', '2025-11-10', 'Right Knee',
             'Successful — currently in post-op rehab', 'Primary reason for current rehab programme.', pid),
            (pid, 'Meniscectomy (partial)', '2019-04-22', 'Right Knee',
             'Full recovery achieved', 'Arthroscopic removal of torn medial meniscus.', pid),
        ]
    )

    # Past injuries — one related to current problem, incomplete recovery
    cursor.executemany(
        '''INSERT INTO medical_injuries
               (patient_id, body_region, injury_description, related_to_current,
                recovery_complete, recurrence, injury_date, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Right Knee', 'Grade II MCL sprain', 1, 0, 1,
             '2022-08-15',
             'Related to current knee problem. Incomplete recovery — mild instability persists. '
             'Has recurred: same knee sprained again in 2023.', pid),
            (pid, 'Lower Back', 'L4-L5 disc bulge', 0, 1, 0,
             '2017-03-10',
             'Unrelated to current problem. Fully recovered after 6 months of physiotherapy.', pid),
        ]
    )

    # Medications — consistent with diabetes + hypertension + post-op pain
    cursor.executemany(
        '''INSERT INTO medical_medications (patient_id, drug_name, indication, active, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Metformin 500mg twice daily',   'Type 2 Diabetes',   1, pid),
            (pid, 'Amlodipine 5mg once daily',     'Hypertension',      1, pid),
            (pid, 'Celecoxib 200mg as needed',     'Post-op knee pain', 1, pid),
            (pid, 'Aspirin 81mg once daily',       'Cardiovascular prophylaxis', 1, pid),
        ]
    )

    # Family history
    cursor.executemany(
        '''INSERT INTO medical_family_history (patient_id, condition, relation, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Type 2 Diabetes',     'Father',
             'Father diagnosed at 58. Paternal grandmother also diabetic.', pid),
            (pid, 'Cardiovascular disease', 'Mother',
             'Mother had coronary artery bypass at age 65.', pid),
        ]
    )


def seed_jack_daniels(cursor, pid: int):
    """
    Jack Daniels — lower-back pain (Spine & MSK).
    History: hypertension, two prior spine surgeries, recurrent disc injury.
    Medications align with chronic pain management.
    """
    cursor.executemany(
        '''INSERT INTO medical_conditions (patient_id, name, onset_year, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Hypertension',            2012,
             'On Lisinopril. BP averages 138/88. Reduces peripheral healing perfusion.', pid),
            (pid, 'Chronic Lower Back Pain', 2016,
             'Degenerative disc disease at L4-L5 and L5-S1. Ongoing for 8 years.', pid),
        ]
    )

    cursor.executemany(
        '''INSERT INTO medical_surgeries (patient_id, procedure, surgery_date, body_region, outcome, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Lumbar Microdiscectomy L4-L5', '2017-09-05', 'Lumbar Spine',
             'Partial recovery — residual numbness in left leg', 'First spinal decompression surgery.', pid),
            (pid, 'Spinal Fusion L5-S1',          '2021-06-18', 'Lumbar Spine',
             'Improved stability; pain partially controlled',
             'Fusion due to instability following first surgery. Adjacent segment now at risk.', pid),
        ]
    )

    cursor.executemany(
        '''INSERT INTO medical_injuries
               (patient_id, body_region, injury_description, related_to_current,
                recovery_complete, recurrence, injury_date, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Lumbar Spine', 'L4-L5 disc herniation', 1, 0, 1,
             '2016-02-20',
             'Directly related to current rehab programme. Incomplete recovery — chronic pain remains. '
             'Recurrence: re-herniated in 2020 following heavy lifting.', pid),
            (pid, 'Left Shoulder', 'Rotator cuff strain (Grade I)', 0, 1, 0,
             '2023-11-03',
             'Unrelated to spine problem. Healed fully with conservative management in 8 weeks.', pid),
        ]
    )

    cursor.executemany(
        '''INSERT INTO medical_medications (patient_id, drug_name, indication, active, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Lisinopril 10mg once daily',    'Hypertension',              1, pid),
            (pid, 'Pregabalin 75mg twice daily',   'Neuropathic back pain',     1, pid),
            (pid, 'Naproxen 500mg as needed',      'Musculoskeletal pain',      1, pid),
            (pid, 'Omeprazole 20mg once daily',    'GI protection (with NSAID)', 1, pid),
        ]
    )

    cursor.executemany(
        '''INSERT INTO medical_family_history (patient_id, condition, relation, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Osteoporosis',              'Mother',
             'Mother fractured hip at 70. Suggests possible hereditary bone density deficit.', pid),
            (pid, 'Connective Tissue Disorder', 'Brother',
             'Brother diagnosed with hypermobile Ehlers-Danlos syndrome (hEDS). '
             'May indicate hereditary collagen/ligament laxity in the family.', pid),
        ]
    )


def seed_sai_ashwin(cursor, pid: int):
    """
    Sai Ashwin — sports injury / orthopaedic rehab.
    History: well-controlled asthma, prior ACL injury that has not fully resolved,
    with recurrence. Younger patient, fewer comorbidities.
    """
    cursor.executemany(
        '''INSERT INTO medical_conditions (patient_id, name, onset_year, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Asthma (mild intermittent)', 2008,
             'Managed with salbutamol inhaler as needed. Well-controlled; no recent hospitalisations.', pid),
            (pid, 'Patellofemoral Pain Syndrome', 2022,
             'Bilateral, worse on left. Aggravated by squatting and stairs. Related to current rehab.', pid),
        ]
    )

    cursor.executemany(
        '''INSERT INTO medical_surgeries (patient_id, procedure, surgery_date, body_region, outcome, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'ACL Reconstruction (BPTB graft)', '2023-03-14', 'Left Knee',
             'Good structural outcome; returned to sport at 9 months',
             'Bone-patellar tendon-bone autograft. Current rehab relates to residual strength deficit.', pid),
            (pid, 'Arthroscopic Knee Washout',        '2021-07-30', 'Left Knee',
             'Symptom relief achieved', 'Removal of loose cartilage fragments post-lateral ankle sprain sequelae.', pid),
        ]
    )

    cursor.executemany(
        '''INSERT INTO medical_injuries
               (patient_id, body_region, injury_description, related_to_current,
                recovery_complete, recurrence, injury_date, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Left Knee', 'ACL rupture (complete tear)', 1, 0, 1,
             '2023-01-08',
             'Directly related to current programme. Recovery ongoing — not yet back to full pre-injury '
             'function. Recurrence risk elevated: prior ACL reconstruction is a known re-injury predictor.', pid),
            (pid, 'Right Ankle', 'Grade III lateral ligament sprain', 0, 1, 0,
             '2020-09-19',
             'Unrelated to current problem. Fully healed after 12 weeks of bracing and physio.', pid),
        ]
    )

    cursor.executemany(
        '''INSERT INTO medical_medications (patient_id, drug_name, indication, active, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Salbutamol 100mcg inhaler (as needed)', 'Asthma',               1, pid),
            (pid, 'Ibuprofen 400mg as needed',             'Knee inflammation',    1, pid),
            (pid, 'Vitamin D3 2000 IU daily',              'Bone health support',  1, pid),
        ]
    )

    cursor.executemany(
        '''INSERT INTO medical_family_history (patient_id, condition, relation, notes, entry_mode, verified, entered_by)
           VALUES (?, ?, ?, ?, 'self_report', 0, ?)''',
        [
            (pid, 'Rheumatoid Arthritis', 'Mother',
             'Mother diagnosed at 45. Possible autoimmune predisposition in the family.', pid),
            (pid, 'Asthma',              'Father',
             'Father has moderate persistent asthma. Hereditary atopic tendency confirmed.', pid),
        ]
    )


def main():
    print("\n" + "=" * 60)
    print("  SEED — SYNTHETIC MEDICAL HISTORY DATA")
    print("=" * 60 + "\n")

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run init_database.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    targets = [
        ('patient@test.com',          'John Patient',  seed_john_patient),
        ('john.doe@example.com',      'Jack Daniels',  seed_jack_daniels),
        ('saiashwin2001@gmail.com',   'Sai Ashwin',    seed_sai_ashwin),
    ]

    seeded = 0
    for email, name, seed_fn in targets:
        pid = get_patient_id(cursor, email)
        if pid is None:
            print(f"  SKIP  {name} ({email}) — user not found in database")
            continue
        if has_history(cursor, pid):
            print(f"  SKIP  {name} — medical history already exists (id={pid})")
            continue
        seed_fn(cursor, pid)
        print(f"  OK    {name} (id={pid}, email={email})")
        seeded += 1

    conn.commit()
    conn.close()

    print(f"\nSeeded {seeded} patient(s).")
    print("All records: entry_mode='self_report', verified=0\n")


if __name__ == '__main__':
    main()
