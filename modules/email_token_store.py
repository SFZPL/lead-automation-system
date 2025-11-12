"""Supabase-based storage for OAuth2 email tokens (multi-user support)."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from api.supabase_database import SupabaseDatabase

logger = logging.getLogger(__name__)


class EmailTokenStore:
    """Store and retrieve OAuth2 tokens for multiple users in Supabase."""

    def __init__(self, db: Optional[SupabaseDatabase] = None):
        """
        Initialize token store with Supabase backend.

        Args:
            db: SupabaseDatabase instance (creates new if not provided)
        """
        self.db = db if db else SupabaseDatabase()

    def save_tokens(
        self,
        user_identifier: str,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        user_email: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> bool:
        """
        Save OAuth2 tokens for a user in Supabase.

        Args:
            user_identifier: Unique identifier for user (e.g., email, Odoo user ID)
            access_token: OAuth2 access token
            refresh_token: OAuth2 refresh token
            expires_in: Token expiration in seconds
            user_email: User's email address (optional, for reference)
            user_name: User's display name (optional, for reference)

        Returns:
            True if saved successfully
        """
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            success = self.db.save_email_tokens(
                user_identifier=user_identifier,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                user_email=user_email,
                user_name=user_name
            )

            if success:
                logger.info(f"Saved tokens for user: {user_identifier}")
            return success

        except Exception as e:
            logger.error(f"Error saving tokens for {user_identifier}: {e}")
            return False

    def get_tokens(self, user_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve tokens for a user from Supabase.

        Args:
            user_identifier: Unique identifier for user

        Returns:
            Dictionary with token data, or None if not found
        """
        try:
            data = self.db.get_email_tokens(user_identifier)

            if not data:
                logger.debug(f"No tokens found for user: {user_identifier}")
                return None

            return data

        except Exception as e:
            logger.error(f"Error loading tokens for {user_identifier}: {e}")
            return None

    def is_token_expired(self, user_identifier: str) -> bool:
        """Check if user's access token is expired."""
        data = self.get_tokens(user_identifier)
        if not data:
            return True

        expires_at_str = data.get("expires_at")
        if not expires_at_str:
            return True

        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            # Add 5 minute buffer
            return datetime.utcnow() >= (expires_at - timedelta(minutes=5))
        except:
            return True

    def update_access_token(
        self,
        user_identifier: str,
        access_token: str,
        expires_in: int,
    ) -> bool:
        """Update just the access token (after refresh) in Supabase."""
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            success = self.db.update_email_access_token(
                user_identifier=user_identifier,
                access_token=access_token,
                expires_at=expires_at
            )

            if not success:
                logger.error(f"Cannot update token - no data found for {user_identifier}")

            return success
        except Exception as e:
            logger.error(f"Error updating token for {user_identifier}: {e}")
            return False

    def delete_tokens(self, user_identifier: str) -> bool:
        """Delete tokens for a user (e.g., on logout/revocation) from Supabase."""
        try:
            success = self.db.delete_email_tokens(user_identifier)
            if success:
                logger.info(f"Deleted tokens for user: {user_identifier}")
            return success
        except Exception as e:
            logger.error(f"Error deleting tokens for {user_identifier}: {e}")
            return False

    def list_authorized_users(self) -> list[Dict[str, Any]]:
        """List all users who have authorized email access from Supabase."""
        try:
            return self.db.list_authorized_email_users()
        except Exception as e:
            logger.error(f"Error listing authorized users: {e}")
            return []
