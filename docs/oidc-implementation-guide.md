# OIDC Implementation Guide

This guide documents how to implement OAuth2/OIDC authentication for Data Compass (Phase 9.4). Use this guide when you're ready to integrate with an enterprise identity provider like Azure AD, Okta, or Google Workspace.

## Overview

The authentication infrastructure is already in place:
- `AuthProvider` interface for pluggable providers
- `LocalAuthProvider` for email/password authentication
- `DisabledAuthProvider` for no-auth mode
- JWT token generation and validation
- API key management
- Frontend login UI with SSO button placeholder

What needs to be implemented:
- `OIDCAuthProvider` class
- OAuth2 authorization code flow
- ID token validation with JWKS
- User auto-registration (optional)
- CLI device flow (optional)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  AuthService (existing)                     │
│         Coordinates authentication + session mgmt           │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                  AuthProvider (interface)                   │
├─────────────────────────────────────────────────────────────┤
│  LocalAuthProvider   │  OIDCAuthProvider  │  LDAPProvider  │
│  (implemented)       │  (TO IMPLEMENT)    │  (future)      │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### 1. Create OIDCAuthProvider

Create `src/datacompass/core/auth/providers/oidc.py`:

```python
"""OIDC authentication provider."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from datacompass.core.auth.providers.base import AuthProvider, AuthResult
from datacompass.core.models.auth import User
from datacompass.core.repositories.auth import UserRepository
from datacompass.config.settings import Settings


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
    scopes: list[str] | None = None

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = ["openid", "email", "profile"]


class OIDCAuthProvider(AuthProvider):
    """OAuth2/OIDC authentication for enterprise identity providers."""

    def __init__(self, session: Session, config: OIDCConfig):
        self.session = session
        self.config = config
        self.user_repo = UserRepository(session)
        self._jwks_client: PyJWKClient | None = None

    @property
    def provider_name(self) -> str:
        return self.config.provider_name

    def supports_password_auth(self) -> bool:
        return False

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

    def authenticate(self, credentials: dict[str, Any]) -> AuthResult:
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
        try:
            tokens = self._exchange_code(code, redirect_uri)
        except Exception as e:
            return AuthResult(success=False, error=f"Token exchange failed: {e}")

        id_token = tokens.get("id_token")
        if not id_token:
            return AuthResult(success=False, error="No ID token in response")

        # Decode and validate ID token
        try:
            claims = self._decode_id_token(id_token)
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
                self.session.commit()
            else:
                # New user - return needs_registration
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
        from datetime import datetime
        user.last_login_at = datetime.utcnow()
        self.session.commit()

        return AuthResult(success=True, user=user, external_claims=claims)

    def validate_token(self, token: str) -> AuthResult:
        """Validate a JWT access token."""
        try:
            claims = self._decode_id_token(token)
            external_id = claims.get("sub")

            user = self.user_repo.get_by_external_id(self.provider_name, external_id)
            if not user or not user.is_active:
                return AuthResult(success=False, error="User not found or inactive")

            return AuthResult(success=True, user=user)
        except Exception as e:
            return AuthResult(success=False, error=f"Invalid token: {e}")

    def _exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for tokens."""
        with httpx.Client() as client:
            response = client.post(
                self.config.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            response.raise_for_status()
            return response.json()

    def _decode_id_token(self, token: str) -> dict:
        """Decode and validate an ID token."""
        if self.config.jwks_uri:
            # Validate signature using JWKS
            if self._jwks_client is None:
                self._jwks_client = PyJWKClient(self.config.jwks_uri)

            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.config.client_id,
                issuer=self.config.issuer,
            )
        else:
            # No JWKS URI - decode without verification (not recommended for production)
            return jwt.decode(token, options={"verify_signature": False})
```

### 2. Add Configuration Settings

