"""
Supabase client for PrezLab Leads application.
Handles connection to Supabase for analysis caching and user collaboration.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class SupabaseClient:
    """Client for interacting with Supabase database."""

    def __init__(self):
        """Initialize Supabase client with credentials from environment."""
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Use service role for backend

        if not self.url or not self.key:
            logger.warning("Supabase credentials not found. Caching will be disabled.")
            self.client: Optional[Client] = None
        else:
            try:
                # Create client with named parameters for better compatibility
                self.client = create_client(
                    supabase_url=self.url,
                    supabase_key=self.key
                )
                logger.info("✅ Supabase client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                self.client = None

    def is_connected(self) -> bool:
        """Check if Supabase client is connected."""
        return self.client is not None

    # ============================================================================
    # Analysis Cache Methods
    # ============================================================================

    def get_cached_analysis(
        self,
        user_id: int,
        analysis_type: str,
        parameters: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached analysis results.

        Args:
            user_id: User ID
            analysis_type: Type of analysis ('proposal_followups', etc.)
            parameters: Analysis parameters (days_back, no_response_days, etc.)

        Returns:
            Cached analysis data or None if not found/expired
        """
        if not self.client:
            return None

        try:
            # Query for matching cache entry
            result = (
                self.client.table("analysis_cache")
                .select("*")
                .eq("user_id", user_id)
                .eq("analysis_type", analysis_type)
                .contains("parameters", parameters)  # JSONB contains check
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if not result.data:
                logger.info(f"No cache found for user {user_id}, type {analysis_type}")
                return None

            cache_entry = result.data[0]

            # Check if expired
            if cache_entry.get("expires_at"):
                expires_at = datetime.fromisoformat(cache_entry["expires_at"].replace("Z", "+00:00"))
                if datetime.now(expires_at.tzinfo) > expires_at:
                    logger.info(f"Cache expired for user {user_id}, type {analysis_type}")
                    # Delete expired entry
                    self.delete_analysis_cache(cache_entry["id"])
                    return None

            logger.info(f"✅ Cache hit for user {user_id}, type {analysis_type}")
            return cache_entry["results"]

        except Exception as e:
            logger.error(f"Error retrieving cached analysis: {e}")
            return None

    def save_analysis_cache(
        self,
        user_id: int,
        analysis_type: str,
        parameters: Dict[str, Any],
        results: Dict[str, Any],
        cache_duration_days: Optional[int] = None
    ) -> bool:
        """
        Save analysis results to cache.

        Args:
            user_id: User ID
            analysis_type: Type of analysis
            parameters: Analysis parameters
            results: Analysis results to cache
            cache_duration_days: Cache expiration in days (None = no expiration)

        Returns:
            True if saved successfully
        """
        if not self.client:
            logger.warning("Supabase not connected. Cannot save cache.")
            return False

        try:
            expires_at = None
            if cache_duration_days:
                expires_at = (datetime.now() + timedelta(days=cache_duration_days)).isoformat()

            data = {
                "user_id": user_id,
                "analysis_type": analysis_type,
                "parameters": parameters,
                "results": results,
                "expires_at": expires_at,
                "is_shared": False
            }

            result = self.client.table("analysis_cache").insert(data).execute()

            if result.data:
                logger.info(f"✅ Analysis cached for user {user_id}, type {analysis_type}, expires: {expires_at}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error saving analysis cache: {e}")
            return False

    def delete_analysis_cache(self, cache_id: str) -> bool:
        """Delete a specific cache entry."""
        if not self.client:
            return False

        try:
            self.client.table("analysis_cache").delete().eq("id", cache_id).execute()
            logger.info(f"Deleted cache entry: {cache_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting cache: {e}")
            return False

    def clear_user_cache(
        self,
        user_id: int,
        analysis_type: Optional[str] = None
    ) -> int:
        """
        Clear all cache entries for a user.

        Args:
            user_id: User ID
            analysis_type: Optional - only clear this analysis type

        Returns:
            Number of entries deleted
        """
        if not self.client:
            return 0

        try:
            query = self.client.table("analysis_cache").delete().eq("user_id", user_id)

            if analysis_type:
                query = query.eq("analysis_type", analysis_type)

            result = query.execute()
            count = len(result.data) if result.data else 0
            logger.info(f"Cleared {count} cache entries for user {user_id}")
            return count

        except Exception as e:
            logger.error(f"Error clearing user cache: {e}")
            return 0

    # ============================================================================
    # Lead Assignment Methods
    # ============================================================================

    def create_lead_assignment(
        self,
        conversation_id: str,
        external_email: str,
        subject: str,
        assigned_from_user_id: int,
        lead_data: Dict[str, Any],
        assigned_to_user_id: Optional[int] = None,
        assigned_to_teams_id: Optional[str] = None,
        assigned_to_name: Optional[str] = None,
        assigned_to_email: Optional[str] = None,
        notes: Optional[str] = None,
        analysis_cache_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new lead assignment.

        Args:
            conversation_id: Email conversation ID
            external_email: External contact email
            subject: Email subject
            assigned_from_user_id: User assigning the lead
            lead_data: Full lead/thread data
            assigned_to_user_id: User receiving the assignment (database user ID)
            assigned_to_teams_id: Azure AD user ID for Teams users
            assigned_to_name: Display name for Teams users
            assigned_to_email: Email address for Teams users
            notes: Optional notes from assignor
            analysis_cache_id: Optional reference to analysis cache

        Returns:
            Created assignment record or None
        """
        if not self.client:
            return None

        try:
            data = {
                "conversation_id": conversation_id,
                "external_email": external_email,
                "subject": subject,
                "assigned_from_user_id": assigned_from_user_id,
                "lead_data": lead_data,
                "notes": notes,
                "analysis_cache_id": analysis_cache_id,
                "status": "pending"
            }

            # Add user ID or Teams info
            if assigned_to_user_id:
                data["assigned_to_user_id"] = assigned_to_user_id
            if assigned_to_teams_id:
                data["assigned_to_teams_id"] = assigned_to_teams_id
            if assigned_to_name:
                data["assigned_to_name"] = assigned_to_name
            if assigned_to_email:
                data["assigned_to_email"] = assigned_to_email

            result = self.client.table("lead_assignments").insert(data).execute()

            if result.data:
                assignee_info = assigned_to_name or str(assigned_to_user_id)
                logger.info(f"✅ Lead assigned from user {assigned_from_user_id} to {assignee_info}")
                return result.data[0]
            return None

        except Exception as e:
            logger.error(f"Error creating lead assignment: {e}")
            return None

    def get_received_assignments(
        self,
        user_id: int,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get assignments received by a user."""
        if not self.client:
            return []

        try:
            query = (
                self.client.table("lead_assignments")
                .select("*")
                .eq("assigned_to_user_id", user_id)
                .order("assigned_at", desc=True)
            )

            if status:
                query = query.eq("status", status)

            result = query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"Error fetching received assignments: {e}")
            return []

    def get_sent_assignments(
        self,
        user_id: int,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get assignments sent by a user."""
        if not self.client:
            return []

        try:
            query = (
                self.client.table("lead_assignments")
                .select("*")
                .eq("assigned_from_user_id", user_id)
                .order("assigned_at", desc=True)
            )

            if status:
                query = query.eq("status", status)

            result = query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"Error fetching sent assignments: {e}")
            return []

    def update_assignment_status(
        self,
        assignment_id: str,
        status: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Update assignment status.

        Args:
            assignment_id: Assignment UUID
            status: New status ('accepted', 'completed', 'rejected')
            notes: Optional notes

        Returns:
            True if updated successfully
        """
        if not self.client:
            return False

        try:
            update_data = {"status": status}
            if notes:
                update_data["notes"] = notes

            result = (
                self.client.table("lead_assignments")
                .update(update_data)
                .eq("id", assignment_id)
                .execute()
            )

            if result.data:
                logger.info(f"✅ Assignment {assignment_id} updated to {status}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error updating assignment status: {e}")
            return False

    # ============================================================================
    # User Preferences Methods
    # ============================================================================

    def get_user_preferences(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user preferences."""
        if not self.client:
            return None

        try:
            result = (
                self.client.table("user_preferences")
                .select("*")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            logger.error(f"Error fetching user preferences: {e}")
            return None

    def upsert_user_preferences(
        self,
        user_id: int,
        preferences: Dict[str, Any]
    ) -> bool:
        """Create or update user preferences."""
        if not self.client:
            return False

        try:
            data = {"user_id": user_id, **preferences}
            result = self.client.table("user_preferences").upsert(data).execute()

            if result.data:
                logger.info(f"✅ Preferences saved for user {user_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error upserting user preferences: {e}")
            return False

    # ============================================================================
    # Utility Methods
    # ============================================================================

    def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries. Returns number of deleted entries."""
        if not self.client:
            return 0

        try:
            result = self.client.rpc("cleanup_expired_cache").execute()
            count = result.data if isinstance(result.data, int) else 0
            logger.info(f"Cleaned up {count} expired cache entries")
            return count
        except Exception as e:
            logger.error(f"Error cleaning up expired cache: {e}")
            return 0


# Global singleton instance
_supabase_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """Get or create global Supabase client instance."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client
