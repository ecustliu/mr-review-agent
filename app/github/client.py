from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.config import Settings, get_settings
from app.github.auth import GitHubAppAuth


@dataclass(frozen=True)
class PullRequestDiff:
    repo_full_name: str
    pr_number: int
    base_sha: str
    head_sha: str
    diff_text: str
    files: list[str]
    truncated: bool = False


class GitHubApiError(RuntimeError):
    pass


class GitHubClient:
    """GitHub App REST client for PR review data."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        auth: Optional[GitHubAppAuth] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.settings = settings or get_settings()
        self.auth = auth or GitHubAppAuth(self.settings)
        self.http_client = http_client

    async def collect_pull_request_diff(
        self,
        *,
        repo_full_name: str,
        pr_number: int,
        base_sha: str,
        head_sha: str,
        previous_head_sha: Optional[str],
        installation_id: Optional[int] = None,
    ) -> PullRequestDiff:
        compare_base = previous_head_sha or base_sha
        if previous_head_sha:
            diff_text = await self._get_diff(
                f"/repos/{repo_full_name}/compare/{previous_head_sha}...{head_sha}",
                installation_id=installation_id,
            )
            compare_payload = await self.get_json(
                f"/repos/{repo_full_name}/compare/{previous_head_sha}...{head_sha}",
                installation_id=installation_id,
            )
            files = [file["filename"] for file in compare_payload.get("files", [])]
        else:
            diff_text = await self._get_diff(
                f"/repos/{repo_full_name}/pulls/{pr_number}",
                installation_id=installation_id,
            )
            files_payload = await self._get_paginated(
                f"/repos/{repo_full_name}/pulls/{pr_number}/files",
                installation_id=installation_id,
            )
            files = [file["filename"] for file in files_payload]

        trimmed_diff, truncated = trim_diff(diff_text, self.settings.max_diff_lines)
        return PullRequestDiff(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            base_sha=compare_base,
            head_sha=head_sha,
            diff_text=trimmed_diff,
            files=files,
            truncated=truncated,
        )

    async def get_json(self, path: str, *, installation_id: Optional[int] = None) -> Any:
        response = await self._request(
            "GET",
            path,
            installation_id=installation_id,
            accept="application/vnd.github+json",
        )
        return response.json()

    async def post_json(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        installation_id: Optional[int] = None,
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            path,
            installation_id=installation_id,
            accept="application/vnd.github+json",
            json=payload,
        )
        return response.json()

    async def patch_json(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        installation_id: Optional[int] = None,
    ) -> dict[str, Any]:
        response = await self._request(
            "PATCH",
            path,
            installation_id=installation_id,
            accept="application/vnd.github+json",
            json=payload,
        )
        return response.json()

    async def _get_diff(self, path: str, *, installation_id: Optional[int]) -> str:
        response = await self._request(
            "GET",
            path,
            installation_id=installation_id,
            accept="application/vnd.github.diff",
        )
        return response.text

    async def _get_paginated(self, path: str, *, installation_id: Optional[int]) -> list[dict[str, Any]]:
        page = 1
        items: list[dict[str, Any]] = []
        while True:
            response = await self._request(
                "GET",
                path,
                installation_id=installation_id,
                accept="application/vnd.github+json",
                params={"per_page": 100, "page": page},
            )
            page_items = response.json()
            if not page_items:
                return items
            items.extend(page_items)
            if "next" not in response.links:
                return items
            page += 1

    async def _request(
        self,
        method: str,
        path: str,
        *,
        installation_id: Optional[int],
        accept: str,
        **kwargs: Any,
    ) -> httpx.Response:
        token = await self.auth.installation_token(installation_id)
        headers = {
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if self.http_client is not None:
            response = await self.http_client.request(method, path, headers=headers, **kwargs)
        else:
            async with httpx.AsyncClient(base_url=self.settings.github_api_url) as client:
                response = await client.request(method, path, headers=headers, **kwargs)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GitHubApiError(f"GitHub API request failed: {method} {path}") from exc
        return response


def trim_diff(diff_text: str, max_lines: int) -> tuple[str, bool]:
    lines = diff_text.splitlines()
    if max_lines <= 0 or len(lines) <= max_lines:
        return diff_text, False

    trimmed = lines[:max_lines]
    trimmed.append(f"... diff truncated after {max_lines} lines ...")
    return "\n".join(trimmed), True
