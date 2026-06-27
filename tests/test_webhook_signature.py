import hashlib
import hmac

from app.github.webhook import verify_signature


def make_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_verify_signature_accepts_valid_signature() -> None:
    body = b'{"action":"opened"}'
    secret = "test-secret"

    assert verify_signature(body, make_signature(body, secret), secret)


def test_verify_signature_rejects_invalid_signature() -> None:
    body = b'{"action":"opened"}'

    assert not verify_signature(body, "sha256=bad", "test-secret")
