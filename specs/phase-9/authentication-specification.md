# Data Compass - Authentication Specification

## Executive Summary

This specification defines a **pluggable authentication system** for Data Compass that works in development (local username/password) and production (enterprise SSO via OAuth2/OIDC). The design follows Data Compass's terminal-first philosophy: authentication works headlessly via CLI before being exposed through the API and web UI.

### Goals

1. **Pluggable providers** - Swap authentication backends without changing application code
2. **Development-friendly** - Local auth with no external dependencies for dev/testing
3. **Enterprise-ready** - Support OAuth2/OIDC for corporate identity providers (Azure AD, Okta, etc.)
4. **CLI-first** - API keys and device flow for terminal access
5. **Incremental adoption** - Can run without auth (current state) or with auth enforced

---

## 1. Authentication Architecture

### 1.1 Provider Pattern

Authentication is handled by pluggable providers that implement a common interface:

```
┌─────────────────────────────────────────────────────────────┐
│                  AuthService (core)                         │
│         Coordinates authentication + session mgmt           │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                  AuthProvider (interface)                   │
├─────────────────────────────────────────────────────────────┤
│  LocalAuthProvider   │  OIDCAuthProvider  │  LDAPProvider  │
│  (dev/simple)        │  (enterprise SSO)  │  (legacy)      │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Auth Modes

| Mode | Provider | Use Case |
|------|----------|----------|
| `disabled` | None | Current behavior, no auth required |
| `local` | LocalAuthProvider | Development, small teams, testing |
| `oidc` | OIDCAuthProvider | Enterprise SSO (Azure AD, Okta, Google) |
| `ldap` | LDAPAuthProvider | Legacy corporate directories |

Configuration via environment:
```bash
DATACOMPASS_AUTH_MODE=local           # or: disabled, oidc, ldap
DATACOMPASS_AUTH_PROVIDER_CONFIG=...  # Provider-specific config (JSON or path)
```

### 1.3 Session & Token Strategy

| Context | Authentication Method |
|---------|----------------------|
| Web UI | Session cookies (httponly, secure) |
| API (programmatic) | Bearer tokens (JWT) |
| CLI | API keys (long-lived) or device flow (short-lived) |

---

## 2. Database Schema

### 2.1 Core Auth Tables

```sql
-- Migration: 007_authentication.py

-- Users table (local provider stores credentials, OIDC stores identity mapping)
CREATE TABLE users (
    id INTEGER PRIMARY KEY,

    -- Identity
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) UNIQUE,
    display_name VARCHAR(255),

    -- Local auth (null for OIDC-only users)
    password_hash VARCHAR(255),

    -- External identity (for OIDC/LDAP)
    external_provider VARCHAR(50),      -- 'azure_ad', 'okta', 'google', etc.
    external_id VARCHAR(255),           -- Provider's user ID

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

CREATE UNIQUE INDEX ix_users_external ON users(external_provider, external_id)
    WHERE external_provider IS NOT NULL;

-- API Keys for CLI/programmatic access
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Key identity
    name VARCHAR(100) NOT NULL,         -- "My laptop", "CI/CD", etc.
    key_prefix VARCHAR(8) NOT NULL,     -- First 8 chars for identification
    key_hash VARCHAR(255) NOT NULL,     -- bcrypt hash of full key

    -- Permissions
    scopes TEXT,                        -- JSON array: ["read", "write", "admin"]

    -- Lifecycle
    expires_at TIMESTAMP,               -- NULL = never expires
    last_used_at TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_api_keys_user ON api_keys(user_id);
CREATE INDEX ix_api_keys_prefix ON api_keys(key_prefix);

