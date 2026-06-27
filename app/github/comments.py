from typing import Any, Optional

from app.config import Settings, get_settings
from app.github.client import GitHubClient
from app.review.schemas import ReviewReport


COMMENT_MARKER = "<!-- crewai-review-agent -->"


class GitHubReviewPublisher:
    """Publishes review summaries and inline comments to GitHub."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        github_client: Optional[GitHubClient] = None,
    ):
        self.settings = settings or get_settings()
        self.github_client = github_client or GitHubClient(self.settings)

    async def publish_summary(
        self,
        *,
        repo_full_name: str,
        pr_number: int,
        submitter: str,
        report: ReviewReport,
        installation_id: Optional[int] = None,
    ) -> str:
        body = render_summary_comment(submitter=submitter, report=report)
        existing_comment = await self._find_existing_summary_comment(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            installation_id=installation_id,
        )
        if existing_comment:
            updated = await self.github_client.patch_json(
                f"/repos/{repo_full_name}/issues/comments/{existing_comment['id']}",
                payload={"body": body},
                installation_id=installation_id,
            )
            return str(updated["id"])

        created = await self.github_client.post_json(
            f"/repos/{repo_full_name}/issues/{pr_number}/comments",
            payload={"body": body},
            installation_id=installation_id,
        )
        return str(created["id"])

    async def _find_existing_summary_comment(
        self,
        *,
        repo_full_name: str,
        pr_number: int,
        installation_id: Optional[int],
    ) -> Optional[dict[str, Any]]:
        comments = await self._list_issue_comments(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            installation_id=installation_id,
        )
        for comment in comments:
            if COMMENT_MARKER in comment.get("body", ""):
                return comment
        return None

    async def _list_issue_comments(
        self,
        *,
        repo_full_name: str,
        pr_number: int,
        installation_id: Optional[int],
    ) -> list[dict[str, Any]]:
        page = 1
        comments: list[dict[str, Any]] = []
        while True:
            payload = await self.github_client.get_json(
                f"/repos/{repo_full_name}/issues/{pr_number}/comments?per_page=100&page={page}",
                installation_id=installation_id,
            )
            if not payload:
                return comments
            comments.extend(payload)
            if len(payload) < 100:
                return comments
            page += 1


def render_summary_comment(*, submitter: str, report: ReviewReport) -> str:
    sections = [
        COMMENT_MARKER,
        f"@{submitter} 本次新增提交已完成自动 review，建议优先处理高风险问题。",
        "",
        "## 高风险",
        _render_findings(report.high_risk),
        "",
        "## 中风险",
        _render_findings(report.medium_risk),
        "",
        "## 低风险",
        _render_findings(report.low_risk),
        "",
        "## 总结",
        report.summary or "本次变更暂无额外总结。",
    ]
    return "\n".join(sections)


def _render_findings(findings: list[str]) -> str:
    if not findings:
        return "- 暂无"
    return "\n".join(f"- {finding}" for finding in findings)
