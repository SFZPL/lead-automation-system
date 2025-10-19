"""Script to create initial admin user."""

import sys
from api.database import Database
from api.auth import AuthService

def create_admin():
    db = Database()
    auth = AuthService(db)

    # Check if admin already exists
    existing_admin = db.get_user_by_email("admin@prezlab.com")
    if existing_admin:
        print("Admin user already exists!")
        print(f"Email: admin@prezlab.com")
        return

    # Create admin user
    try:
        user_id = auth.register_user(
            email="admin@prezlab.com",
            name="Admin User",
            password="prezlab2024",
            role="admin"
        )
        print(f"[OK] Admin user created successfully!")
        print(f"  Email: admin@prezlab.com")
        print(f"  Password: prezlab2024")
        print(f"  User ID: {user_id}")
        print(f"\nPlease change the password after first login!")
    except Exception as e:
        print(f"[ERROR] Error creating admin user: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_admin()
