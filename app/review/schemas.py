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


class LlmUsage(BaseModel):
    provider: str
    model: str
    latency_ms: int
    prompt_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: Optional[float] = None
    pricing_note: str = ""


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
    llm_usage: Optional[LlmUsage] = None
