from typing import Annotated
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.github.webhook import (
    WebhookError,
    is_supported_pr_event,
    parse_pull_request_event,
    verify_signature,
)
from app.review.service import ReviewService
from app.storage.database import ReviewStateRepository, get_db, init_db

app = FastAPI(title="GitHub MR Review Agent")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def get_review_service() -> ReviewService:
    return ReviewService()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_github_event: Annotated[Optional[str], Header()] = None,
    x_github_delivery: Annotated[Optional[str], Header()] = None,
    x_hub_signature_256: Annotated[Optional[str], Header()] = None,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db),
    review_service: ReviewService = Depends(get_review_service),
) -> dict[str, str]:
    body = await request.body()
    try:
        signature_ok = verify_signature(body, x_hub_signature_256, settings.github_webhook_secret)
    except WebhookError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if not signature_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    if not x_github_event or not x_github_delivery:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing GitHub headers")

    payload = await request.json()
    action = payload.get("action")
    if not is_supported_pr_event(x_github_event, action):
        return {"status": "ignored", "reason": "unsupported event or action"}

    try:
        pr_event = parse_pull_request_event(x_github_delivery, payload)
    except WebhookError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if pr_event.is_draft and not settings.review_draft_pr:
        return {"status": "ignored", "reason": "draft pull request"}

    state_repository = ReviewStateRepository(session)
    is_new_delivery = state_repository.mark_delivery_seen(
        delivery_id=pr_event.delivery_id,
        event=x_github_event,
        action=pr_event.action,
        repo_full_name=pr_event.repo_full_name,
        pr_number=pr_event.pr_number,
    )
    if not is_new_delivery:
        return {"status": "skipped", "reason": "duplicate delivery"}

    if not state_repository.should_review(pr_event.repo_full_name, pr_event.pr_number, pr_event.head_sha):
        return {"status": "skipped", "reason": "head sha already reviewed"}

    await review_service.review_pull_request(event=pr_event, state_repository=state_repository)
    return {"status": "reviewed"}
