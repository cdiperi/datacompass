"""Authentication endpoints."""

from fastapi import APIRouter, status

from datacompass.api.dependencies import AuthServiceDep, RequiredUser, SuperUser
from datacompass.core.models.auth import (
    APIKeyCreate,
    APIKeyCreated,
    APIKeyResponse,
    AuthStatusResponse,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from datacompass.core.services.auth_service import AuthDisabledError

router = APIRouter(prefix="/auth", tags=["auth"])


# =============================================================================
# Authentication
# =============================================================================


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Authenticate with email and password.

    Returns access and refresh tokens on successful authentication.

    Args:
        request: Login credentials (email and password).

    Returns:
        Token response with access and refresh tokens.

    Raises:
        400: If authentication is disabled.
        401: If credentials are invalid.
    """
    return auth_service.authenticate(request.email, request.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Refresh access and refresh tokens.

    Uses a valid refresh token to obtain new access and refresh tokens.
    The old refresh token is invalidated.

    Args:
        request: Refresh token request.

    Returns:
        New token response with access and refresh tokens.

    Raises:
        400: If authentication is disabled.
        401: If refresh token is invalid or expired.
    """
    return auth_service.refresh_tokens(request.refresh_token)


@router.get("/me", response_model=AuthStatusResponse)
async def get_current_user_info(
    auth_service: AuthServiceDep,
    user: RequiredUser,
) -> AuthStatusResponse:
    """Get current user information.

    Returns the authenticated user's profile and auth status.

    Returns:
        Auth status with user info if authenticated.

    Raises:
        401: If not authenticated.
    """
    status_info = auth_service.get_auth_status()
    return AuthStatusResponse(
        auth_mode=status_info["auth_mode"],
        is_authenticated=True,
        user=UserResponse.model_validate(user),
    )


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(
    auth_service: AuthServiceDep,
) -> AuthStatusResponse:
    """Get authentication status and configuration.

    Returns auth mode and whether authentication is enabled.
    Does not require authentication.

    Returns:
        Auth status response.
    """
    status_info = auth_service.get_auth_status()
    return AuthStatusResponse(
        auth_mode=status_info["auth_mode"],
        is_authenticated=False,
        user=None,
    )


# =============================================================================
# API Keys
# =============================================================================


@router.post("/apikeys", response_model=APIKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: APIKeyCreate,
    auth_service: AuthServiceDep,
    user: RequiredUser,
) -> APIKeyCreated:
    """Create a new API key.

    The full key is only shown once in the response.
    Store it securely as it cannot be retrieved again.

    Args:
        request: API key creation request with name and optional scopes/expiration.

    Returns:
        Created API key with full key value.

    Raises:
        400: If authentication is disabled.
        401: If not authenticated.
    """
    # Check if using dummy user (auth disabled)
    if user.id == 0:
        raise AuthDisabledError("create API key")

    return auth_service.create_api_key(
        user=user,
        name=request.name,
        scopes=request.scopes,
        expires_days=request.expires_days,
    )


@router.get("/apikeys", response_model=list[APIKeyResponse])
async def list_api_keys(
    auth_service: AuthServiceDep,
    user: RequiredUser,
    include_inactive: bool = False,
) -> list[APIKeyResponse]:
    """List API keys for the current user.

    Args:
        include_inactive: Include revoked keys.

    Returns:
        List of API keys (without full key values).

    Raises:
        401: If not authenticated.
    """
    keys = auth_service.list_api_keys(user, include_inactive=include_inactive)
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.delete("/apikeys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: int,
    auth_service: AuthServiceDep,
    user: RequiredUser,
) -> None:
    """Revoke an API key.

    Users can only revoke their own keys unless they are superusers.

    Args:
        key_id: ID of the key to revoke.

    Raises:
        401: If not authenticated.
        404: If key not found or not owned by user.
    """
    auth_service.revoke_api_key(key_id, user)


# =============================================================================
# User Management (Superuser only)
# =============================================================================


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreate,
    auth_service: AuthServiceDep,
    user: SuperUser,
) -> UserResponse:
    """Create a new user (superuser only).

    Args:
        request: User creation request with email and optional password/details.

    Returns:
        Created user.

    Raises:
        401: If not authenticated.
        403: If not superuser.
        409: If user with email already exists.
    """
    new_user = auth_service.create_local_user(request)
    return UserResponse.model_validate(new_user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    auth_service: AuthServiceDep,
    user: SuperUser,
    include_inactive: bool = False,
) -> list[UserResponse]:
    """List all users (superuser only).

    Args:
        include_inactive: Include inactive users.

    Returns:
        List of users.

    Raises:
        401: If not authenticated.
        403: If not superuser.
    """
    users = auth_service.list_users(include_inactive=include_inactive)
    return [UserResponse.model_validate(u) for u in users]


@router.get("/users/{email}", response_model=UserResponse)
async def get_user(
    email: str,
    auth_service: AuthServiceDep,
    user: SuperUser,
) -> UserResponse:
    """Get a user by email (superuser only).

    Args:
        email: User email address.

    Returns:
        User details.

    Raises:
        401: If not authenticated.
        403: If not superuser.
        404: If user not found.
    """
    target_user = auth_service.get_user_by_email(email)
    return UserResponse.model_validate(target_user)


@router.post("/users/{email}/disable", response_model=UserResponse)
async def disable_user(
    email: str,
    auth_service: AuthServiceDep,
    user: SuperUser,
) -> UserResponse:
    """Disable a user account (superuser only).

    Disabling a user invalidates all their sessions and refresh tokens.

    Args:
        email: User email address.

    Returns:
        Updated user.

    Raises:
        401: If not authenticated.
        403: If not superuser.
        404: If user not found.
    """
    updated_user = auth_service.disable_user(email)
    return UserResponse.model_validate(updated_user)


@router.post("/users/{email}/enable", response_model=UserResponse)
async def enable_user(
    email: str,
    auth_service: AuthServiceDep,
    user: SuperUser,
) -> UserResponse:
    """Enable a user account (superuser only).

    Args:
        email: User email address.

    Returns:
        Updated user.

    Raises:
        401: If not authenticated.
        403: If not superuser.
        404: If user not found.
    """
    updated_user = auth_service.enable_user(email)
    return UserResponse.model_validate(updated_user)


@router.post("/users/{email}/set-superuser", response_model=UserResponse)
async def set_superuser(
    email: str,
    is_superuser: bool,
    auth_service: AuthServiceDep,
    user: SuperUser,
) -> UserResponse:
    """Set or remove superuser status (superuser only).

    Args:
        email: User email address.
        is_superuser: New superuser status.

    Returns:
        Updated user.

    Raises:
        401: If not authenticated.
        403: If not superuser.
        404: If user not found.
    """
    updated_user = auth_service.set_superuser(email, is_superuser)
    return UserResponse.model_validate(updated_user)