-- Sessions for web UI (optional - can use stateless JWT instead)
CREATE TABLE sessions (
    id VARCHAR(64) PRIMARY KEY,         -- Secure random token
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Session data
    user_agent VARCHAR(500),
    ip_address VARCHAR(45),

    -- Lifecycle
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_sessions_user ON sessions(user_id);
CREATE INDEX ix_sessions_expires ON sessions(expires_at);

-- Refresh tokens (for token rotation)
CREATE TABLE refresh_tokens (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,

    -- Rotation tracking
    replaced_by INTEGER REFERENCES refresh_tokens(id),

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_refresh_tokens_user ON refresh_tokens(user_id);
```

### 2.2 RBAC Tables (Deferred to Phase 10)

Role-based access control is covered in the Governance phase. For now, authentication provides:
- `is_superuser` flag for admin access
- API key `scopes` for programmatic access control

---

## 3. Core Library

### 3.1 Models

```python
# src/datacompass/core/models/auth.py

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from datacompass.core.models.base import Base


class User(Base):
    """User account model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=True)
    display_name = Column(String(255))

    # Local auth
    password_hash = Column(String(255))

    # External identity
    external_provider = Column(String(50))
    external_id = Column(String(255))

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)

    # Relationships
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")


class APIKey(Base):
    """API key for programmatic access."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(100), nullable=False)
    key_prefix = Column(String(8), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False)

    scopes = Column(Text)  # JSON array

    expires_at = Column(DateTime)
    last_used_at = Column(DateTime)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="api_keys")


# Pydantic schemas for API
class UserCreate(BaseModel):
    email: EmailStr
    username: str | None = None
    display_name: str | None = None
    password: str | None = None  # Required for local auth

class UserResponse(BaseModel):
    id: int
    email: str
    username: str | None
    display_name: str | None
    is_active: bool
    is_superuser: bool
    external_provider: str | None
    created_at: datetime
    last_login_at: datetime | None

    class Config:
        from_attributes = True

class APIKeyCreate(BaseModel):
    name: str
    scopes: list[str] = ["read"]
    expires_in_days: int | None = None  # None = never expires

class APIKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class APIKeyCreated(APIKeyResponse):
    """Response when creating a new API key - includes the full key (only shown once)."""
    key: str  # Full key, only returned on creation

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None

class LoginRequest(BaseModel):
    email: str
    password: str
```

### 3.2 Auth Provider Interface

```python
# src/datacompass/core/auth/providers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from datacompass.core.models.auth import User


@dataclass
class AuthResult:
    """Result of an authentication attempt."""
    success: bool
    user: User | None = None
    error: str | None = None
    needs_registration: bool = False
    external_claims: dict[str, Any] | None = None  # For OIDC


class AuthProvider(ABC):
    """Base class for authentication providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier for this provider (e.g., 'local', 'azure_ad')."""
        pass

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """
        Authenticate a user with the given credentials.

        For local auth: {"email": "...", "password": "..."}
        For OIDC: {"code": "...", "state": "..."}
        """
        pass

    @abstractmethod
    async def validate_token(self, token: str) -> AuthResult:
        """Validate an access token and return the associated user."""
        pass

    def supports_password_auth(self) -> bool:
        """Whether this provider supports username/password authentication."""
        return False

    def supports_oauth_flow(self) -> bool:
        """Whether this provider supports OAuth2/OIDC flows."""
        return False

    def get_oauth_authorize_url(self, state: str, redirect_uri: str) -> str | None:
        """Get the OAuth2 authorization URL for initiating login."""
        return None
```

### 3.3 Local Auth Provider

```python
# src/datacompass/core/auth/providers/local.py

import secrets
from datetime import datetime, timedelta
from typing import Any

import bcrypt
import jwt
from sqlalchemy.orm import Session

from datacompass.core.auth.providers.base import AuthProvider, AuthResult
from datacompass.core.models.auth import User
from datacompass.core.repositories.auth import UserRepository
from datacompass.config import settings


class LocalAuthProvider(AuthProvider):
    """Local username/password authentication."""

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    @property
    def provider_name(self) -> str:
        return "local"

    def supports_password_auth(self) -> bool:
        return True

    async def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """Authenticate with email and password."""
        email = credentials.get("email")
        password = credentials.get("password")

        if not email or not password:
            return AuthResult(success=False, error="Email and password required")

        user = self.user_repo.get_by_email(email)
        if not user:
            return AuthResult(success=False, error="Invalid credentials")

        if not user.is_active:
            return AuthResult(success=False, error="Account is disabled")

        if not user.password_hash:
            return AuthResult(success=False, error="Password login not enabled")

        if not self._verify_password(password, user.password_hash):
            return AuthResult(success=False, error="Invalid credentials")

        # Update last login
        user.last_login_at = datetime.utcnow()
        self.session.commit()

        return AuthResult(success=True, user=user)

    async def validate_token(self, token: str) -> AuthResult:
        """Validate a JWT access token."""
        try:
            payload = jwt.decode(
                token,
                settings.auth_secret_key,
                algorithms=["HS256"]
            )
            user_id = payload.get("sub")
            if not user_id:
                return AuthResult(success=False, error="Invalid token")

            user = self.user_repo.get_by_id(int(user_id))
            if not user or not user.is_active:
                return AuthResult(success=False, error="User not found or inactive")

            return AuthResult(success=True, user=user)
        except jwt.ExpiredSignatureError:
            return AuthResult(success=False, error="Token expired")
        except jwt.InvalidTokenError:
            return AuthResult(success=False, error="Invalid token")

    def create_user(self, email: str, password: str, **kwargs) -> User:
        """Create a new local user."""
        password_hash = self._hash_password(password)
        return self.user_repo.create(
            email=email,
            password_hash=password_hash,
            **kwargs
        )

    def _hash_password(self, password: str) -> str:
        """Hash a password with bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode(), password_hash.encode())
```

### 3.4 OIDC Auth Provider

```python
# src/datacompass/core/auth/providers/oidc.py

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy.orm import Session

from datacompass.core.auth.providers.base import AuthProvider, AuthResult
from datacompass.core.models.auth import User
from datacompass.core.repositories.auth import UserRepository


@dataclass
class OIDCConfig:
    """Configuration for an OIDC identity provider."""
    provider_name: str           # 'azure_ad', 'okta', 'google'
    client_id: str
    client_secret: str
    issuer: str                  # e.g., 'https://login.microsoftonline.com/{tenant}/v2.0'
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str | None = None
    jwks_uri: str | None = None
    scopes: list[str] = None

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = ["openid", "email", "profile"]


class OIDCAuthProvider(AuthProvider):
    """OAuth2/OIDC authentication for enterprise identity providers."""

    def __init__(self, session: Session, config: OIDCConfig):
        self.session = session
        self.config = config
        self.user_repo = UserRepository(session)
        self._jwks_client = None

    @property
    def provider_name(self) -> str:
        return self.config.provider_name

    def supports_oauth_flow(self) -> bool:
        return True

    def get_oauth_authorize_url(self, state: str, redirect_uri: str) -> str:
        """Generate the authorization URL to redirect users to."""
        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.config.scopes),
            "state": state,
        }
        return f"{self.config.authorization_endpoint}?{urlencode(params)}"

    async def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """
        Exchange authorization code for tokens and authenticate user.

        Credentials should contain:
        - code: Authorization code from OAuth callback
        - redirect_uri: The redirect URI used in the auth request
        """
        code = credentials.get("code")
        redirect_uri = credentials.get("redirect_uri")

        if not code:
            return AuthResult(success=False, error="Authorization code required")

        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                self.config.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )

        if token_response.status_code != 200:
            return AuthResult(success=False, error="Failed to exchange code for tokens")

        tokens = token_response.json()
        id_token = tokens.get("id_token")

        # Decode and validate ID token
        try:
            claims = await self._decode_id_token(id_token)
        except Exception as e:
            return AuthResult(success=False, error=f"Invalid ID token: {e}")

        # Extract user info from claims
        external_id = claims.get("sub")
        email = claims.get("email")
        name = claims.get("name") or claims.get("preferred_username")

        if not external_id or not email:
            return AuthResult(success=False, error="Missing required claims (sub, email)")

        # Find or create user
        user = self.user_repo.get_by_external_id(self.provider_name, external_id)

        if not user:
            # Check if user exists by email (might have been pre-provisioned)
            user = self.user_repo.get_by_email(email)
            if user:
                # Link existing user to external identity
                user.external_provider = self.provider_name
                user.external_id = external_id
            else:
                # New user - might require admin approval or auto-create
                return AuthResult(
                    success=False,
                    needs_registration=True,
                    external_claims={
                        "provider": self.provider_name,
                        "external_id": external_id,
                        "email": email,
                        "display_name": name,
                    },
                    error="User registration required"
                )

        if not user.is_active:
            return AuthResult(success=False, error="Account is disabled")

        # Update last login
        user.last_login_at = datetime.utcnow()
        self.session.commit()

        return AuthResult(success=True, user=user, external_claims=claims)

    async def validate_token(self, token: str) -> AuthResult:
        """Validate an OIDC access token."""
        # For OIDC, we typically validate the ID token or call userinfo endpoint
        # This depends on the specific provider configuration
        try:
            claims = await self._decode_id_token(token)
            external_id = claims.get("sub")

            user = self.user_repo.get_by_external_id(self.provider_name, external_id)
            if not user or not user.is_active:
                return AuthResult(success=False, error="User not found or inactive")

            return AuthResult(success=True, user=user)
        except Exception as e:
            return AuthResult(success=False, error=f"Invalid token: {e}")

    async def _decode_id_token(self, token: str) -> dict:
        """Decode and validate an ID token."""
        # In production, validate signature using JWKS
        # For simplicity, decode without verification (validate in real impl)
        return jwt.decode(token, options={"verify_signature": False})
```

### 3.5 Auth Service

```python
# src/datacompass/core/services/auth_service.py

import secrets
from datetime import datetime, timedelta
from typing import Any

import bcrypt
import jwt
from sqlalchemy.orm import Session

from datacompass.core.auth.providers.base import AuthProvider, AuthResult
from datacompass.core.models.auth import (
    User, APIKey, UserCreate, APIKeyCreate, TokenResponse
)
from datacompass.core.repositories.auth import UserRepository, APIKeyRepository
from datacompass.config import settings


class AuthService:
    """
    Core authentication service.

    Coordinates authentication across providers and manages:
    - User sessions
    - JWT tokens
    - API keys
    """

    def __init__(self, session: Session, provider: AuthProvider):
        self.session = session
        self.provider = provider
        self.user_repo = UserRepository(session)
        self.api_key_repo = APIKeyRepository(session)

    # --- Authentication ---

    async def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
        """Authenticate using the configured provider."""
        return await self.provider.authenticate(credentials)

    async def authenticate_api_key(self, key: str) -> AuthResult:
        """Authenticate using an API key."""
        if not key or len(key) < 8:
            return AuthResult(success=False, error="Invalid API key format")

        prefix = key[:8]
        api_key = self.api_key_repo.get_by_prefix(prefix)

        if not api_key:
            return AuthResult(success=False, error="Invalid API key")

        if not api_key.is_active:
            return AuthResult(success=False, error="API key is disabled")

        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return AuthResult(success=False, error="API key has expired")

        # Verify the full key
        if not bcrypt.checkpw(key.encode(), api_key.key_hash.encode()):
            return AuthResult(success=False, error="Invalid API key")

        # Update last used
        api_key.last_used_at = datetime.utcnow()
        self.session.commit()

        user = api_key.user
        if not user.is_active:
            return AuthResult(success=False, error="User account is disabled")

        return AuthResult(success=True, user=user)

    # --- Token Management ---

    def create_access_token(self, user: User, expires_delta: timedelta | None = None) -> str:
        """Create a JWT access token for a user."""
        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.auth_access_token_expire_minutes)

        expire = datetime.utcnow() + expires_delta
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "exp": expire,
            "iat": datetime.utcnow(),
        }

        return jwt.encode(payload, settings.auth_secret_key, algorithm="HS256")

    def create_refresh_token(self, user: User) -> str:
        """Create a refresh token for token rotation."""
        token = secrets.token_urlsafe(32)
        # Store hashed in database
        token_hash = bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()
        self.user_repo.create_refresh_token(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(days=settings.auth_refresh_token_expire_days)
        )
        self.session.commit()
        return token

    def create_token_response(self, user: User, include_refresh: bool = True) -> TokenResponse:
        """Create a complete token response for a user."""
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user) if include_refresh else None

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.auth_access_token_expire_minutes * 60,
            refresh_token=refresh_token,
        )

    # --- User Management ---

    def create_local_user(self, data: UserCreate) -> User:
        """Create a new local user."""
        if not data.password:
            raise ValueError("Password required for local users")

        password_hash = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()

        return self.user_repo.create(
            email=data.email,
            username=data.username,
            display_name=data.display_name,
            password_hash=password_hash,
        )

    def register_external_user(
        self,
        provider: str,
        external_id: str,
        email: str,
        display_name: str | None = None,
    ) -> User:
        """Register a user from an external identity provider."""
        return self.user_repo.create(
            email=email,
            display_name=display_name,
            external_provider=provider,
            external_id=external_id,
        )

    def get_user_by_id(self, user_id: int) -> User | None:
        """Get a user by ID."""
        return self.user_repo.get_by_id(user_id)

    def get_user_by_email(self, email: str) -> User | None:
        """Get a user by email."""
        return self.user_repo.get_by_email(email)

    def list_users(self, include_inactive: bool = False) -> list[User]:
        """List all users."""
        return self.user_repo.list_all(include_inactive=include_inactive)

    # --- API Key Management ---

    def create_api_key(self, user: User, data: APIKeyCreate) -> tuple[APIKey, str]:
        """
        Create a new API key for a user.

        Returns the APIKey model and the raw key (only returned once).
        """
        # Generate a secure random key
        raw_key = secrets.token_urlsafe(32)
        prefix = raw_key[:8]
        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()

        expires_at = None
        if data.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=data.expires_in_days)

        api_key = self.api_key_repo.create(
            user_id=user.id,
            name=data.name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=data.scopes,
            expires_at=expires_at,
        )
        self.session.commit()

        return api_key, raw_key

    def list_api_keys(self, user: User) -> list[APIKey]:
        """List all API keys for a user."""
        return self.api_key_repo.list_by_user(user.id)

    def revoke_api_key(self, key_id: int, user: User) -> bool:
        """Revoke an API key. Returns True if successful."""
        api_key = self.api_key_repo.get_by_id(key_id)
        if not api_key or api_key.user_id != user.id:
            return False

        api_key.is_active = False
        self.session.commit()
        return True
```

---

## 4. CLI Commands

### 4.1 Command Structure

```bash
# User management (admin)
datacompass auth user create <email> [--password] [--display-name "..."]
datacompass auth user list [--include-inactive]
datacompass auth user show <email>
datacompass auth user disable <email>
datacompass auth user enable <email>
datacompass auth user set-superuser <email> [--remove]

# API key management (self-service)
datacompass auth login                              # Interactive login (opens browser for OIDC)
datacompass auth login --email <email> --password   # Local auth (prompts for password)
datacompass auth logout                             # Clear stored credentials
datacompass auth whoami                             # Show current user

datacompass auth apikey create <name> [--scopes read,write] [--expires-days 365]
datacompass auth apikey list
datacompass auth apikey revoke <key-id>

# Configuration check
datacompass auth status                             # Show auth mode and provider info
```

### 4.2 CLI Implementation

```python
# src/datacompass/cli/auth.py

import getpass
import webbrowser
from typing import Annotated

import typer

from datacompass.cli.helpers import get_session, output_result, OutputFormat, handle_error
from datacompass.core.services.auth_service import AuthService
from datacompass.core.auth.providers import get_provider
from datacompass.config import settings


app = typer.Typer(help="Authentication management")
user_app = typer.Typer(help="User management (admin)")
apikey_app = typer.Typer(help="API key management")

app.add_typer(user_app, name="user")
app.add_typer(apikey_app, name="apikey")


@app.command()
def login(
    email: Annotated[str | None, typer.Option("--email", "-e")] = None,
    password: Annotated[bool, typer.Option("--password", "-p")] = False,
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.json,
) -> None:
    """
    Log in to Data Compass.

    For OIDC providers, opens a browser for authentication.
    For local auth, use --email and --password.
    """
    try:
        with get_session() as session:
            provider = get_provider(session)
            auth_service = AuthService(session, provider)

            if provider.supports_password_auth() and email:
                # Local authentication
                pwd = getpass.getpass("Password: ") if password else None
                if not pwd:
                    raise typer.BadParameter("Password required for local auth")

                import asyncio
                result = asyncio.run(auth_service.authenticate({
                    "email": email,
                    "password": pwd,
                }))

                if not result.success:
                    handle_error(result.error)
                    raise typer.Exit(1)

                # Generate and store token
                token_response = auth_service.create_token_response(result.user)
                _store_credentials(token_response)

                output_result({"message": f"Logged in as {result.user.email}"}, format)

            elif provider.supports_oauth_flow():
                # OIDC authentication - device flow or browser
                state = secrets.token_urlsafe(16)
                redirect_uri = f"http://localhost:{settings.auth_callback_port}/callback"
                auth_url = provider.get_oauth_authorize_url(state, redirect_uri)

                typer.echo(f"Opening browser for authentication...")
                typer.echo(f"If browser doesn't open, visit: {auth_url}")
                webbrowser.open(auth_url)

                # Start local server to receive callback
                token_response = _wait_for_oauth_callback(auth_service, state, redirect_uri)
                _store_credentials(token_response)

                output_result({"message": "Login successful"}, format)
            else:
                handle_error("No supported authentication method available")
                raise typer.Exit(1)

    except Exception as e:
        handle_error(e)
        raise typer.Exit(1)


@app.command()
def logout() -> None:
    """Log out and clear stored credentials."""
    _clear_credentials()
    typer.echo("Logged out successfully")


@app.command()
def whoami(
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.json,
) -> None:
    """Show the current authenticated user."""
    try:
        with get_session() as session:
            provider = get_provider(session)
            auth_service = AuthService(session, provider)

            token = _get_stored_token()
            if not token:
                output_result({"authenticated": False, "message": "Not logged in"}, format)
                return

            import asyncio
            result = asyncio.run(provider.validate_token(token))

            if result.success:
                output_result({
                    "authenticated": True,
                    "user": {
                        "id": result.user.id,
                        "email": result.user.email,
                        "display_name": result.user.display_name,
                        "is_superuser": result.user.is_superuser,
                    }
                }, format)
            else:
                output_result({"authenticated": False, "message": result.error}, format)

    except Exception as e:
        handle_error(e)
        raise typer.Exit(1)


@app.command()
def status(
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.json,
) -> None:
    """Show authentication configuration status."""
    output_result({
        "auth_mode": settings.auth_mode,
        "provider": settings.auth_provider_name if settings.auth_mode != "disabled" else None,
        "password_auth": settings.auth_mode == "local",
        "oauth_flow": settings.auth_mode == "oidc",
    }, format)


# --- API Key Commands ---

@apikey_app.command("create")
def apikey_create(
    name: Annotated[str, typer.Argument(help="Name for the API key")],
    scopes: Annotated[str, typer.Option("--scopes", "-s")] = "read",
    expires_days: Annotated[int | None, typer.Option("--expires-days")] = None,
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.json,
) -> None:
    """Create a new API key."""
    try:
        user = _get_current_user()
        if not user:
            handle_error("Must be logged in to create API keys")
            raise typer.Exit(1)

        with get_session() as session:
            provider = get_provider(session)
            auth_service = AuthService(session, provider)

            from datacompass.core.models.auth import APIKeyCreate
            data = APIKeyCreate(
                name=name,
                scopes=scopes.split(","),
                expires_in_days=expires_days,
            )

            api_key, raw_key = auth_service.create_api_key(user, data)

            output_result({
                "id": api_key.id,
                "name": api_key.name,
                "key": raw_key,  # Only shown once!
                "scopes": data.scopes,
                "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
                "warning": "Save this key now - it won't be shown again!",
            }, format)

    except Exception as e:
        handle_error(e)
        raise typer.Exit(1)


@apikey_app.command("list")
def apikey_list(
    format: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.json,
) -> None:
    """List your API keys."""
    try:
        user = _get_current_user()
        if not user:
            handle_error("Must be logged in")
            raise typer.Exit(1)

        with get_session() as session:
            provider = get_provider(session)
            auth_service = AuthService(session, provider)

            keys = auth_service.list_api_keys(user)
            output_result([{
                "id": k.id,
                "name": k.name,
                "prefix": k.key_prefix,
                "scopes": k.scopes,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "is_active": k.is_active,
            } for k in keys], format)

    except Exception as e:
        handle_error(e)
        raise typer.Exit(1)


@apikey_app.command("revoke")
def apikey_revoke(
    key_id: Annotated[int, typer.Argument(help="API key ID to revoke")],
) -> None:
    """Revoke an API key."""
    try:
        user = _get_current_user()
        if not user:
            handle_error("Must be logged in")
            raise typer.Exit(1)

        with get_session() as session:
            provider = get_provider(session)
            auth_service = AuthService(session, provider)

            if auth_service.revoke_api_key(key_id, user):
                typer.echo(f"API key {key_id} revoked")
            else:
                handle_error("API key not found or not owned by you")
                raise typer.Exit(1)

    except Exception as e:
        handle_error(e)
        raise typer.Exit(1)


# --- Helper Functions ---

def _store_credentials(token_response) -> None:
    """Store authentication credentials locally."""
    import json
    creds_path = settings.data_dir / ".credentials"
    creds_path.write_text(json.dumps({
        "access_token": token_response.access_token,
        "refresh_token": token_response.refresh_token,
    }))
    creds_path.chmod(0o600)  # Secure permissions


def _get_stored_token() -> str | None:
    """Get stored access token."""
    import json
    creds_path = settings.data_dir / ".credentials"
    if creds_path.exists():
        creds = json.loads(creds_path.read_text())
        return creds.get("access_token")
    return None


def _clear_credentials() -> None:
    """Clear stored credentials."""
    creds_path = settings.data_dir / ".credentials"
    if creds_path.exists():
        creds_path.unlink()


def _get_current_user():
    """Get the currently authenticated user."""
    # Implementation depends on stored credentials
    pass
```

---

## 5. API Layer

### 5.1 Auth Middleware

```python
# src/datacompass/api/middleware/auth.py

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.orm import Session

from datacompass.api.dependencies import get_session
from datacompass.core.services.auth_service import AuthService
from datacompass.core.auth.providers import get_provider
from datacompass.core.models.auth import User
from datacompass.config import settings


security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
    bearer: HTTPAuthorizationCredentials | None = Depends(security),
    api_key: str | None = Depends(api_key_header),
) -> User | None:
    """
    Get the current authenticated user.

    Supports:
    - Bearer token (JWT)
    - X-API-Key header
    - Session cookie (for web UI)

    Returns None if auth is disabled or no credentials provided.
    """
    if settings.auth_mode == "disabled":
        return None

    provider = get_provider(session)
    auth_service = AuthService(session, provider)

    # Try Bearer token first
    if bearer:
        result = await provider.validate_token(bearer.credentials)
        if result.success:
            return result.user
        raise HTTPException(status_code=401, detail=result.error)

    # Try API key
    if api_key:
        result = await auth_service.authenticate_api_key(api_key)
        if result.success:
            return result.user
        raise HTTPException(status_code=401, detail=result.error)

    # Try session cookie
    session_id = request.cookies.get("session_id")
    if session_id:
        user = auth_service.get_user_from_session(session_id)
        if user:
            return user

    return None


async def require_auth(
    user: User | None = Depends(get_current_user),
) -> User:
    """Require authentication - raises 401 if not authenticated."""
    if settings.auth_mode == "disabled":
        # Return a dummy user for development
        return User(id=0, email="dev@localhost", is_superuser=True)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_superuser(
    user: User = Depends(require_auth),
) -> User:
    """Require superuser privileges."""
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    return user


def check_scope(required_scope: str):
    """Dependency factory to check API key scopes."""
    async def _check(
        request: Request,
        user: User = Depends(require_auth),
    ) -> User:
        # API keys have scopes, JWT tokens have full access
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Get the API key's scopes and check
            # Implementation details...
            pass
        return user
    return _check
```

### 5.2 Auth Routes

```python
# src/datacompass/api/routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session

from datacompass.api.dependencies import get_session
from datacompass.api.middleware.auth import get_current_user, require_auth, require_superuser
from datacompass.core.services.auth_service import AuthService
from datacompass.core.auth.providers import get_provider
from datacompass.core.models.auth import (
    User, UserCreate, UserResponse, LoginRequest, TokenResponse,
    APIKeyCreate, APIKeyResponse, APIKeyCreated,
)
from datacompass.config import settings


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """
    Authenticate with email and password (local auth only).

    Returns access and refresh tokens.
    """
    provider = get_provider(session)
    if not provider.supports_password_auth():
        raise HTTPException(
            status_code=400,
            detail="Password authentication not supported. Use OAuth flow."
        )

    auth_service = AuthService(session, provider)
    result = await auth_service.authenticate({
        "email": data.email,
        "password": data.password,
    })

    if not result.success:
        raise HTTPException(status_code=401, detail=result.error)

    return auth_service.create_token_response(result.user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Exchange a refresh token for a new access token."""
    provider = get_provider(session)
    auth_service = AuthService(session, provider)

    user = auth_service.validate_refresh_token(refresh_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Rotate refresh token
    return auth_service.create_token_response(user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: User = Depends(require_auth),
) -> UserResponse:
    """Get the current authenticated user's information."""
    return UserResponse.from_orm(user)


# --- OAuth Routes ---

@router.get("/oauth/authorize")
async def oauth_authorize(
    redirect_uri: str,
    session: Session = Depends(get_session),
) -> dict:
    """
    Get the OAuth authorization URL.

    Used by frontends to initiate the OAuth flow.
    """
    provider = get_provider(session)
    if not provider.supports_oauth_flow():
        raise HTTPException(status_code=400, detail="OAuth not supported")

    import secrets
    state = secrets.token_urlsafe(16)
    # Store state in session for validation

    auth_url = provider.get_oauth_authorize_url(state, redirect_uri)
    return {"authorization_url": auth_url, "state": state}


@router.post("/oauth/callback", response_model=TokenResponse)
async def oauth_callback(
    code: str,
    state: str,
    redirect_uri: str,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """
    Handle OAuth callback and exchange code for tokens.
    """
    # Validate state
    # ...

    provider = get_provider(session)
    auth_service = AuthService(session, provider)

    result = await auth_service.authenticate({
        "code": code,
        "redirect_uri": redirect_uri,
    })

    if result.needs_registration:
        # Auto-register or require admin approval
        if settings.auth_auto_register:
            claims = result.external_claims
            user = auth_service.register_external_user(
                provider=claims["provider"],
                external_id=claims["external_id"],
                email=claims["email"],
                display_name=claims.get("display_name"),
            )
            session.commit()
            return auth_service.create_token_response(user)
        else:
            raise HTTPException(
                status_code=403,
                detail="User registration requires admin approval"
            )

    if not result.success:
        raise HTTPException(status_code=401, detail=result.error)

    return auth_service.create_token_response(result.user)


# --- API Key Routes ---

@router.post("/apikeys", response_model=APIKeyCreated)
async def create_api_key(
    data: APIKeyCreate,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session),
) -> APIKeyCreated:
    """Create a new API key for the current user."""
    provider = get_provider(session)
    auth_service = AuthService(session, provider)

    api_key, raw_key = auth_service.create_api_key(user, data)

    return APIKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=raw_key,  # Only returned on creation
        scopes=data.scopes,
        expires_at=api_key.expires_at,
        last_used_at=None,
        is_active=True,
        created_at=api_key.created_at,
    )


@router.get("/apikeys", response_model=list[APIKeyResponse])
async def list_api_keys(
    user: User = Depends(require_auth),
    session: Session = Depends(get_session),
) -> list[APIKeyResponse]:
    """List all API keys for the current user."""
    provider = get_provider(session)
    auth_service = AuthService(session, provider)

    keys = auth_service.list_api_keys(user)
    return [APIKeyResponse.from_orm(k) for k in keys]


@router.delete("/apikeys/{key_id}")
async def revoke_api_key(
    key_id: int,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session),
) -> dict:
    """Revoke an API key."""
    provider = get_provider(session)
    auth_service = AuthService(session, provider)

    if not auth_service.revoke_api_key(key_id, user):
        raise HTTPException(status_code=404, detail="API key not found")

    return {"message": "API key revoked"}


