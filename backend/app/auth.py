"""Mock role-based authentication.

Deliberately not production auth. There is no CAC/PIV, no real session store,
and the token is an opaque random string kept in memory. Passwords are stored
salted-and-hashed (PBKDF2-HMAC-SHA256) rather than in plaintext, so the storage
pattern is correct even though the accounts are fake.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass

_ITERATIONS = 120_000


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)


@dataclass
class User:
    username: str
    role: str  # "coordinator" | "admin"
    salt: bytes
    pw_hash: bytes


def _make_user(username: str, password: str, role: str) -> User:
    salt = os.urandom(16)
    return User(username, role, salt, _hash_password(password, salt))


# Seed accounts for the prototype. Real deployments would not ship credentials.
_USERS: dict[str, User] = {
    u.username: u
    for u in (
        _make_user("coordinator", "unite-demo", "coordinator"),
        _make_user("admin", "unite-admin", "admin"),
    )
}

# token -> username, for the lifetime of the process.
_TOKENS: dict[str, str] = {}


def authenticate(username: str, password: str) -> str | None:
    """Return a bearer token on success, else None."""
    user = _USERS.get(username)
    if user is None:
        return None
    candidate = _hash_password(password, user.salt)
    if not hmac.compare_digest(candidate, user.pw_hash):
        return None
    token = secrets.token_urlsafe(24)
    _TOKENS[token] = username
    return token


def role_for_token(token: str) -> str | None:
    username = _TOKENS.get(token)
    if username is None:
        return None
    return _USERS[username].role
