"""Supabase-based database for user management."""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from cryptography.fernet import Fernet
import os

from api.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class SupabaseDatabase:
    """Supabase database for user management with encrypted credentials."""

    def __init__(self):
        self.supabase = get_supabase_client()

        # Encryption key for Odoo passwords
        # In production, store this in environment variable or secrets manager
        self.encryption_key = os.getenv('ENCRYPTION_KEY')
        if not self.encryption_key:
            # Generate a key if not exists (for development only)
            self.encryption_key = Fernet.generate_key().decode()
            logger.warning("Using generated encryption key. Set ENCRYPTION_KEY environment variable in production!")

        self.cipher = Fernet(self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key)

    def _encrypt_password(self, password: str) -> str:
        """Encrypt a password."""
        return self.cipher.encrypt(password.encode()).decode()

    def _decrypt_password(self, encrypted_password: str) -> str:
        """Decrypt a password."""
        return self.cipher.decrypt(encrypted_password.encode()).decode()

    def create_user(self, email: str, name: str, password_hash: str, role: str = "user") -> int:
        """Create a new user."""
        try:
            # Insert user
            result = self.supabase.client.table("users").insert({
                "email": email,
                "name": name,
                "password_hash": password_hash,
                "role": role,
            }).execute()

            if not result.data:
                raise ValueError(f"Failed to create user {email}")

            user_id = result.data[0]["id"]

            # Initialize user settings
            self.supabase.client.table("user_settings").insert({
                "user_id": user_id,
                "settings_json": {}
            }).execute()

            return user_id

        except Exception as e:
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                raise ValueError(f"User with email {email} already exists")
            raise

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        result = self.supabase.client.table("users")\
            .select("*")\
            .eq("email", email)\
            .execute()

        if not result.data:
            return None

        user = result.data[0]
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "password_hash": user["password_hash"],
            "role": user["role"],
            "created_at": user["created_at"],
            "last_login": user.get("last_login")
        }

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        result = self.supabase.client.table("users")\
            .select("*")\
            .eq("id", user_id)\
            .execute()

        if not result.data:
            return None

        user = result.data[0]
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "password_hash": user["password_hash"],
            "role": user["role"],
            "created_at": user["created_at"],
            "last_login": user.get("last_login")
        }

    def update_last_login(self, user_id: int):
        """Update user's last login timestamp."""
        self.supabase.client.table("users")\
            .update({"last_login": datetime.utcnow().isoformat()})\
            .eq("id", user_id)\
            .execute()

    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Get user settings with decrypted Odoo password."""
        result = self.supabase.client.table("user_settings")\
            .select("*")\
            .eq("user_id", user_id)\
            .execute()

        if not result.data:
            return {}

        settings = result.data[0]

        # Decrypt Odoo password if it exists
        odoo_password = None
        if settings.get("odoo_encrypted_password"):
            try:
                odoo_password = self._decrypt_password(settings["odoo_encrypted_password"])
            except Exception as e:
                logger.error(f"Failed to decrypt Odoo password for user {user_id}: {e}")

        return {
            "outlook_tokens": settings.get("outlook_tokens"),
            "user_identifier": settings.get("user_identifier"),
            "odoo_url": settings.get("odoo_url"),
            "odoo_db": settings.get("odoo_db"),
            "odoo_username": settings.get("odoo_username"),
            "odoo_password": odoo_password,
            **(settings.get("settings_json") or {})
        }

    def update_user_settings(self, user_id: int, **kwargs):
        """Update user settings with encrypted Odoo password."""
        # Handle special columns
        outlook_tokens = kwargs.pop("outlook_tokens", None)
        user_identifier = kwargs.pop("user_identifier", None)
        odoo_url = kwargs.pop("odoo_url", None)
        odoo_db = kwargs.pop("odoo_db", None)
        odoo_username = kwargs.pop("odoo_username", None)
        odoo_password = kwargs.pop("odoo_password", None)

        # Get current settings
        result = self.supabase.client.table("user_settings")\
            .select("settings_json")\
            .eq("user_id", user_id)\
            .execute()

        current_settings = {}
        if result.data:
            current_settings = result.data[0].get("settings_json") or {}

        # Update settings JSON with remaining kwargs
        current_settings.update(kwargs)

        # Build update data
        update_data = {"settings_json": current_settings}

        if outlook_tokens is not None:
            update_data["outlook_tokens"] = outlook_tokens

        if user_identifier is not None:
            update_data["user_identifier"] = user_identifier

        if odoo_url is not None:
            update_data["odoo_url"] = odoo_url

        if odoo_db is not None:
            update_data["odoo_db"] = odoo_db

        if odoo_username is not None:
            update_data["odoo_username"] = odoo_username

        if odoo_password is not None:
            # Encrypt password before storing
            update_data["odoo_encrypted_password"] = self._encrypt_password(odoo_password)

        # Update settings
        self.supabase.client.table("user_settings")\
            .update(update_data)\
            .eq("user_id", user_id)\
            .execute()

    def list_users(self) -> List[Dict[str, Any]]:
        """List all users (excluding password hashes)."""
        result = self.supabase.client.table("users")\
            .select("id, email, name, role, created_at, last_login")\
            .execute()

        return [
            {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
                "created_at": user["created_at"],
                "last_login": user.get("last_login")
            }
            for user in result.data
        ]

    def mark_followup_complete(
        self,
        thread_id: str,
        conversation_id: str,
        user_id: int,
        completion_method: str = "manual_marked",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Mark a follow-up as completed."""
        try:
            result = self.supabase.client.table("followup_completions").insert({
                "thread_id": thread_id,
                "conversation_id": conversation_id,
                "completed_by_user_id": user_id,
                "completion_method": completion_method,
                "notes": notes
            }).execute()

            if result.data:
                return result.data[0]
            return {}
        except Exception as e:
            logger.error(f"Error marking follow-up complete: {e}")
            raise

    def get_completed_followups(self, thread_ids: Optional[List[str]] = None) -> List[str]:
        """Get list of completed thread IDs."""
        try:
            query = self.supabase.client.table("followup_completions").select("thread_id")

            if thread_ids:
                query = query.in_("thread_id", thread_ids)

            result = query.execute()
            return [item["thread_id"] for item in result.data]
        except Exception as e:
            logger.error(f"Error getting completed follow-ups: {e}")
            return []

    def is_followup_completed(self, thread_id: str) -> bool:
        """Check if a specific follow-up is completed."""
        try:
            result = self.supabase.client.table("followup_completions")\
                .select("id")\
                .eq("thread_id", thread_id)\
                .execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error checking follow-up completion: {e}")
            return False

    def save_report(
        self,
        user_id: int,
        analysis_type: str,
        report_type: str,
        report_period: str,
        result: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None,
        is_shared: bool = True
    ) -> str:
        """Save a scheduled report."""
        try:
            logger.info(f"Preparing to save report: type={report_type}, period={report_period}, user={user_id}")

            data = {
                "user_id": user_id,
                "analysis_type": analysis_type,
                "report_type": report_type,
                "report_period": report_period,
                "results": json.dumps(result),
                "parameters": json.dumps(parameters or {}),
                "is_shared": is_shared
            }

            logger.info(f"Inserting report into analysis_cache table")
            insert_result = self.supabase.client.table("analysis_cache").insert(data).execute()

            if insert_result.data:
                report_id = insert_result.data[0]["id"]
                logger.info(f"Report saved successfully to database with ID: {report_id}")
                return report_id
            else:
                logger.error(f"Report insert returned no data. Response: {insert_result}")
                return ""
        except Exception as e:
            logger.error(f"Error saving report: {e}", exc_info=True)
            raise

    def get_saved_reports(
        self,
        analysis_type: str = "proposal_followups",
        report_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all saved reports."""
        try:
            query = self.supabase.client.table("analysis_cache")\
                .select("*")\
                .eq("analysis_type", analysis_type)\
                .eq("is_shared", True)\
                .not_.is_("report_type", "null")\
                .order("created_at", desc=True)

            if report_type:
                query = query.eq("report_type", report_type)

            result = query.execute()

            return [
                {
                    "id": item["id"],
                    "report_type": item["report_type"],
                    "report_period": item["report_period"],
                    "created_at": item["created_at"],
                    "result": json.loads(item["results"]) if item.get("results") else {},
                    "parameters": json.loads(item["parameters"]) if item.get("parameters") else {}
                }
                for item in result.data
            ]
        except Exception as e:
            logger.error(f"Error getting saved reports: {e}")
            return []

    def delete_report(self, report_id: str) -> bool:
        """Delete a saved report by UUID."""
        try:
            result = self.supabase.client.table("analysis_cache")\
                .delete()\
                .eq("id", report_id)\
                .execute()

            return True
        except Exception as e:
            logger.error(f"Error deleting report {report_id}: {e}")
            return False

    def create_refresh_token(self, user_id: int, token: str, device_info: Optional[str] = None) -> int:
        """Create a new refresh token for a user (never expires unless manually revoked)."""
        try:
            result = self.supabase.client.table("refresh_tokens").insert({
                "user_id": user_id,
                "token": token,
                "device_info": device_info,
                "is_active": True
            }).execute()

            if result.data:
                return result.data[0]["id"]
            return 0
        except Exception as e:
            logger.error(f"Error creating refresh token: {e}")
            raise

    def get_refresh_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get refresh token details if it's valid and active."""
        try:
            result = self.supabase.client.table("refresh_tokens")\
                .select("*")\
                .eq("token", token)\
                .eq("is_active", True)\
                .execute()

            if not result.data:
                return None

            return result.data[0]
        except Exception as e:
            logger.error(f"Error getting refresh token: {e}")
            return None

    def revoke_refresh_token(self, token: str):
        """Revoke a refresh token."""
        try:
            self.supabase.client.table("refresh_tokens")\
                .update({"is_active": False})\
                .eq("token", token)\
                .execute()
        except Exception as e:
            logger.error(f"Error revoking refresh token: {e}")
            raise

    def revoke_all_user_refresh_tokens(self, user_id: int):
        """Revoke all refresh tokens for a user."""
        try:
            self.supabase.client.table("refresh_tokens")\
                .update({"is_active": False})\
                .eq("user_id", user_id)\
                .execute()
        except Exception as e:
            logger.error(f"Error revoking user refresh tokens: {e}")
            raise
