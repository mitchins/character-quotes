"""Small bearer-token guard for the deployed management API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, Request, status

AUTH_ENABLED = "CHARACTER_QUOTES_SEARCH_AUTH"
AUTH_TOKEN = "CHARACTER_QUOTES_SEARCH_BEARER_TOKEN"
VERIFIER_FILE = "CHARACTER_QUOTES_SEARCH_BEARER_VERIFIER_FILE"
DEFAULT_VERIFIER_FILE = "/data/search-bearer-token.scrypt"


def enabled(value: str | None) -> bool:
    return value == "true"


@dataclass(frozen=True)
class TokenVerifier:
    salt: bytes
    digest: bytes

    @classmethod
    def from_token(cls, token: str) -> TokenVerifier:
        salt = secrets.token_bytes(16)
        return cls(salt=salt, digest=derive(token, salt))

    @classmethod
    def read(cls, path: Path) -> TokenVerifier:
        try:
            encoded_salt, encoded_digest = path.read_text(encoding="ascii").split(":")
            return cls(
                salt=base64.b64decode(encoded_salt, validate=True),
                digest=base64.b64decode(encoded_digest, validate=True),
            )
        except (OSError, ValueError) as error:
            raise RuntimeError(f"invalid search bearer verifier: {path}") from error

    def write_new(self, path: Path) -> bool:
        encoded = ":".join(
            (
                base64.b64encode(self.salt).decode("ascii"),
                base64.b64encode(self.digest).decode("ascii"),
            )
        )
        temporary_path = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        try:
            descriptor = os.open(
                temporary_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary_path, path)
            except FileExistsError:
                return False
            return True
        finally:
            temporary_path.unlink(missing_ok=True)

    def matches(self, token: str) -> bool:
        return hmac.compare_digest(self.digest, derive(token, self.salt))


def derive(token: str, salt: bytes) -> bytes:
    return hashlib.scrypt(token.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)


@dataclass(frozen=True)
class SearchAuth:
    verifier: TokenVerifier | None
    explicit_token: str | None

    @classmethod
    def from_environment(cls) -> SearchAuth:
        if not enabled(os.getenv(AUTH_ENABLED)):
            return cls(verifier=None, explicit_token=None)
        explicit_token = os.getenv(AUTH_TOKEN)
        if explicit_token:
            return cls(verifier=None, explicit_token=explicit_token)
        path = Path(os.getenv(VERIFIER_FILE, DEFAULT_VERIFIER_FILE))
        if path.exists():
            return cls(verifier=TokenVerifier.read(path), explicit_token=None)
        token = secrets.token_urlsafe(32)
        verifier = TokenVerifier.from_token(token)
        if verifier.write_new(path):
            print(
                f"Generated search Bearer token (shown once; save it now): {token}",
                flush=True,
            )
            return cls(verifier=verifier, explicit_token=None)
        return cls(verifier=TokenVerifier.read(path), explicit_token=None)

    def require(self, request: Request) -> None:
        if self.verifier is None and self.explicit_token is None:
            return
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        valid = scheme.lower() == "bearer" and bool(token) and self.matches(token)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def matches(self, token: str) -> bool:
        if self.explicit_token is not None:
            return hmac.compare_digest(self.explicit_token, token)
        return self.verifier is not None and self.verifier.matches(token)