Add to `src/datacompass/config/settings.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # OIDC Configuration (when auth_mode=oidc)
    auth_oidc_provider_name: str | None = None      # 'azure_ad', 'okta', 'google'
    auth_oidc_client_id: str | None = None
    auth_oidc_client_secret: str | None = None
    auth_oidc_issuer: str | None = None
    auth_oidc_authorization_endpoint: str | None = None
    auth_oidc_token_endpoint: str | None = None
    auth_oidc_userinfo_endpoint: str | None = None
    auth_oidc_jwks_uri: str | None = None
    auth_oidc_scopes: str = "openid email profile"  # Space-separated
```

### 3. Update Provider Factory

Update `src/datacompass/core/auth/__init__.py`:

```python
from sqlalchemy.orm import Session

from datacompass.config.settings import get_settings
from datacompass.core.auth.providers.base import AuthProvider
from datacompass.core.auth.providers.disabled import DisabledAuthProvider
from datacompass.core.auth.providers.local import LocalAuthProvider


def get_provider(session: Session) -> AuthProvider:
    """Get the configured authentication provider."""
    settings = get_settings()

    if settings.auth_mode == "disabled":
        return DisabledAuthProvider()
    elif settings.auth_mode == "local":
        return LocalAuthProvider(session)
    elif settings.auth_mode == "oidc":
        from datacompass.core.auth.providers.oidc import OIDCAuthProvider, OIDCConfig

        config = OIDCConfig(
            provider_name=settings.auth_oidc_provider_name or "oidc",
            client_id=settings.auth_oidc_client_id,
            client_secret=settings.auth_oidc_client_secret,
            issuer=settings.auth_oidc_issuer,
            authorization_endpoint=settings.auth_oidc_authorization_endpoint,
            token_endpoint=settings.auth_oidc_token_endpoint,
            userinfo_endpoint=settings.auth_oidc_userinfo_endpoint,
            jwks_uri=settings.auth_oidc_jwks_uri,
            scopes=settings.auth_oidc_scopes.split(),
        )
        return OIDCAuthProvider(session, config)
    else:
        raise ValueError(f"Unknown auth mode: {settings.auth_mode}")
```

### 4. Add API Endpoints for OAuth Flow

Add to `src/datacompass/api/routes/auth.py`:

```python
@router.get("/oauth/authorize")
async def oauth_authorize(
    redirect_uri: str,
    auth_service: AuthServiceDep,
) -> dict:
    """Get the OAuth authorization URL."""
    provider = auth_service.provider
    if not provider.supports_oauth_flow():
        raise HTTPException(status_code=400, detail="OAuth not supported")

    import secrets
    state = secrets.token_urlsafe(16)
    # TODO: Store state in session/cache for validation

    auth_url = provider.get_oauth_authorize_url(state, redirect_uri)
    return {"authorization_url": auth_url, "state": state}


@router.post("/oauth/callback", response_model=TokenResponse)
async def oauth_callback(
    code: str,
    state: str,
    redirect_uri: str,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Handle OAuth callback and exchange code for tokens."""
    # TODO: Validate state against stored value

    result = auth_service.authenticate({
        "code": code,
        "redirect_uri": redirect_uri,
    })

    if result.needs_registration:
        settings = get_settings()
        if settings.auth_auto_register:
            claims = result.external_claims
            user = auth_service.register_external_user(
                provider=claims["provider"],
                external_id=claims["external_id"],
                email=claims["email"],
                display_name=claims.get("display_name"),
            )
            return auth_service.create_token_response(user)
        else:
            raise HTTPException(
                status_code=403,
                detail="User registration requires admin approval"
            )

    if not result.success:
        raise HTTPException(status_code=401, detail=result.error)

    return auth_service.create_token_response(result.user)
```

### 5. Update Frontend for OAuth

Update `frontend/src/context/AuthContext.tsx` to add OAuth support:

