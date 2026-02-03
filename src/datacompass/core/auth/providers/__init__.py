"""Authentication providers for different auth backends."""

from datacompass.core.auth.providers.base import AuthProvider, AuthResult
from datacompass.core.auth.providers.disabled import DisabledAuthProvider
from datacompass.core.auth.providers.local import LocalAuthProvider

__all__ = [
    "AuthProvider",
    "AuthResult",
    "DisabledAuthProvider",
    "LocalAuthProvider",
]