# --- Admin Routes ---

@router.post("/users", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    admin: User = Depends(require_superuser),
    session: Session = Depends(get_session),
) -> UserResponse:
    """Create a new user (admin only)."""
    provider = get_provider(session)
    auth_service = AuthService(session, provider)

    user = auth_service.create_local_user(data)
    session.commit()

    return UserResponse.from_orm(user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    include_inactive: bool = False,
    admin: User = Depends(require_superuser),
    session: Session = Depends(get_session),
) -> list[UserResponse]:
    """List all users (admin only)."""
    provider = get_provider(session)
    auth_service = AuthService(session, provider)

    users = auth_service.list_users(include_inactive=include_inactive)
    return [UserResponse.from_orm(u) for u in users]
```

---

## 6. Frontend Integration

### 6.1 Auth Context

```typescript
// frontend/src/contexts/AuthContext.tsx

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';

interface User {
  id: number;
  email: string;
  displayName: string | null;
  isSuperuser: boolean;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loginWithOAuth: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem('access_token')
  );

  // Fetch current user
  const { data: user, isLoading } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => api.get<User>('/auth/me'),
    enabled: !!token,
    retry: false,
  });

  // Login mutation
  const loginMutation = useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }) => {
      const response = await api.post<{ access_token: string; refresh_token: string }>(
        '/auth/login',
        { email, password }
      );
      return response;
    },
    onSuccess: (data) => {
      localStorage.setItem('access_token', data.access_token);
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token);
      }
      setToken(data.access_token);
      queryClient.invalidateQueries({ queryKey: ['auth'] });
    },
  });

  const login = async (email: string, password: string) => {
    await loginMutation.mutateAsync({ email, password });
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    queryClient.clear();
  };

  const loginWithOAuth = async () => {
    // Get OAuth authorization URL
    const { authorization_url } = await api.get<{ authorization_url: string }>(
      '/auth/oauth/authorize',
      { params: { redirect_uri: `${window.location.origin}/auth/callback` } }
    );
    // Redirect to OAuth provider
    window.location.href = authorization_url;
  };

  return (
    <AuthContext.Provider
      value={{
        user: user ?? null,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        loginWithOAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
```

### 6.2 Login Page

```typescript
// frontend/src/pages/LoginPage.tsx

import React, { useState } from 'react';
import { Form, Input, Button, Card, Divider, Alert, Typography } from 'antd';
import { UserOutlined, LockOutlined, GoogleOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';

const { Title } = Typography;

export function LoginPage() {
  const { login, loginWithOAuth, isLoading } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as any)?.from?.pathname || '/';

  const handleSubmit = async (values: { email: string; password: string }) => {
    try {
      setError(null);
      await login(values.email, values.password);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message || 'Login failed');
    }
  };

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: '#f0f2f5',
    }}>
      <Card style={{ width: 400, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 24 }}>
          Data Compass
        </Title>

        {error && (
          <Alert message={error} type="error" showIcon style={{ marginBottom: 16 }} />
        )}

        <Form onFinish={handleSubmit} layout="vertical">
          <Form.Item
            name="email"
            rules={[{ required: true, message: 'Please enter your email' }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="Email"
              size="large"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: 'Please enter your password' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="Password"
              size="large"
            />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              block
              loading={isLoading}
            >
              Log In
            </Button>
          </Form.Item>
        </Form>

        <Divider>or</Divider>

        <Button
          icon={<GoogleOutlined />}
          size="large"
          block
          onClick={loginWithOAuth}
        >
          Continue with SSO
        </Button>
      </Card>
    </div>
  );
}
```

### 6.3 Protected Routes

```typescript
// frontend/src/components/ProtectedRoute.tsx

import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import { useAuth } from '../contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireSuperuser?: boolean;
}

