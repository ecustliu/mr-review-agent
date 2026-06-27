from app.review.risk import build_report
from app.review.schemas import PullRequestReviewInput, ReviewReport
from app.review.tasks import build_initial_findings


class PullRequestReviewCrew:
    """Entry point for the CrewAI review workflow.

    The class keeps the workflow boundary stable while the concrete CrewAI
    agents/tasks are added in the next milestone.
    """

    def review(self, review_input: PullRequestReviewInput) -> ReviewReport:
        findings = build_initial_findings(review_input)
        summary = (
            f"本次变更来自 `{review_input.repo_full_name}` PR #{review_input.pr_number}，"
            f"当前 review 范围为 `{review_input.base_sha}...{review_input.head_sha}`。"
        )
        return build_report(findings, summary)
