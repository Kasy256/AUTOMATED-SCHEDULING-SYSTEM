import hashlib

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
# Verified against when the user is unknown, so both login paths cost one argon2 verify.
_DUMMY_HASH = _hasher.hash("cartlyf-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        matched = _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return matched and password_hash is not None


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def fingerprint(password_hash: str | None) -> str:
    """Short digest of the hash; links carry it so a later password change invalidates them."""
    return hashlib.sha256((password_hash or "").encode()).hexdigest()[:16]
