from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PullRequestDiff:
    repo_full_name: str
    pr_number: int
    base_sha: str
    head_sha: str
    diff_text: str
    files: list[str]


class GitHubClient:
    """Thin placeholder for GitHub App API calls used by the review workflow."""

    async def collect_pull_request_diff(
        self,
        *,
        repo_full_name: str,
        pr_number: int,
        base_sha: str,
        head_sha: str,
        previous_head_sha: Optional[str],
    ) -> PullRequestDiff:
        # TODO: Replace with GitHub App auth and PR/compare API calls in milestone 2.
        compare_base = previous_head_sha or base_sha
        return PullRequestDiff(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            base_sha=compare_base,
            head_sha=head_sha,
            diff_text="",
            files=[],
        )
