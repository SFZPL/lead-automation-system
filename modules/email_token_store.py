"""Simple file-based storage for OAuth2 email tokens (multi-user support)."""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EmailTokenStore:
    """Store and retrieve OAuth2 tokens for multiple users."""

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize token store.

        Args:
            storage_dir: Directory to store token files (default: .email_tokens/)
        """
        if storage_dir is None:
            # Store in project root by default
            project_root = Path(__file__).parent.parent
            storage_dir = project_root / ".email_tokens"

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True, parents=True)

        # Add to .gitignore to prevent committing tokens
        gitignore_path = project_root / ".gitignore"
        gitignore_entry = ".email_tokens/\n"
        try:
            if gitignore_path.exists():
                content = gitignore_path.read_text()
                if ".email_tokens" not in content:
                    with open(gitignore_path, "a") as f:
                        f.write(gitignore_entry)
            else:
                gitignore_path.write_text(gitignore_entry)
        except Exception as e:
            logger.warning(f"Could not update .gitignore: {e}")

    def _get_user_file(self, user_identifier: str) -> Path:
        """Get the file path for a user's tokens."""
        # Sanitize identifier for filesystem
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_identifier)
        return self.storage_dir / f"{safe_id}.json"

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
        Save OAuth2 tokens for a user.

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
            expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

            data = {
                "user_identifier": user_identifier,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "user_email": user_email,
                "user_name": user_name,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            user_file = self._get_user_file(user_identifier)
            with open(user_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved tokens for user: {user_identifier}")
            return True

        except Exception as e:
            logger.error(f"Error saving tokens for {user_identifier}: {e}")
            return False

    def get_tokens(self, user_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve tokens for a user.

        Args:
            user_identifier: Unique identifier for user

        Returns:
            Dictionary with token data, or None if not found
        """
        try:
            user_file = self._get_user_file(user_identifier)

            if not user_file.exists():
                logger.debug(f"No tokens found for user: {user_identifier}")
                return None

            with open(user_file, "r") as f:
                data = json.load(f)

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
        """Update just the access token (after refresh)."""
        data = self.get_tokens(user_identifier)
        if not data:
            logger.error(f"Cannot update token - no data found for {user_identifier}")
            return False

        data["access_token"] = access_token
        data["expires_at"] = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
        data["updated_at"] = datetime.utcnow().isoformat()

        try:
            user_file = self._get_user_file(user_identifier)
            with open(user_file, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error updating token for {user_identifier}: {e}")
            return False

    def delete_tokens(self, user_identifier: str) -> bool:
        """Delete tokens for a user (e.g., on logout/revocation)."""
        try:
            user_file = self._get_user_file(user_identifier)
            if user_file.exists():
                user_file.unlink()
                logger.info(f"Deleted tokens for user: {user_identifier}")
            return True
        except Exception as e:
            logger.error(f"Error deleting tokens for {user_identifier}: {e}")
            return False

    def list_authorized_users(self) -> list[Dict[str, Any]]:
        """List all users who have authorized email access."""
        users = []
        try:
            for token_file in self.storage_dir.glob("*.json"):
                try:
                    with open(token_file, "r") as f:
                        data = json.load(f)
                        users.append({
                            "user_identifier": data.get("user_identifier"),
                            "user_email": data.get("user_email"),
                            "user_name": data.get("user_name"),
                            "created_at": data.get("created_at"),
                            "is_expired": self.is_token_expired(data.get("user_identifier", "")),
                        })
                except Exception as e:
                    logger.warning(f"Error reading token file {token_file}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error listing authorized users: {e}")

        return users
