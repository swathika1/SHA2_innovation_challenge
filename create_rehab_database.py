from main import app, db, User, UserVisit
from datetime import datetime, date

with app.app_context():
    # Drop all tables and recreate them
    db.drop_all()
    db.create_all()
    
    # Create dummy users
    users_data = [
        {
            'name': 'John Doe',
            'email_id': 'john.doe@example.com',
            'role': 'patient',
            'password': 'password123',
            'joining_date': '2024-01-15',
            'address': '123 Main Street, Springfield, IL 62701'
        },
        {
            'name': 'Dr. Smith',
            'email_id': 'dr.smith@example.com',
            'role': 'clinician',
            'password': 'password123',
            'joining_date': '2023-06-01',
            'address': '456 Medical Plaza, Springfield, IL 62702'
        },
        {
            'name': 'Jane Caregiver',
            'email_id': 'jane.care@example.com',
            'role': 'caregiver',
            'password': 'password123',
            'joining_date': '2023-09-10',
            'address': '789 Care Lane, Springfield, IL 62703'
        }
    ]
    
    for user_data in users_data:
        user = User(
            name=user_data['name'],
            email_id=user_data['email_id'],
            role=user_data['role'],
            password=user_data['password'],
            joining_date=user_data['joining_date'],
            address=user_data['address']
        )
        db.session.add(user)
    
    db.session.commit()
    
    # Create a visit for the first user
    first_user = User.query.filter_by(email_id='john.doe@example.com').first()
    if first_user:
        visit = UserVisit(
            user_id=first_user.user_id,
            visit_time=datetime.utcnow()
        )
        db.session.add(visit)
        db.session.commit()
    
    print("=" * 60)
    print("Database populated successfully!")
    print("=" * 60)
    print("\nTest Credentials:")
    print("-" * 60)
    for user_data in users_data:
        print(f"Role: {user_data['role'].upper()}")
        print(f"Email: {user_data['email_id']}")
        print(f"Password: {user_data['password']}")
        print("-" * 60)
    
    # Verify the data
    all_users = User.query.all()
    print(f"\nTotal users in database: {len(all_users)}")
    for user in all_users:
        print(f"  - {user.name} ({user.email_id}) - {user.role}")