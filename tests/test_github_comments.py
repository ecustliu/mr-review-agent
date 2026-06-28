from typing import Any, Optional

import pytest

from app.github.comments import COMMENT_MARKER, GitHubReviewPublisher, render_summary_comment
from app.review.schemas import LlmUsage, ReviewReport


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


def test_render_summary_comment_includes_llm_usage() -> None:
    comment = render_summary_comment(
        submitter="alice",
        report=ReviewReport(
            summary="done",
            llm_usage=LlmUsage(
                provider="deepseek",
                model="deepseek-v4-flash",
                latency_ms=3210,
                prompt_tokens=1000,
                prompt_cache_hit_tokens=200,
                prompt_cache_miss_tokens=800,
                completion_tokens=100,
                total_tokens=1100,
                estimated_cost_usd=0.00014,
            ),
        ),
    )

    assert "模型调用信息" in comment
    assert "模型：`deepseek-v4-flash`" in comment
    assert "耗时：3.21s" in comment
    assert "cache hit 200, cache miss 800" in comment
    assert "预估花费：$0.00014000 USD" in comment
