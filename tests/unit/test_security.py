from app.core.security import (
    create_access_token,
    decode_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    pw = "super-secret-password"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_api_key_generation():
    raw, key_hash = generate_api_key()
    assert len(raw) > 20
    assert len(key_hash) == 64  # SHA-256 hex
    assert key_hash == hash_api_key(raw)


def test_jwt_encode_decode():
    token = create_access_token("user-123", extra={"role": "admin"})
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"
