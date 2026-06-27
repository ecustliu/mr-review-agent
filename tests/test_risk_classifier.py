from app.review.risk import build_report
from app.review.schemas import ReviewFinding, RiskLevel


def test_risk_classifier_groups_findings_by_level() -> None:
    report = build_report(
        [
            ReviewFinding(file_path="src/auth/session.py", message="token 过期后仍可能放行请求"),
            ReviewFinding(file_path="src/config/cache.py", message="timeout 缺少回退策略"),
            ReviewFinding(file_path="src/utils/name.py", message="命名可以更明确"),
        ],
        summary="summary",
    )

    assert report.findings[0].risk_level == RiskLevel.high
    assert report.findings[1].risk_level == RiskLevel.medium
    assert report.findings[2].risk_level == RiskLevel.low
    assert len(report.high_risk) == 1
    assert len(report.medium_risk) == 1
    assert len(report.low_risk) == 1
