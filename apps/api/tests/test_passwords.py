from cartlyf_api.auth.passwords import fingerprint, hash_password, needs_rehash, verify_password


def test_AUTH_02_hash_is_argon2id() -> None:
    assert hash_password("correct horse battery").startswith("$argon2id$")


def test_verify_password() -> None:
    hashed = hash_password("correct horse battery")
    assert verify_password(hashed, "correct horse battery")
    assert not verify_password(hashed, "wrong")
    assert not verify_password(None, "anything")
    assert not verify_password("not-a-hash", "anything")


def test_fresh_hash_needs_no_rehash() -> None:
    assert not needs_rehash(hash_password("correct horse battery"))


def test_fingerprint_changes_with_hash() -> None:
    assert fingerprint(hash_password("a" * 12)) != fingerprint(hash_password("a" * 12))
    assert fingerprint(None) == fingerprint(None)
