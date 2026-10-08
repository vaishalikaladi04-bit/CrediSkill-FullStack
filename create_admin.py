from app import mongo, app
from werkzeug.security import generate_password_hash
import datetime
import os

with app.app_context():
    email = os.getenv('ADMIN_EMAIL')
    password = os.getenv('ADMIN_PASSWORD')

    if not email or not password:
        raise RuntimeError('Set ADMIN_EMAIL and ADMIN_PASSWORD in the environment or .env file.')
    if len(password) < 12:
        raise ValueError('ADMIN_PASSWORD must be at least 12 characters long.')

    # Check if admin already exists
    admin_exists = mongo.db.users.find_one({'email': email})

    if not admin_exists:
        admin = {
            'name': 'System Administrator',
            'email': email,
            'password': generate_password_hash(password),
            'role': 'admin',
            'created_at': datetime.datetime.now()
        }
        result = mongo.db.users.insert_one(admin)
        print(f"Admin user created with ID: {result.inserted_id}")
        print(f"Email: {email}")
    else:
        print("Admin user already exists!")