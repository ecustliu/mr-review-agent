from app.review.schemas import ReviewFinding, ReviewReport, RiskLevel


HIGH_RISK_KEYWORDS = {
    "auth",
    "authorization",
    "authentication",
    "permission",
    "password",
    "secret",
    "token",
    "sql",
    "payment",
    "schema",
}

MEDIUM_RISK_KEYWORDS = {
    "cache",
    "config",
    "migration",
    "timeout",
    "retry",
    "shared",
    "dependency",
    "test",
}


def classify_finding(finding: ReviewFinding) -> ReviewFinding:
    if finding.risk_level is not None:
        return finding

    haystack = f"{finding.file_path} {finding.message}".lower()
    if any(keyword in haystack for keyword in HIGH_RISK_KEYWORDS):
        finding.risk_level = RiskLevel.high
        finding.reason = finding.reason or "涉及安全、权限、数据或核心业务风险"
    elif any(keyword in haystack for keyword in MEDIUM_RISK_KEYWORDS):
        finding.risk_level = RiskLevel.medium
        finding.reason = finding.reason or "涉及配置、依赖、共享逻辑或测试缺口"
    else:
        finding.risk_level = RiskLevel.low
        finding.reason = finding.reason or "局部可维护性或可读性建议"
    return finding


def build_report(findings: list[ReviewFinding], summary: str) -> ReviewReport:
    report = ReviewReport(summary=summary, findings=[classify_finding(finding) for finding in findings])

    for finding in report.findings:
        rendered = render_finding(finding)
        if finding.risk_level == RiskLevel.high:
            report.high_risk.append(rendered)
        elif finding.risk_level == RiskLevel.medium:
            report.medium_risk.append(rendered)
        else:
            report.low_risk.append(rendered)

    return report


def render_finding(finding: ReviewFinding) -> str:
    location = f"`{finding.file_path}`"
    if finding.line is not None:
        location = f"{location}:{finding.line}"
    return f"{location}: {finding.message}"
