from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_does_not_return_plain_password() -> None:
    assert hash_password("StrongPass123") != "StrongPass123"


def test_password_hash_is_salted() -> None:
    assert hash_password("StrongPass123") != hash_password("StrongPass123")


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("StrongPass123")
    assert verify_password("StrongPass123", hashed)


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("StrongPass123")
    assert not verify_password("WrongPass123", hashed)


def test_access_token_contains_access_type() -> None:
    assert decode_token(create_access_token("abc"))["type"] == "access"


def test_refresh_token_contains_refresh_type() -> None:
    assert decode_token(create_refresh_token("abc"))["type"] == "refresh"

