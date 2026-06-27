from app.review.schemas import ReviewReport


COMMENT_MARKER = "<!-- crewai-review-agent -->"


class GitHubReviewPublisher:
    """Publishes review summaries and inline comments to GitHub."""

    async def publish_summary(
        self,
        *,
        repo_full_name: str,
        pr_number: int,
        submitter: str,
        report: ReviewReport,
    ) -> str:
        # TODO: Replace with issue comment API call in milestone 4.
        _ = (repo_full_name, pr_number)
        body = render_summary_comment(submitter=submitter, report=report)
        return str(abs(hash(body)))


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
