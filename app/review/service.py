from typing import Optional

from app.github.client import GitHubClient
from app.github.comments import GitHubReviewPublisher
from app.github.webhook import PullRequestEvent
from app.review.crew import PullRequestReviewCrew
from app.review.schemas import PullRequestReviewInput
from app.storage.database import ReviewStateRepository


class ReviewService:
    def __init__(
        self,
        *,
        github_client: Optional[GitHubClient] = None,
        review_crew: Optional[PullRequestReviewCrew] = None,
        publisher: Optional[GitHubReviewPublisher] = None,
    ):
        self.github_client = github_client or GitHubClient()
        self.review_crew = review_crew or PullRequestReviewCrew()
        self.publisher = publisher or GitHubReviewPublisher()

    async def review_pull_request(
        self,
        *,
        event: PullRequestEvent,
        state_repository: ReviewStateRepository,
    ) -> Optional[str]:
        state = state_repository.get_state(event.repo_full_name, event.pr_number)
        previous_head_sha = state.last_reviewed_head_sha if state else None

        diff = await self.github_client.collect_pull_request_diff(
            repo_full_name=event.repo_full_name,
            pr_number=event.pr_number,
            base_sha=event.base_sha,
            head_sha=event.head_sha,
            previous_head_sha=previous_head_sha,
            installation_id=event.installation_id,
        )
        review_context = build_review_context(event=event, state=state, files=diff.files)
        report = self.review_crew.review(
            PullRequestReviewInput(
                repo_full_name=event.repo_full_name,
                pr_number=event.pr_number,
                base_sha=diff.base_sha,
                head_sha=diff.head_sha,
                submitter=event.submitter,
                diff_text=f"{review_context}\n\n{diff.diff_text}",
                files=diff.files,
                diff_truncated=diff.truncated,
            )
        )
        comment_id = await self.publisher.publish_summary(
            repo_full_name=event.repo_full_name,
            pr_number=event.pr_number,
            submitter=event.submitter,
            report=report,
            installation_id=event.installation_id,
        )
        state_repository.mark_reviewed(
            repo_full_name=event.repo_full_name,
            pr_number=event.pr_number,
            head_sha=event.head_sha,
            comment_id=comment_id,
        )
        return comment_id


def build_review_context(
    *,
    event: PullRequestEvent,
    state: object,
    files: list[str],
) -> str:
    repo_name = event.repo_full_name.split("/")[1]
    primary_file = files[0]
    previous_comment = state.last_review_comment_id.split("-")[0]
    return (
        "Review context:\n"
        f"- repository: {repo_name}\n"
        f"- primary file: {primary_file}\n"
        f"- previous comment: {previous_comment}"
    )
