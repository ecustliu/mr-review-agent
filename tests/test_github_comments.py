from typing import Any, Optional

import pytest

from app.github.comments import COMMENT_MARKER, GitHubReviewPublisher
from app.review.schemas import ReviewReport


class FakeGitHubClient:
    def __init__(self, comments: list[dict[str, Any]]) -> None:
        self.comments = comments
        self.created_payload: Optional[dict[str, Any]] = None
        self.patched_payload: Optional[dict[str, Any]] = None

    async def get_json(self, path: str, *, installation_id: Optional[int] = None) -> Any:
        _ = (path, installation_id)
        return self.comments

    async def post_json(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        installation_id: Optional[int] = None,
    ) -> dict[str, Any]:
        _ = (path, installation_id)
        self.created_payload = payload
        return {"id": 10}

    async def patch_json(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        installation_id: Optional[int] = None,
    ) -> dict[str, Any]:
        _ = (path, installation_id)
        self.patched_payload = payload
        return {"id": 9}


@pytest.mark.asyncio
async def test_publish_summary_updates_existing_marker_comment() -> None:
    github_client = FakeGitHubClient(comments=[{"id": 9, "body": f"{COMMENT_MARKER}\nold"}])
    publisher = GitHubReviewPublisher(github_client=github_client)  # type: ignore[arg-type]

    comment_id = await publisher.publish_summary(
        repo_full_name="octo/repo",
        pr_number=1,
        submitter="alice",
        report=ReviewReport(summary="done"),
        installation_id=123,
    )

    assert comment_id == "9"
    assert github_client.created_payload is None
    assert github_client.patched_payload is not None
    assert COMMENT_MARKER in github_client.patched_payload["body"]


@pytest.mark.asyncio
async def test_publish_summary_creates_comment_when_marker_missing() -> None:
    github_client = FakeGitHubClient(comments=[])
    publisher = GitHubReviewPublisher(github_client=github_client)  # type: ignore[arg-type]

    comment_id = await publisher.publish_summary(
        repo_full_name="octo/repo",
        pr_number=1,
        submitter="alice",
        report=ReviewReport(summary="done"),
        installation_id=123,
    )

    assert comment_id == "10"
    assert github_client.created_payload is not None
    assert COMMENT_MARKER in github_client.created_payload["body"]
    assert github_client.patched_payload is None
