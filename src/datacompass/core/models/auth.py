"""Authentication models for users, API keys, sessions, and tokens."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datacompass.core.models.base import Base, TimestampMixin

# =============================================================================
# SQLAlchemy Models
# =============================================================================


class User(Base, TimestampMixin):
    """User account for authentication.

    Supports both local password auth and external provider auth (OIDC/LDAP).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email!r})>"


class APIKey(Base):
    """API key for programmatic access.

    Keys are stored as a prefix (for identification) and a hash (for verification).
    The full key is only shown once at creation time.
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, name={self.name!r}, prefix={self.key_prefix!r})>"


class Session(Base):
    """User session for web/CLI access.

    Sessions track active logins and support session management (list, revoke).
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session(id={self.id[:8]}..., user_id={self.user_id})>"


class RefreshToken(Base):
    """Refresh token for obtaining new access tokens.

    Tokens are stored as hashes. The replaced_by field supports token rotation.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    replaced_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id})>"


# =============================================================================
# Pydantic Schemas
# =============================================================================


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    email: str = Field(..., min_length=3, pattern=r".+@.+")
    password: str | None = None
    username: str | None = None
    display_name: str | None = None
    is_superuser: bool = False


class UserResponse(BaseModel):
    """Schema for user response (excludes sensitive data)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str | None = None
    display_name: str | None = None
    external_provider: str | None = None
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class APIKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] | None = None
    expires_days: int | None = Field(default=None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """Schema for API key response (excludes hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    key_prefix: str
    scopes: list[str] | None = None
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    is_active: bool
    created_at: datetime


class APIKeyCreated(BaseModel):
    """Schema for newly created API key (includes full key, shown only once)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    key: str  # Full key, only shown once at creation
    key_prefix: str
    scopes: list[str] | None = None
    expires_at: datetime | None = None
    created_at: datetime


class LoginRequest(BaseModel):
    """Schema for login request."""

    email: str = Field(..., min_length=3, pattern=r".+@.+")
    password: str


class TokenResponse(BaseModel):
    """Schema for token response after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until access token expires


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str


class AuthStatusResponse(BaseModel):
    """Schema for authentication status response."""

    auth_mode: str
    is_authenticated: bool = False
    user: UserResponse | None = None
