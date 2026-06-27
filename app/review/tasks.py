from app.review.schemas import PullRequestReviewInput, ReviewFinding


def build_initial_findings(review_input: PullRequestReviewInput) -> list[ReviewFinding]:
    """Small deterministic fallback until real CrewAI task output is wired in."""
    if not review_input.diff_text.strip():
        return [
            ReviewFinding(
                file_path="PR diff",
                message="当前骨架尚未接入 GitHub diff 拉取，暂未发现可定位问题。",
            )
        ]

    findings: list[ReviewFinding] = []
    for file_path in review_input.files:
        if file_path.endswith((".env", ".pem", ".key")):
            findings.append(
                ReviewFinding(
                    file_path=file_path,
                    message="变更包含敏感配置或密钥类文件，请确认没有提交 secret。",
                )
            )

    if not findings:
        findings.append(
            ReviewFinding(
                file_path=review_input.files[0] if review_input.files else "PR diff",
                message="请补充关键路径测试，确保本次新增提交覆盖主要行为变化。",
            )
        )
    return findings
