"""Authentication service with JWT tokens."""

import secrets
import hashlib
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, Header

from .database import Database
from .supabase_database import SupabaseDatabase


class AuthService:
    """Handles user authentication and JWT token management."""

    # In production, this should be an environment variable
    SECRET_KEY = secrets.token_urlsafe(32)
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        return AuthService.hash_password(password) == password_hash

    def create_access_token(self, user_id: int, email: str, role: str) -> str:
        """Create a JWT access token."""
        expire = datetime.utcnow() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(user_id),
            "email": email,
            "role": role,
            "exp": expire
        }
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidSignatureError:
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate a user with email and password."""
        user = self.db.get_user_by_email(email)
        if not user:
            return None

        if not self.verify_password(password, user["password_hash"]):
            return None

        # Update last login
        self.db.update_last_login(user["id"])

        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"]
        }

    def register_user(self, email: str, name: str, password: str, role: str = "user") -> int:
        """Register a new user."""
        password_hash = self.hash_password(password)
        return self.db.create_user(email, name, password_hash, role)

    def get_current_user(self, authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
        """Get current user from Authorization header."""
        if not authorization:
            raise HTTPException(status_code=401, detail="Not authenticated")

        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        payload = self.verify_token(token)
        user_id = int(payload.get("sub"))

        user = self.db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"]
        }


# Global database instance - Use Supabase
_db = SupabaseDatabase()
_auth_service = AuthService(_db)


def get_auth_service() -> AuthService:
    """Dependency to get auth service."""
    return _auth_service


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Dependency to get current authenticated user."""
    return _auth_service.get_current_user(authorization)


def get_database():
    """Dependency to get database."""
    return _db
