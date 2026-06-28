import json
import re
from typing import Callable, Optional

import httpx
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.review.guidelines import build_review_guidelines
from app.review.risk import build_report
from app.review.schemas import PullRequestReviewInput, ReviewFinding, ReviewReport
from app.review.tasks import build_initial_findings


class PullRequestReviewCrew:
    """Entry point for the CrewAI review workflow.

    The class keeps the workflow boundary stable while the concrete CrewAI
    agents/tasks are added in the next milestone.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        http_client_factory: Optional[Callable[[], httpx.Client]] = None,
    ):
        self.settings = settings or get_settings()
        self.http_client_factory = http_client_factory or self._default_http_client

    def review(self, review_input: PullRequestReviewInput) -> ReviewReport:
        fallback_report = self._fallback_review(review_input)
        if not self._llm_enabled():
            return fallback_report

        try:
            return self._review_with_llm(review_input)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError, IndexError):
            return fallback_report

    def _fallback_review(self, review_input: PullRequestReviewInput) -> ReviewReport:
        findings = build_initial_findings(review_input)
        summary = (
            f"本次变更来自 `{review_input.repo_full_name}` PR #{review_input.pr_number}，"
            f"当前 review 范围为 `{review_input.base_sha}...{review_input.head_sha}`。"
        )
        if review_input.diff_truncated:
            summary += " diff 超过配置上限，已裁剪后 review。"
        return build_report(findings, summary)

    def _llm_enabled(self) -> bool:
        return bool(
            self.settings.llm_provider == "deepseek"
            and self.settings.llm_api_key
            and self.settings.llm_model
            and self.settings.llm_base_url
        )

    def _review_with_llm(self, review_input: PullRequestReviewInput) -> ReviewReport:
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(review_input)},
            ],
            "temperature": 0.1,
            "max_tokens": 1800,
            "response_format": {"type": "json_object"},
        }
        with self.http_client_factory() as client:
            response = client.post("/chat/completions", json=payload)
            response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]
        return self._parse_llm_report(content)

    def _parse_llm_report(self, content: str) -> ReviewReport:
        data = json.loads(_strip_json_fence(content))
        findings = [ReviewFinding.model_validate(item) for item in data.get("findings", [])]
        summary = str(data.get("summary") or "模型未返回总结。")
        return build_report(findings, summary)

    def _default_http_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.llm_base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _system_prompt(self) -> str:
        return (
            "你是资深代码审查助手。只审查给定 pull request diff 中实际出现的变更，"
            "优先指出 bug、权限/安全风险、数据一致性问题、缺失测试和可维护性问题。"
            "不要编造没有依据的问题。必须只返回 JSON 对象，不要返回 Markdown。"
        )

    def _user_prompt(self, review_input: PullRequestReviewInput) -> str:
        guidelines = build_review_guidelines(review_input)
        guidelines_section = f"Review guidelines:\n{guidelines}\n" if guidelines else ""
        return (
            "请审查下面的 GitHub Pull Request diff，并按指定 JSON schema 返回结果。\n"
            "请优先依据适用的语言规范判断问题是否真实、具体、可操作。\n"
            "JSON schema:\n"
            "{\n"
            '  "summary": "简短中文总结",\n'
            '  "findings": [\n'
            "    {\n"
            '      "file_path": "文件路径",\n'
            '      "line": 123,\n'
            '      "risk_level": "high|medium|low",\n'
            '      "message": "具体问题和建议",\n'
            '      "reason": "为什么这是这个风险等级"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "如果没有发现明确问题，findings 返回空数组。\n\n"
            f"Repository: {review_input.repo_full_name}\n"
            f"PR: #{review_input.pr_number}\n"
            f"Submitter: {review_input.submitter}\n"
            f"Range: {review_input.base_sha}...{review_input.head_sha}\n"
            f"Diff truncated: {review_input.diff_truncated}\n"
            f"Files: {', '.join(review_input.files) or '(unknown)'}\n\n"
            f"{guidelines_section}"
            "Diff:\n"
            f"{review_input.diff_text}"
        )


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return match.group(1) if match else stripped
