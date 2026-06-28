import httpx

from app.config import Settings
from app.review.crew import PullRequestReviewCrew
from app.review.schemas import PullRequestReviewInput, RiskLevel


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.requests: list[dict] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def post(self, path: str, json: dict) -> FakeResponse:
        self.requests.append({"path": path, "json": json})
        return self.response


def make_review_input() -> PullRequestReviewInput:
    return PullRequestReviewInput(
        repo_full_name="octo/repo",
        pr_number=7,
        base_sha="base",
        head_sha="head",
        submitter="monalisa",
        files=["app/auth.py"],
        diff_text="diff --git a/app/auth.py b/app/auth.py\n+token = request.headers.get('Authorization')",
    )


def make_settings() -> Settings:
    return Settings(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-chat",
        llm_base_url="https://api.deepseek.com",
    )


def test_review_uses_deepseek_json_response() -> None:
    client = FakeClient(
        FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"发现认证风险","findings":[{'
                                '"file_path":"app/auth.py",'
                                '"line":12,'
                                '"risk_level":"high",'
                                '"message":"Authorization token 未校验为空的情况。",'
                                '"reason":"认证路径变更属于高风险。"}]}'
                            )
                        }
                    }
                ]
            }
        )
    )
    crew = PullRequestReviewCrew(settings=make_settings(), http_client_factory=lambda: client)

    report = crew.review(make_review_input())

    assert client.requests[0]["path"] == "/chat/completions"
    assert report.summary == "发现认证风险"
    assert report.findings[0].risk_level == RiskLevel.high
    assert "`app/auth.py`:12" in report.high_risk[0]


def test_review_includes_python_guidelines_for_python_changes() -> None:
    client = FakeClient(
        FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"ok","findings":[]}',
                        }
                    }
                ]
            }
        )
    )
    crew = PullRequestReviewCrew(settings=make_settings(), http_client_factory=lambda: client)

    crew.review(make_review_input())

    user_prompt = client.requests[0]["json"]["messages"][1]["content"]
    assert "Python review guidelines" in user_prompt
    assert "FastAPI patterns" in user_prompt
    assert "avoid blocking I/O in async endpoints" in user_prompt


def test_review_omits_python_guidelines_for_non_python_changes() -> None:
    client = FakeClient(
        FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"ok","findings":[]}',
                        }
                    }
                ]
            }
        )
    )
    review_input = PullRequestReviewInput(
        repo_full_name="octo/repo",
        pr_number=7,
        base_sha="base",
        head_sha="head",
        submitter="monalisa",
        files=["README.md"],
        diff_text="diff --git a/README.md b/README.md\n+docs",
    )
    crew = PullRequestReviewCrew(settings=make_settings(), http_client_factory=lambda: client)

    crew.review(review_input)

    user_prompt = client.requests[0]["json"]["messages"][1]["content"]
    assert "Python review guidelines" not in user_prompt


def test_review_falls_back_when_llm_request_fails() -> None:
    def failing_client() -> httpx.Client:
        raise httpx.ConnectError("network unavailable")

    crew = PullRequestReviewCrew(settings=make_settings(), http_client_factory=failing_client)

    report = crew.review(make_review_input())

    assert "本次变更来自 `octo/repo` PR #7" in report.summary
    assert report.findings
