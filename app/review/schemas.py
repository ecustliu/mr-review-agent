from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ReviewFinding(BaseModel):
    file_path: str
    message: str
    risk_level: Optional[RiskLevel] = None
    line: Optional[int] = None
    reason: Optional[str] = None


class PullRequestReviewInput(BaseModel):
    repo_full_name: str
    pr_number: int
    base_sha: str
    head_sha: str
    submitter: str
    diff_text: str = ""
    files: list[str] = Field(default_factory=list)
    diff_truncated: bool = False


class ReviewReport(BaseModel):
    high_risk: list[str] = Field(default_factory=list)
    medium_risk: list[str] = Field(default_factory=list)
    low_risk: list[str] = Field(default_factory=list)
    summary: str = ""
    findings: list[ReviewFinding] = Field(default_factory=list)
