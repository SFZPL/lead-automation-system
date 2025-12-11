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

    def get_completed_followups_with_timestamps(self) -> Dict[str, str]:
        """Get map of completed thread IDs to their completion timestamps."""
        try:
            result = self.supabase.client.table("followup_completions")\
                .select("thread_id, conversation_id, completed_at")\
                .execute()

            # Return dict mapping conversation_id to completed_at timestamp
            return {
                item["conversation_id"]: item["completed_at"]
                for item in result.data
            }
        except Exception as e:
            logger.error(f"Error getting completed follow-ups with timestamps: {e}")
            return {}

    def reopen_completed_followup(self, conversation_id: str) -> bool:
        """Delete completion record to reopen a thread."""
        try:
            self.supabase.client.table("followup_completions")\
                .delete()\
                .eq("conversation_id", conversation_id)\
                .execute()
            logger.info(f"Reopened completed thread: {conversation_id}")
            return True
        except Exception as e:
            logger.error(f"Error reopening follow-up: {e}")
            return False

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

    def favorite_followup(self, thread_id: str, conversation_id: str) -> bool:
        """Mark a follow-up thread as favorited."""
        try:
            self.supabase.client.table("followup_favorites").insert({
                "thread_id": thread_id,
                "conversation_id": conversation_id,
                "favorited_at": datetime.now().isoformat()
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Error favoriting follow-up: {e}")
            return False

    def unfavorite_followup(self, thread_id: str) -> bool:
        """Remove favorite from a follow-up thread."""
        try:
            self.supabase.client.table("followup_favorites")\
                .delete()\
                .eq("thread_id", thread_id)\
                .execute()
            return True
        except Exception as e:
            logger.error(f"Error unfavoriting follow-up: {e}")
            return False

    def get_favorited_followups(self, thread_ids: Optional[List[str]] = None) -> List[str]:
        """Get list of favorited thread IDs."""
        try:
            query = self.supabase.client.table("followup_favorites").select("thread_id")

            if thread_ids:
                query = query.in_("thread_id", thread_ids)

            result = query.execute()
            return [item["thread_id"] for item in result.data]
        except Exception as e:
            logger.error(f"Error getting favorited follow-ups: {e}")
            return []

    # NDA Analysis Methods
    def create_nda_document(
        self,
        user_id: str,
        file_name: str,
        file_size: int,
        file_content: str,
        language: Optional[str] = None,
        original_pdf_base64: Optional[str] = None
    ) -> Optional[str]:
        """Create a new NDA document record."""
        try:
            data = {
                "user_id": user_id,
                "file_name": file_name,
                "file_size": file_size,
                "file_content": file_content,
                "language": language,
                "status": "pending"
            }
            if original_pdf_base64:
                data["original_pdf_base64"] = original_pdf_base64
            result = self.supabase.client.table("nda_documents").insert(data).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Error creating NDA document: {e}")
            return None

    def update_nda_analysis(
        self,
        nda_id: str,
        risk_category: str,
        risk_score: int,
        summary: str,
        questionable_clauses: List[Dict[str, Any]],
        analysis_details: Dict[str, Any],
        language: Optional[str] = None
    ) -> bool:
        """Update NDA document with analysis results."""
        try:
            update_data = {
                "analyzed_at": datetime.now().isoformat(),
                "risk_category": risk_category,
                "risk_score": risk_score,
                "summary": summary,
                "questionable_clauses": questionable_clauses,
                "analysis_details": analysis_details,
                "status": "completed"
            }

            if language:
                update_data["language"] = language

            self.supabase.client.table("nda_documents")\
                .update(update_data)\
                .eq("id", nda_id)\
                .execute()
            return True
        except Exception as e:
            logger.error(f"Error updating NDA analysis: {e}")
            return False

    def update_nda_status(self, nda_id: str, status: str, error_message: Optional[str] = None) -> bool:
        """Update NDA document status."""
        try:
            update_data = {"status": status}
            if error_message:
                update_data["error_message"] = error_message

            self.supabase.client.table("nda_documents")\
                .update(update_data)\
                .eq("id", nda_id)\
                .execute()
            return True
        except Exception as e:
            logger.error(f"Error updating NDA status: {e}")
            return False

    def get_nda_documents(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get NDA documents for a user."""
        try:
            result = self.supabase.client.table("nda_documents")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("uploaded_at", desc=True)\
                .limit(limit)\
                .execute()
            return result.data
        except Exception as e:
            logger.error(f"Error getting NDA documents: {e}")
            return []

    def get_nda_document(self, nda_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific NDA document by ID."""
        try:
            result = self.supabase.client.table("nda_documents")\
                .select("*")\
                .eq("id", nda_id)\
                .single()\
                .execute()
            return result.data
        except Exception as e:
            logger.error(f"Error getting NDA document: {e}")
            return None

    def delete_nda_document(self, nda_id: str) -> bool:
        """Delete an NDA document."""
        try:
            self.supabase.client.table("nda_documents")\
                .delete()\
                .eq("id", nda_id)\
                .execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting NDA document: {e}")
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

            # Limit the size of the result to avoid timeout
            # Keep only summary and truncate large lists
            result_to_save = self._truncate_report_for_storage(result)

            # Serialize and check size
            results_json = json.dumps(result_to_save)
            params_json = json.dumps(parameters or {})
            total_size_kb = (len(results_json) + len(params_json)) / 1024

            logger.info(f"Report data size: {total_size_kb:.1f} KB (results: {len(results_json)/1024:.1f} KB)")

            # Warn if still large (> 500 KB can be slow)
            if total_size_kb > 500:
                logger.warning(f"Report data is large ({total_size_kb:.1f} KB), may timeout on insert")

            data = {
                "user_id": user_id,
                "analysis_type": analysis_type,
                "report_type": report_type,
                "report_period": report_period,
                "results": results_json,
                "parameters": params_json,
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

    def _truncate_report_for_storage(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Truncate large report data to avoid database timeouts."""
        if not isinstance(result, dict):
            return result

        # Deep copy to avoid modifying the original
        import copy
        truncated = copy.deepcopy(result)

        # Limit follow_ups list to newest 100 items (previously worked with 110)
        if "follow_ups" in truncated and isinstance(truncated["follow_ups"], list):
            original_count = len(truncated["follow_ups"])
            if original_count > 100:
                # Keep the last 100 (newest) items, drop oldest
                truncated["follow_ups"] = truncated["follow_ups"][-100:]
                truncated["_truncated"] = True
                truncated["_original_count"] = original_count
                logger.info(f"Truncated follow_ups from {original_count} to newest 100 for storage")

        # Truncate long text fields in each follow-up
        if "follow_ups" in truncated and isinstance(truncated["follow_ups"], list):
            for fu in truncated["follow_ups"]:
                if isinstance(fu, dict):
                    # Limit AI suggestions to 500 chars
                    if "ai_suggestion" in fu and isinstance(fu["ai_suggestion"], str) and len(fu["ai_suggestion"]) > 500:
                        fu["ai_suggestion"] = fu["ai_suggestion"][:500] + "..."
                    # Limit notes to 300 chars
                    if "notes" in fu and isinstance(fu["notes"], str) and len(fu["notes"]) > 300:
                        fu["notes"] = fu["notes"][:300] + "..."
                    # Remove large fields that aren't needed for display
                    fu.pop("conversation_history", None)
                    fu.pop("full_email_body", None)
                    fu.pop("raw_messages", None)
                    # Truncate subject if too long
                    if "subject" in fu and isinstance(fu["subject"], str) and len(fu["subject"]) > 200:
                        fu["subject"] = fu["subject"][:200] + "..."
                    # Truncate preview if exists
                    if "preview" in fu and isinstance(fu["preview"], str) and len(fu["preview"]) > 300:
                        fu["preview"] = fu["preview"][:300] + "..."

        # Remove raw data that isn't needed for the saved report display
        truncated.pop("raw_threads", None)
        truncated.pop("debug_info", None)

        return truncated

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
                .order("created_at", desc=True)

            # Only filter by report_type if explicitly requested
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

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get a single report by UUID."""
        try:
            result = self.supabase.client.table("analysis_cache")\
                .select("*")\
                .eq("id", report_id)\
                .execute()

            if not result.data:
                return None

            item = result.data[0]
            return {
                "id": item["id"],
                "report_type": item["report_type"],
                "report_period": item["report_period"],
                "created_at": item["created_at"],
                "report_data": json.loads(item["results"]) if item.get("results") else {},
                "parameters": json.loads(item["parameters"]) if item.get("parameters") else {}
            }
        except Exception as e:
            logger.error(f"Error getting report {report_id}: {e}")
            return None

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

    # ============================================================================
    # EMAIL TOKEN MANAGEMENT (Outlook OAuth)
    # ============================================================================

    def save_email_tokens(
        self,
        user_identifier: str,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
        user_email: Optional[str] = None,
        user_name: Optional[str] = None
    ) -> bool:
        """Save or update Outlook OAuth tokens for a user."""
        try:
            data = {
                "user_identifier": user_identifier,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at.isoformat(),
                "user_email": user_email,
                "user_name": user_name,
                "updated_at": datetime.utcnow().isoformat()
            }

            # Upsert (insert or update if exists)
            result = self.supabase.client.table("email_tokens")\
                .upsert(data, on_conflict="user_identifier")\
                .execute()

            return bool(result.data)
        except Exception as e:
            logger.error(f"Error saving email tokens for {user_identifier}: {e}")
            return False

    def get_email_tokens(self, user_identifier: str) -> Optional[Dict[str, Any]]:
        """Get Outlook OAuth tokens for a user."""
        try:
            result = self.supabase.client.table("email_tokens")\
                .select("*")\
                .eq("user_identifier", user_identifier)\
                .execute()

            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting email tokens for {user_identifier}: {e}")
            return None

    def update_email_access_token(
        self,
        user_identifier: str,
        access_token: str,
        expires_at: datetime
    ) -> bool:
        """Update just the access token after refresh."""
        try:
            result = self.supabase.client.table("email_tokens")\
                .update({
                    "access_token": access_token,
                    "expires_at": expires_at.isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                })\
                .eq("user_identifier", user_identifier)\
                .execute()

            return bool(result.data)
        except Exception as e:
            logger.error(f"Error updating email access token for {user_identifier}: {e}")
            return False

    def delete_email_tokens(self, user_identifier: str) -> bool:
        """Delete Outlook OAuth tokens for a user."""
        try:
            self.supabase.client.table("email_tokens")\
                .delete()\
                .eq("user_identifier", user_identifier)\
                .execute()

            return True
        except Exception as e:
            logger.error(f"Error deleting email tokens for {user_identifier}: {e}")
            return False

    def list_authorized_email_users(self) -> List[Dict[str, Any]]:
        """List all users who have authorized email access."""
        try:
            result = self.supabase.client.table("email_tokens")\
                .select("user_identifier, user_email, user_name, created_at, expires_at")\
                .execute()

            if result.data:
                # Add is_expired flag
                now = datetime.utcnow()
                for user in result.data:
                    expires_at_str = user.get("expires_at")
                    if expires_at_str:
                        try:
                            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                            user["is_expired"] = now >= expires_at
                        except:
                            user["is_expired"] = True
                    else:
                        user["is_expired"] = True

                return result.data
            return []
        except Exception as e:
            logger.error(f"Error listing authorized email users: {e}")
            return []