```typescript
const loginWithOAuth = useCallback(async () => {
  // Get OAuth authorization URL from backend
  const response = await fetch('/api/v1/auth/oauth/authorize?' + new URLSearchParams({
    redirect_uri: `${window.location.origin}/auth/callback`,
  }))
  const data = await response.json()

  // Store state for validation
  sessionStorage.setItem('oauth_state', data.state)

  // Redirect to identity provider
  window.location.href = data.authorization_url
}, [])
```

Create `frontend/src/pages/OAuthCallbackPage.tsx`:

```typescript
import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Spin } from 'antd'
import { setTokens } from '../api/client'

export function OAuthCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  useEffect(() => {
    async function handleCallback() {
      const code = searchParams.get('code')
      const state = searchParams.get('state')
      const storedState = sessionStorage.getItem('oauth_state')

      if (!code || state !== storedState) {
        navigate('/login?error=invalid_state')
        return
      }

      sessionStorage.removeItem('oauth_state')

      try {
        const response = await fetch('/api/v1/auth/oauth/callback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code,
            state,
            redirect_uri: `${window.location.origin}/auth/callback`,
          }),
        })

        if (!response.ok) {
          throw new Error('OAuth callback failed')
        }

        const tokens = await response.json()
        setTokens(tokens.access_token, tokens.refresh_token)
        navigate('/')
      } catch (error) {
        navigate('/login?error=auth_failed')
      }
    }

    handleCallback()
  }, [searchParams, navigate])

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <Spin size="large" />
    </div>
  )
}
```

Add the route in `App.tsx`:

```tsx
<Route path="/auth/callback" element={<OAuthCallbackPage />} />
```

## Provider-Specific Configuration

### Azure AD / Entra ID

```bash
DATACOMPASS_AUTH_MODE=oidc
DATACOMPASS_AUTH_SECRET_KEY=<secure-random-key>
DATACOMPASS_AUTH_OIDC_PROVIDER_NAME=azure_ad
DATACOMPASS_AUTH_OIDC_CLIENT_ID=<app-client-id>
DATACOMPASS_AUTH_OIDC_CLIENT_SECRET=<app-client-secret>
DATACOMPASS_AUTH_OIDC_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
DATACOMPASS_AUTH_OIDC_AUTHORIZATION_ENDPOINT=https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize
DATACOMPASS_AUTH_OIDC_TOKEN_ENDPOINT=https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token
DATACOMPASS_AUTH_OIDC_JWKS_URI=https://login.microsoftonline.com/<tenant-id>/discovery/v2.0/keys
DATACOMPASS_AUTH_AUTO_REGISTER=true
```

Azure AD App Registration:
1. Go to Azure Portal > App Registrations
2. Create new registration
3. Add redirect URI: `http://localhost:5173/auth/callback` (and production URL)
4. Create client secret under "Certificates & secrets"
5. Add API permissions: `openid`, `email`, `profile`

### Okta

```bash
DATACOMPASS_AUTH_MODE=oidc
DATACOMPASS_AUTH_SECRET_KEY=<secure-random-key>
DATACOMPASS_AUTH_OIDC_PROVIDER_NAME=okta
DATACOMPASS_AUTH_OIDC_CLIENT_ID=<okta-client-id>
DATACOMPASS_AUTH_OIDC_CLIENT_SECRET=<okta-client-secret>
DATACOMPASS_AUTH_OIDC_ISSUER=https://<domain>.okta.com
DATACOMPASS_AUTH_OIDC_AUTHORIZATION_ENDPOINT=https://<domain>.okta.com/oauth2/v1/authorize
DATACOMPASS_AUTH_OIDC_TOKEN_ENDPOINT=https://<domain>.okta.com/oauth2/v1/token
DATACOMPASS_AUTH_OIDC_JWKS_URI=https://<domain>.okta.com/oauth2/v1/keys
DATACOMPASS_AUTH_AUTO_REGISTER=true
```

### Google Workspace

