from typing import Optional

import httpx
import pytest

from app.config import Settings
from app.github.client import GitHubClient, trim_diff


class FakeAuth:
    def __init__(self) -> None:
        self.installation_id: Optional[int] = None

    async def installation_token(self, installation_id: Optional[int] = None) -> str:
        self.installation_id = installation_id
        return "token"


@pytest.mark.asyncio
async def test_collect_pull_request_diff_uses_compare_for_incremental_review() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.headers["Accept"] == "application/vnd.github.diff":
            return httpx.Response(200, text="diff --git a/app.py b/app.py\n+change")
        return httpx.Response(200, json={"files": [{"filename": "app.py"}]})

    auth = FakeAuth()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.github.test",
    ) as http_client:
        client = GitHubClient(
            Settings(github_webhook_secret="secret", max_diff_lines=10),
            auth=auth,  # type: ignore[arg-type]
            http_client=http_client,
        )
        diff = await client.collect_pull_request_diff(
            repo_full_name="octo/repo",
            pr_number=1,
            base_sha="base",
            head_sha="head",
            previous_head_sha="old-head",
            installation_id=123,
        )

    assert diff.base_sha == "old-head"
    assert diff.head_sha == "head"
    assert diff.files == ["app.py"]
    assert diff.diff_text.startswith("diff --git")
    assert auth.installation_id == 123
    assert requests[0].url.path == "/repos/octo/repo/compare/old-head...head"


def test_trim_diff_marks_truncated_content() -> None:
    diff, truncated = trim_diff("1\n2\n3", 2)

    assert truncated is True
    assert diff.splitlines() == ["1", "2", "... diff truncated after 2 lines ..."]
