"""RS256 JWT issuance and verification.

We sign access tokens with a private RSA key and expose a JWKS endpoint
for clients. The service lazily generates a key pair if none exists at the
configured paths (development convenience). In production, keys are mounted
from a secret manager.
"""

from __future__ import annotations

import base64
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidTokenError as PyJWTInvalidTokenError,
)

from ...settings import Settings, get_settings
from ..errors import TokenExpiredError
from ..ids import new_ulid
from ..time import utc_now


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Claims for an issued access token."""

    sub: str
    tenant_id: str
    scopes: tuple[str, ...]
    mfa: bool
    jti: str = field(default_factory=lambda: new_ulid())
    iat: int = field(default_factory=lambda: int(time.time()))
    exp: int = 0
    iss: str = "kepler.api"
    aud: str = "kepler.web"

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub": self.sub,
            "tid": self.tenant_id,
            "scope": " ".join(self.scopes),
            "mfa": self.mfa,
            "jti": self.jti,
            "iat": self.iat,
            "exp": self.exp,
            "iss": self.iss,
            "aud": self.aud,
            "typ": "access",
        }


@dataclass(frozen=True, slots=True)
class RefreshTokenClaims:
    """Claims for an issued refresh token. Contains no sensitive data."""

    sub: str
    family_id: str
    jti: str = field(default_factory=lambda: new_ulid())
    iat: int = field(default_factory=lambda: int(time.time()))
    exp: int = 0
    iss: str = "kepler.api"
    aud: str = "kepler.refresh"

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub": self.sub,
            "fid": self.family_id,
            "jti": self.jti,
            "iat": self.iat,
            "exp": self.exp,
            "iss": self.iss,
            "aud": self.aud,
            "typ": "refresh",
        }


class JWTService:
    """Issue and verify RS256 JWTs, expose JWKS."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._private_key: RSAPrivateKey | None = None
        self._public_key: RSAPublicKey | None = None
        self._key_id: str | None = None
        self._load_or_generate()

    @property
    def issuer(self) -> str:
        return self._settings.jwt_issuer

    def _load_or_generate(self) -> None:
        """Load keys from disk, or generate a 2048-bit pair if missing (dev)."""
        priv_path = Path(self._settings.jwt_private_key_path)
        pub_path = Path(self._settings.jwt_public_key_path)

        if priv_path.exists() and pub_path.exists():
            priv_pem = priv_path.read_bytes()
            pub_pem = pub_path.read_bytes()
            self._private_key = serialization.load_pem_private_key(priv_pem, password=None)  # type: ignore[assignment]
            self._public_key = serialization.load_pem_public_key(pub_pem)  # type: ignore[assignment]
            # Key ID is the SHA-256 of the public key DER
            self._key_id = self._compute_kid(self._public_key)
            return

        # Generate ephemeral key pair (development only)
        from cryptography.hazmat.primitives.asymmetric import rsa

        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = priv.public_key()
        self._private_key = priv
        self._public_key = pub
        self._key_id = self._compute_kid(pub)

        # Persist in dev so the same key is used across restarts
        if self._settings.app_env in ("development", "test"):
            priv_path.parent.mkdir(parents=True, exist_ok=True)
            priv_path.write_bytes(
                priv.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
            pub_path.write_bytes(
                pub.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )

    @staticmethod
    def _compute_kid(public_key: RSAPublicKey) -> str:
        """Compute a key ID as base64url(SHA-256(DER))."""
        import hashlib

        der = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        digest = hashlib.sha256(der).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")[:16]

    # ------------------------------------------------------------------ issue

    def issue_access(
        self,
        *,
        user_id: str,
        tenant_id: str,
        scopes: list[str],
        mfa: bool = False,
        audience: str | None = None,
    ) -> tuple[str, AccessTokenClaims]:
        """Issue an access token. Returns (jwt, claims)."""
        assert self._private_key is not None
        now = int(time.time())
        claims = AccessTokenClaims(
            sub=user_id,
            tenant_id=tenant_id,
            scopes=tuple(scopes),
            mfa=mfa,
            iat=now,
            exp=now + self._settings.access_token_ttl_seconds,
            iss=self._settings.jwt_issuer,
            aud=audience or self._settings.jwt_audience_web,
        )
        token = jwt.encode(
            claims.to_dict(),
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._key_id} if self._key_id else None,
        )
        return token, claims

    def issue_refresh(
        self,
        *,
        user_id: str,
        family_id: str,
    ) -> tuple[str, RefreshTokenClaims]:
        """Issue a refresh token. Returns (jwt, claims)."""
        assert self._private_key is not None
        now = int(time.time())
        claims = RefreshTokenClaims(
            sub=user_id,
            family_id=family_id,
            iat=now,
            exp=now + self._settings.refresh_token_ttl_seconds,
            iss=self._settings.jwt_issuer,
            aud=self._settings.jwt_issuer + ".refresh",
        )
        token = jwt.encode(
            claims.to_dict(),
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._key_id} if self._key_id else None,
        )
        return token, claims

    # ------------------------------------------------------------------ verify

    def verify_access(
        self,
        token: str,
        *,
        audience: str | None = None,
    ) -> AccessTokenClaims:
        """Verify an access token.

        `audience` (if provided) must match the `aud` claim. If omitted, the
        `aud` claim is read from settings (web / cli / api). For tokens issued
        via `issue_access`, the audience is `settings.jwt_audience_web` by
        default. Production should pass the explicit audience of the caller
        (e.g., `kepler.web` for the browser, `kepler.cli` for the CLI).
        """
        expected_aud = audience or self._settings.jwt_audience_web
        return self._verify(
            token,
            expected_type="access",
            expected_audience=expected_aud,
            verify_aud=True,
        )

    def verify_refresh(self, token: str) -> RefreshTokenClaims:
        """Verify a refresh token."""
        return self._verify(token, expected_type="refresh", expected_audience=self._settings.jwt_issuer + ".refresh")

    def _verify(
        self,
        token: str,
        *,
        expected_type: str,
        expected_audience: str | None,
        verify_aud: bool = True,
    ) -> Any:
        assert self._public_key is not None
        options: dict[str, Any] = {"require": ["exp", "iat", "iss", "sub", "jti"]}
        if not verify_aud:
            options["verify_aud"] = False
        try:
            payload: dict[str, Any] = jwt.decode(  # type: ignore[assignment]
                token,
                self._public_key,
                algorithms=["RS256"],
                issuer=self._settings.jwt_issuer,
                audience=expected_audience,
                options=options,
            )
        except ExpiredSignatureError as exc:
            raise TokenExpiredError("Token has expired") from exc
        except (InvalidIssuerError, InvalidAudienceError) as exc:
            raise _invalid_token(str(exc)) from exc
        except PyJWTInvalidTokenError as exc:
            raise _invalid_token("Invalid token") from exc

        if payload.get("typ") != expected_type:
            raise _invalid_token("Wrong token type")

        if expected_type == "access":
            return AccessTokenClaims(
                sub=payload["sub"],
                tenant_id=payload.get("tid", ""),
                scopes=tuple(payload.get("scope", "").split()) if payload.get("scope") else (),
                mfa=bool(payload.get("mfa", False)),
                jti=payload["jti"],
                iat=payload["iat"],
                exp=payload["exp"],
                iss=payload["iss"],
                aud=payload["aud"],
            )
        return RefreshTokenClaims(
            sub=payload["sub"],
            family_id=payload["fid"],
            jti=payload["jti"],
            iat=payload["iat"],
            exp=payload["exp"],
            iss=payload["iss"],
            aud=payload.get("aud", self._settings.jwt_issuer + ".refresh"),
        )

    # ------------------------------------------------------------------ jwks

    def jwks(self) -> dict[str, list[dict[str, str]]]:
        """Return the public JWKS document."""
        assert self._public_key is not None
        numbers = self._public_key.public_numbers()

        def _b64uint(value: int) -> str:
            byte_length = (value.bit_length() + 7) // 8
            return base64.urlsafe_b64encode(value.to_bytes(byte_length, "big")).rstrip(b"=").decode("ascii")

        jwk: dict[str, str] = {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": self._key_id or "",
            "n": _b64uint(numbers.n),
            "e": _b64uint(numbers.e),
        }
        return {"keys": [jwk]}


def _invalid_token(message: str) -> Exception:
    from ..errors import InvalidTokenError

    return InvalidTokenError(message)


_singleton: JWTService | None = None


def get_jwt_service() -> JWTService:
    """Return the process-wide JWT service instance."""
    global _singleton
    if _singleton is None:
        _singleton = JWTService(get_settings())
    return _singleton


def reset_jwt_service() -> None:
    """Reset the singleton (used in tests)."""
    global _singleton
    _singleton = None


__all__ = [
    "AccessTokenClaims",
    "RefreshTokenClaims",
    "JWTService",
    "get_jwt_service",
    "reset_jwt_service",
    "utc_now",
]
