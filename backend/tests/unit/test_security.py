"""Unit tests for :mod:`app.core.security`."""

from __future__ import annotations

import uuid
from datetime import timedelta

import jwt
import pytest
from app.core.security import (
    PasswordPolicyError,
    check_password_policy,
    create_access_token,
    decode_access_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_then_verify_succeeds(self) -> None:
        h = hash_password("Korrekt-Pferd-Batterie-9")
        assert verify_password("Korrekt-Pferd-Batterie-9", h)

    def test_verify_rejects_wrong_password(self) -> None:
        h = hash_password("Korrekt-Pferd-Batterie-9")
        assert not verify_password("Falsch-Pferd-Batterie-9", h)

    def test_hashes_are_salted_unique(self) -> None:
        assert hash_password("samesame12") != hash_password("samesame12")

    def test_verify_rejects_malformed_hash(self) -> None:
        assert not verify_password("anything", "not-a-real-hash")


class TestPasswordPolicy:
    @pytest.mark.parametrize(
        "pw",
        ["Sicher123!extra", "abcDEF12345!", "ZürcherKaffee9!"],
    )
    def test_accepts_strong_passwords(self, pw: str) -> None:
        check_password_policy(pw)

    @pytest.mark.parametrize(
        "pw",
        ["short1!", "alllowercase12", "ALLUPPER1234", "passwordpassword"],
    )
    def test_rejects_weak_passwords(self, pw: str) -> None:
        with pytest.raises(PasswordPolicyError):
            check_password_policy(pw)


class TestOpaqueTokens:
    def test_generate_returns_url_safe_string(self) -> None:
        t = generate_token()
        assert len(t) >= 60
        assert all(c.isalnum() or c in "-_" for c in t)

    def test_hash_token_is_deterministic_64_chars(self) -> None:
        assert hash_token("abc") == hash_token("abc")
        assert len(hash_token("abc")) == 64

    def test_different_tokens_hash_differently(self) -> None:
        assert hash_token("a") != hash_token("b")


class TestAccessTokens:
    def test_round_trip(self) -> None:
        uid = uuid.uuid4()
        token = create_access_token(uid)
        claims = decode_access_token(token)
        assert claims.sub == uid

    def test_expired_token_rejected(self) -> None:
        token = create_access_token(uuid.uuid4(), ttl=timedelta(seconds=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_tampered_token_rejected(self) -> None:
        token = create_access_token(uuid.uuid4())
        tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(tampered)
