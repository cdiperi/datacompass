"""Configuration schemas for data source adapters."""

from enum import Enum

from pydantic import BaseModel, Field, SecretStr, model_validator


class AuthMethod(str, Enum):
    """Authentication methods for cloud data sources."""

    PERSONAL_TOKEN = "personal_token"
    SERVICE_PRINCIPAL = "service_principal"
    MANAGED_IDENTITY = "managed_identity"
    USERNAME_PASSWORD = "username_password"
    OAUTH = "oauth"


class DatabricksConfig(BaseModel):
    """Configuration for Databricks Unity Catalog connections.

    Supports three authentication methods:
    - Personal access token (default, simplest for development)
    - Service principal (recommended for production)
    - Managed identity (for Azure workloads)
    """

    # Connection settings
    host: str = Field(
        ...,
        description="Databricks workspace hostname (e.g., adb-xxx.azuredatabricks.net)",
    )
    http_path: str = Field(
        ...,
        description="SQL warehouse HTTP path (e.g., /sql/1.0/warehouses/abc123)",
    )
    catalog: str = Field(
        ...,
        description="Unity Catalog name to scan",
    )

    # Authentication
    auth_method: AuthMethod = Field(
        default=AuthMethod.PERSONAL_TOKEN,
        description="Authentication method to use",
    )

    # Personal token auth
    access_token: SecretStr | None = Field(
        default=None,
        description="Databricks personal access token",
    )

    # Service principal auth (Azure)
    client_id: str | None = Field(
        default=None,
        description="Azure AD application (client) ID",
    )
    client_secret: SecretStr | None = Field(
        default=None,
        description="Azure AD client secret",
    )
    tenant_id: str | None = Field(
        default=None,
        description="Azure AD tenant ID",
    )

    # Filtering
    schema_filter: str | None = Field(
        default=None,
        description="Regex pattern to filter schemas (e.g., '^(sales|marketing)$')",
    )

    # Timeouts and options
    timeout_seconds: int = Field(
        default=300,
        description="Query timeout in seconds",
        ge=1,
        le=3600,
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for transient errors",
        ge=0,
        le=10,
    )

    @model_validator(mode="after")
    def validate_auth(self) -> "DatabricksConfig":
        """Validate that required auth fields are provided."""
        if self.auth_method == AuthMethod.PERSONAL_TOKEN:
            if not self.access_token:
                raise ValueError("access_token is required for personal_token auth")

        elif self.auth_method == AuthMethod.SERVICE_PRINCIPAL:
            missing = []
            if not self.client_id:
                missing.append("client_id")
            if not self.client_secret:
                missing.append("client_secret")
            if not self.tenant_id:
                missing.append("tenant_id")
            if missing:
                raise ValueError(
                    f"Missing required fields for service_principal auth: {', '.join(missing)}"
                )

        elif self.auth_method == AuthMethod.MANAGED_IDENTITY:
            # No additional fields required for managed identity
            pass

        return self
