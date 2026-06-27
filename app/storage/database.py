from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.storage.models import Base, ReviewState, WebhookDelivery


def make_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db(target_engine: Optional[Engine] = None) -> None:
    Base.metadata.create_all(bind=target_engine or engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def configure_database(settings: Settings) -> None:
    global engine, SessionLocal

    engine = make_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class ReviewStateRepository:
    def __init__(self, session: Session):
        self.session = session

    def mark_delivery_seen(
        self,
        *,
        delivery_id: str,
        event: str,
        action: Optional[str],
        repo_full_name: Optional[str],
        pr_number: Optional[int],
    ) -> bool:
        existing = self.session.scalar(
            select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id)
        )
        if existing:
            return False

        self.session.add(
            WebhookDelivery(
                delivery_id=delivery_id,
                event=event,
                action=action,
                repo_full_name=repo_full_name,
                pr_number=pr_number,
            )
        )
        self.session.commit()
        return True

    def get_state(self, repo_full_name: str, pr_number: int) -> Optional[ReviewState]:
        return self.session.scalar(
            select(ReviewState).where(
                ReviewState.repo_full_name == repo_full_name,
                ReviewState.pr_number == pr_number,
            )
        )

    def should_review(self, repo_full_name: str, pr_number: int, head_sha: str) -> bool:
        state = self.get_state(repo_full_name, pr_number)
        return state is None or state.last_reviewed_head_sha != head_sha

    def mark_reviewed(
        self,
        *,
        repo_full_name: str,
        pr_number: int,
        head_sha: str,
        comment_id: Optional[str] = None,
    ) -> ReviewState:
        state = self.get_state(repo_full_name, pr_number)
        if state is None:
            state = ReviewState(repo_full_name=repo_full_name, pr_number=pr_number)
            self.session.add(state)

        state.last_reviewed_head_sha = head_sha
        state.last_reviewed_at = datetime.now(timezone.utc)
        state.last_review_comment_id = comment_id
        self.session.commit()
        self.session.refresh(state)
        return state
