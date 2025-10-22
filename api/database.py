"""Database models and setup for user management."""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path


class Database:
    """Simple SQLite database for user management."""

    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database with user tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)

        # User settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                outlook_tokens TEXT,
                user_identifier TEXT,
                odoo_url TEXT,
                odoo_db TEXT,
                odoo_username TEXT,
                odoo_password TEXT,
                settings_json TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        # Migration: Add Odoo columns if they don't exist
        try:
            cursor.execute("SELECT odoo_url FROM user_settings LIMIT 1")
        except sqlite3.OperationalError:
            # Columns don't exist, add them
            cursor.execute("ALTER TABLE user_settings ADD COLUMN odoo_url TEXT")
            cursor.execute("ALTER TABLE user_settings ADD COLUMN odoo_db TEXT")
            cursor.execute("ALTER TABLE user_settings ADD COLUMN odoo_username TEXT")
            cursor.execute("ALTER TABLE user_settings ADD COLUMN odoo_password TEXT")

        conn.commit()
        conn.close()

    def get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    def create_user(self, email: str, name: str, password_hash: str, role: str = "user") -> int:
        """Create a new user."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (email, name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (email, name, password_hash, role, datetime.utcnow().isoformat())
            )
            user_id = cursor.lastrowid

            # Initialize user settings
            cursor.execute(
                "INSERT INTO user_settings (user_id, settings_json) VALUES (?, ?)",
                (user_id, "{}")
            )

            conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            raise ValueError(f"User with email {email} already exists")
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, email, name, password_hash, role, created_at, last_login FROM users WHERE email = ?",
            (email,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "email": row[1],
            "name": row[2],
            "password_hash": row[3],
            "role": row[4],
            "created_at": row[5],
            "last_login": row[6]
        }

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, email, name, password_hash, role, created_at, last_login FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "email": row[1],
            "name": row[2],
            "password_hash": row[3],
            "role": row[4],
            "created_at": row[5],
            "last_login": row[6]
        }

    def update_last_login(self, user_id: int):
        """Update user's last login timestamp."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), user_id)
        )

        conn.commit()
        conn.close()

    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Get user settings."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT outlook_tokens, user_identifier, odoo_url, odoo_db, odoo_username, odoo_password, settings_json FROM user_settings WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {}

        outlook_tokens = json.loads(row[0]) if row[0] else None
        settings = json.loads(row[6]) if row[6] else {}

        return {
            "outlook_tokens": outlook_tokens,
            "user_identifier": row[1],
            "odoo_url": row[2],
            "odoo_db": row[3],
            "odoo_username": row[4],
            "odoo_password": row[5],
            **settings
        }

    def update_user_settings(self, user_id: int, **kwargs):
        """Update user settings."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get current settings
        cursor.execute("SELECT settings_json FROM user_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        current_settings = json.loads(row[0]) if row and row[0] else {}

        # Handle special columns separately
        outlook_tokens = kwargs.pop("outlook_tokens", None)
        user_identifier = kwargs.pop("user_identifier", None)
        odoo_url = kwargs.pop("odoo_url", None)
        odoo_db = kwargs.pop("odoo_db", None)
        odoo_username = kwargs.pop("odoo_username", None)
        odoo_password = kwargs.pop("odoo_password", None)

        # Update settings JSON with remaining kwargs
        current_settings.update(kwargs)

        # Build update query
        updates = ["settings_json = ?"]
        params = [json.dumps(current_settings)]

        if outlook_tokens is not None:
            updates.append("outlook_tokens = ?")
            params.append(json.dumps(outlook_tokens))

        if user_identifier is not None:
            updates.append("user_identifier = ?")
            params.append(user_identifier)

        if odoo_url is not None:
            updates.append("odoo_url = ?")
            params.append(odoo_url)

        if odoo_db is not None:
            updates.append("odoo_db = ?")
            params.append(odoo_db)

        if odoo_username is not None:
            updates.append("odoo_username = ?")
            params.append(odoo_username)

        if odoo_password is not None:
            updates.append("odoo_password = ?")
            params.append(odoo_password)

        params.append(user_id)

        cursor.execute(
            f"UPDATE user_settings SET {', '.join(updates)} WHERE user_id = ?",
            params
        )

        conn.commit()
        conn.close()

    def list_users(self) -> List[Dict[str, Any]]:
        """List all users (excluding password hashes)."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, email, name, role, created_at, last_login FROM users"
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "email": row[1],
                "name": row[2],
                "role": row[3],
                "created_at": row[4],
                "last_login": row[5]
            }
            for row in rows
        ]
