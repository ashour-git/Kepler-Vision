"""Security primitives: password hashing, JWT, errors.

`api.deps` provides the FastAPI dependency-injection layer that uses
these primitives.
"""

from ..errors import InvalidTokenError, TokenExpiredError
from .password import hash_password, verify_password
from .jwt import (
    JWTService,
    AccessTokenClaims,
    RefreshTokenClaims,
)

__all__ = [
    "hash_password",
    "verify_password",
    "JWTService",
    "AccessTokenClaims",
    "RefreshTokenClaims",
    "InvalidTokenError",
    "TokenExpiredError",
]