```bash
DATACOMPASS_AUTH_MODE=oidc
DATACOMPASS_AUTH_SECRET_KEY=<secure-random-key>
DATACOMPASS_AUTH_OIDC_PROVIDER_NAME=google
DATACOMPASS_AUTH_OIDC_CLIENT_ID=<google-client-id>
DATACOMPASS_AUTH_OIDC_CLIENT_SECRET=<google-client-secret>
DATACOMPASS_AUTH_OIDC_ISSUER=https://accounts.google.com
DATACOMPASS_AUTH_OIDC_AUTHORIZATION_ENDPOINT=https://accounts.google.com/o/oauth2/v2/auth
DATACOMPASS_AUTH_OIDC_TOKEN_ENDPOINT=https://oauth2.googleapis.com/token
DATACOMPASS_AUTH_OIDC_JWKS_URI=https://www.googleapis.com/oauth2/v3/certs
DATACOMPASS_AUTH_AUTO_REGISTER=true
```

## Testing

### Unit Tests

Create `tests/core/auth/test_oidc_provider.py`:

```python
import pytest
from unittest.mock import Mock, patch

from datacompass.core.auth.providers.oidc import OIDCAuthProvider, OIDCConfig


@pytest.fixture
def oidc_config():
    return OIDCConfig(
        provider_name="test_provider",
        client_id="test_client_id",
        client_secret="test_secret",
        issuer="https://test.example.com",
        authorization_endpoint="https://test.example.com/authorize",
        token_endpoint="https://test.example.com/token",
    )


def test_get_oauth_authorize_url(session, oidc_config):
    provider = OIDCAuthProvider(session, oidc_config)
    url = provider.get_oauth_authorize_url("test_state", "http://localhost/callback")

    assert "client_id=test_client_id" in url
    assert "state=test_state" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%2Fcallback" in url


def test_supports_oauth_flow(session, oidc_config):
    provider = OIDCAuthProvider(session, oidc_config)
    assert provider.supports_oauth_flow() is True
    assert provider.supports_password_auth() is False
```

### Integration Tests

Test with a real identity provider in a staging environment before production deployment.

## Security Considerations

1. **State Parameter**: Always validate the `state` parameter to prevent CSRF attacks
2. **JWKS Validation**: Always validate ID token signatures in production using JWKS
3. **Token Storage**: Store tokens securely (httpOnly cookies for web, secure storage for CLI)
4. **Secret Management**: Use environment variables or a secrets manager for client secrets
5. **Redirect URI Validation**: Validate redirect URIs match configured values

## CLI Device Flow (Optional)

For CLI authentication without a browser, implement the OAuth 2.0 Device Authorization Grant:

```python
def authenticate_device_flow(self) -> AuthResult:
    """Authenticate using device authorization grant."""
    # 1. Request device code
    response = httpx.post(
        self.config.device_authorization_endpoint,
        data={
            "client_id": self.config.client_id,
            "scope": " ".join(self.config.scopes),
        },
    )
    data = response.json()

    # 2. Display user code and verification URL
    print(f"Go to: {data['verification_uri']}")
    print(f"Enter code: {data['user_code']}")

    # 3. Poll for token
    while True:
        time.sleep(data['interval'])
        token_response = httpx.post(
            self.config.token_endpoint,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": self.config.client_id,
                "device_code": data['device_code'],
            },
        )
        if token_response.status_code == 200:
            return self._handle_token_response(token_response.json())
```

## Checklist

Before deploying OIDC authentication:

- [ ] OIDCAuthProvider implemented and tested
- [ ] Configuration settings added
- [ ] Provider factory updated
- [ ] OAuth API endpoints added
- [ ] Frontend OAuth flow implemented
- [ ] OAuth callback page created
- [ ] State validation implemented
- [ ] JWKS token validation working
- [ ] Auto-registration flow tested
- [ ] Provider-specific configurations documented
- [ ] Security review completed
- [ ] Integration tests passing with real IdP