export function ProtectedRoute({ children, requireSuperuser = false }: ProtectedRouteProps) {
  const { user, isLoading, isAuthenticated } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requireSuperuser && !user?.isSuperuser) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
```

---

## 7. Configuration

### 7.1 Settings

```python
# src/datacompass/config/settings.py (additions)

from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # ... existing settings ...

    # Authentication
    auth_mode: Literal["disabled", "local", "oidc", "ldap"] = "disabled"
    auth_secret_key: str = "change-me-in-production"  # For JWT signing
    auth_access_token_expire_minutes: int = 30
    auth_refresh_token_expire_days: int = 7
    auth_callback_port: int = 8085  # For CLI OAuth callback
    auth_auto_register: bool = False  # Auto-register OIDC users

    # OIDC Configuration (when auth_mode=oidc)
    auth_oidc_client_id: str | None = None
    auth_oidc_client_secret: str | None = None
    auth_oidc_issuer: str | None = None
    auth_oidc_authorization_endpoint: str | None = None
    auth_oidc_token_endpoint: str | None = None
    auth_oidc_userinfo_endpoint: str | None = None

    # Provider name for display
    auth_provider_name: str | None = None  # 'Azure AD', 'Okta', etc.
```

### 7.2 Example Configurations

**Local Development:**
```bash
DATACOMPASS_AUTH_MODE=local
DATACOMPASS_AUTH_SECRET_KEY=dev-secret-key-change-in-prod
```

**Azure AD:**
```bash
DATACOMPASS_AUTH_MODE=oidc
DATACOMPASS_AUTH_SECRET_KEY=<secure-random-key>
DATACOMPASS_AUTH_OIDC_CLIENT_ID=<app-client-id>
DATACOMPASS_AUTH_OIDC_CLIENT_SECRET=<app-client-secret>
DATACOMPASS_AUTH_OIDC_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
DATACOMPASS_AUTH_OIDC_AUTHORIZATION_ENDPOINT=https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize
DATACOMPASS_AUTH_OIDC_TOKEN_ENDPOINT=https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token
DATACOMPASS_AUTH_PROVIDER_NAME=Azure AD
DATACOMPASS_AUTH_AUTO_REGISTER=true
```

**Okta:**
```bash
DATACOMPASS_AUTH_MODE=oidc
DATACOMPASS_AUTH_SECRET_KEY=<secure-random-key>
DATACOMPASS_AUTH_OIDC_CLIENT_ID=<okta-client-id>
DATACOMPASS_AUTH_OIDC_CLIENT_SECRET=<okta-client-secret>
DATACOMPASS_AUTH_OIDC_ISSUER=https://<domain>.okta.com
DATACOMPASS_AUTH_OIDC_AUTHORIZATION_ENDPOINT=https://<domain>.okta.com/oauth2/v1/authorize
DATACOMPASS_AUTH_OIDC_TOKEN_ENDPOINT=https://<domain>.okta.com/oauth2/v1/token
DATACOMPASS_AUTH_PROVIDER_NAME=Okta
```

---

## 8. Implementation Plan

### Phase 9.1: Core Auth Infrastructure
- [ ] Create migration 007_authentication
- [ ] Implement User, APIKey models
- [ ] Implement UserRepository, APIKeyRepository
- [ ] Implement AuthProvider interface
- [ ] Implement LocalAuthProvider
- [ ] Implement AuthService
- [ ] Add auth settings to configuration

### Phase 9.2: CLI Authentication
- [ ] Implement `datacompass auth login` (local)
- [ ] Implement `datacompass auth logout`
- [ ] Implement `datacompass auth whoami`
- [ ] Implement `datacompass auth apikey create/list/revoke`
- [ ] Implement credential storage (secure file)
- [ ] Add auth headers to CLI API calls

### Phase 9.3: API Authentication
- [ ] Implement auth middleware (Bearer + API key)
- [ ] Implement `/auth/login` endpoint
- [ ] Implement `/auth/me` endpoint
- [ ] Implement `/auth/apikeys` CRUD endpoints
- [ ] Add `require_auth` dependency to protected routes
- [ ] Implement `/auth/users` admin endpoints

### Phase 9.4: OIDC Provider
- [ ] Implement OIDCAuthProvider
- [ ] Implement OAuth authorization URL generation
- [ ] Implement OAuth callback handling
- [ ] Implement token validation with JWKS
- [ ] Add OIDC configuration to settings

### Phase 9.5: Frontend Authentication
- [ ] Implement AuthContext provider
- [ ] Implement LoginPage component
- [ ] Implement ProtectedRoute wrapper
- [ ] Add OAuth callback page
- [ ] Update API client with auth headers
- [ ] Add user menu with logout

### Phase 9.6: Testing & Documentation
- [ ] Unit tests for AuthService
- [ ] Integration tests for auth endpoints
- [ ] CLI tests for auth commands
- [ ] Update API documentation
- [ ] Write user guide for auth configuration

---

## 9. Security Considerations

### 9.1 Password Storage
- Use bcrypt with cost factor 12+
- Never log or expose password hashes
- Enforce minimum password complexity (when local auth)

### 9.2 Token Security
- JWT access tokens: short-lived (30 min default)
- Refresh tokens: stored hashed, support rotation
- API keys: hashed with bcrypt, prefix for identification

### 9.3 Session Security
- HttpOnly, Secure, SameSite cookies for web sessions
- Session invalidation on logout
- Automatic expiration

### 9.4 OIDC Security
- Validate ID token signatures using JWKS
- Verify issuer, audience, expiration claims
- Use state parameter to prevent CSRF

### 9.5 API Security
- Rate limiting on auth endpoints
- Account lockout after failed attempts (optional)
- Audit logging of auth events

---

## 10. Future Enhancements (Deferred)

### 10.1 LDAP Provider
Support legacy Active Directory/LDAP authentication for organizations not using modern OIDC.

### 10.2 Multi-Factor Authentication
Add TOTP (Google Authenticator) support for local auth.

### 10.3 SCIM Provisioning
Auto-provision/deprovision users from identity provider.

### 10.4 Session Management UI
Allow users to view and revoke active sessions.

### 10.5 Audit Logging
Track all authentication events (login, logout, failed attempts).

---

## Appendix A: OIDC Provider Configurations

### Azure AD / Entra ID

1. Register application in Azure Portal
2. Add redirect URI: `http://localhost:8000/auth/callback` (and production URL)
3. Create client secret
4. Configure environment variables:

