import hashlib
import hmac
from dataclasses import dataclass
from typing import Any, Optional


SUPPORTED_PR_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


class WebhookError(ValueError):
    pass


def verify_signature(payload_body: bytes, signature_header: Optional[str], secret: str) -> bool:
    if not secret:
        raise WebhookError("GITHUB_WEBHOOK_SECRET is required")
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@dataclass(frozen=True)
class PullRequestEvent:
    delivery_id: str
    action: str
    repo_full_name: str
    pr_number: int
    head_sha: str
    base_sha: str
    submitter: str
    sender: str
    is_draft: bool


def is_supported_pr_event(event_name: str, action: str) -> bool:
    return event_name == "pull_request" and action in SUPPORTED_PR_ACTIONS


def parse_pull_request_event(delivery_id: str, payload: dict[str, Any]) -> PullRequestEvent:
    try:
        pull_request = payload["pull_request"]
        return PullRequestEvent(
            delivery_id=delivery_id,
            action=payload["action"],
            repo_full_name=payload["repository"]["full_name"],
            pr_number=int(pull_request["number"]),
            head_sha=pull_request["head"]["sha"],
            base_sha=pull_request["base"]["sha"],
            submitter=pull_request["user"]["login"],
            sender=payload["sender"]["login"],
            is_draft=bool(pull_request.get("draft", False)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise WebhookError("Invalid pull_request webhook payload") from exc
