from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.storage.database import ReviewStateRepository
from app.storage.models import Base


def make_repository() -> ReviewStateRepository:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    return ReviewStateRepository(session)


def test_should_review_new_pr_then_skip_same_head_sha() -> None:
    repository = make_repository()

    assert repository.should_review("octo/repo", 1, "sha-1")

    repository.mark_reviewed(repo_full_name="octo/repo", pr_number=1, head_sha="sha-1")

    assert not repository.should_review("octo/repo", 1, "sha-1")
    assert repository.should_review("octo/repo", 1, "sha-2")


def test_delivery_id_is_idempotent() -> None:
    repository = make_repository()

    first = repository.mark_delivery_seen(
        delivery_id="delivery-1",
        event="pull_request",
        action="opened",
        repo_full_name="octo/repo",
        pr_number=1,
    )
    second = repository.mark_delivery_seen(
        delivery_id="delivery-1",
        event="pull_request",
        action="opened",
        repo_full_name="octo/repo",
        pr_number=1,
    )

    assert first is True
    assert second is False