```bash
DATACOMPASS_AUTH_OIDC_ISSUER=https://login.microsoftonline.com/{tenant-id}/v2.0
DATACOMPASS_AUTH_OIDC_AUTHORIZATION_ENDPOINT=https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/authorize
DATACOMPASS_AUTH_OIDC_TOKEN_ENDPOINT=https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/token
```

### Okta

1. Create application in Okta Admin Console
2. Choose "Web Application" type
3. Add redirect URI
4. Configure environment variables:

```bash
DATACOMPASS_AUTH_OIDC_ISSUER=https://{domain}.okta.com
DATACOMPASS_AUTH_OIDC_AUTHORIZATION_ENDPOINT=https://{domain}.okta.com/oauth2/v1/authorize
DATACOMPASS_AUTH_OIDC_TOKEN_ENDPOINT=https://{domain}.okta.com/oauth2/v1/token
```

### Google Workspace

1. Create project in Google Cloud Console
2. Configure OAuth consent screen
3. Create OAuth 2.0 credentials
4. Configure environment variables:

```bash
DATACOMPASS_AUTH_OIDC_ISSUER=https://accounts.google.com
DATACOMPASS_AUTH_OIDC_AUTHORIZATION_ENDPOINT=https://accounts.google.com/o/oauth2/v2/auth
DATACOMPASS_AUTH_OIDC_TOKEN_ENDPOINT=https://oauth2.googleapis.com/token
```

---

## Appendix B: CLI Credential Storage

Credentials are stored in `~/.datacompass/.credentials` with `0600` permissions:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "...",
  "expires_at": "2024-01-15T12:00:00Z"
}
```

The CLI automatically refreshes tokens when expired.

For CI/CD environments, use API keys or environment variables:

```bash
# API key (preferred for automation)
export DATACOMPASS_API_KEY=dc_xxxxxxxxxxxxxxxx

# Or token directly
export DATACOMPASS_ACCESS_TOKEN=eyJ...
```
