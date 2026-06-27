import hashlib
import hmac
import json
from collections.abc import Iterator
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.config import get_settings
from app.main import app, get_review_service
from app.storage.database import get_db
from app.storage.models import Base


SECRET = "test-secret"


class DummyReviewService:
    def __init__(self) -> None:
        self.calls = 0

    async def review_pull_request(self, **kwargs: Any) -> str:
        self.calls += 1
        event = kwargs["event"]
        repository = kwargs["state_repository"]
        repository.mark_reviewed(
            repo_full_name=event.repo_full_name,
            pr_number=event.pr_number,
            head_sha=event.head_sha,
            comment_id="comment-1",
        )
        return "comment-1"


def make_signature(body: bytes) -> str:
    digest = hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def encode_payload(data: dict[str, Any]) -> bytes:
    return json.dumps(data, separators=(",", ":")).encode("utf-8")


def payload(head_sha: str = "head-sha") -> dict[str, Any]:
    return {
        "action": "opened",
        "repository": {"full_name": "octo/repo"},
        "pull_request": {
            "number": 1,
            "draft": False,
            "head": {"sha": head_sha},
            "base": {"sha": "base-sha"},
            "user": {"login": "alice"},
        },
        "sender": {"login": "alice"},
    }


def test_github_webhook_reviews_supported_pr_event() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    review_service = DummyReviewService()

    def override_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_review_service] = lambda: review_service
    app.dependency_overrides[get_settings] = lambda: Settings(github_webhook_secret=SECRET)

    with TestClient(app) as client:
        body = encode_payload(payload())
        response = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "delivery-1",
                "X-Hub-Signature-256": make_signature(body),
            },
        )
        duplicate = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "delivery-1",
                "X-Hub-Signature-256": make_signature(body),
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "reviewed"}
    assert duplicate.json() == {"status": "skipped", "reason": "duplicate delivery"}
    assert review_service.calls == 1


def test_github_webhook_rejects_bad_signature() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(github_webhook_secret=SECRET)

    with TestClient(app) as client:
        response = client.post(
            "/webhooks/github",
            json=payload(),
            headers={
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "delivery-2",
                "X-Hub-Signature-256": "sha256=bad",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 401
