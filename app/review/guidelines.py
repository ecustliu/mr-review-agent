from app.review.schemas import PullRequestReviewInput


PYTHON_REVIEW_GUIDELINES = """Python review guidelines:
- Correctness: check changed control flow, boundary conditions, None handling, mutable default arguments, resource cleanup, and async/sync misuse.
- Security: flag hardcoded secrets, unsafe deserialization, command or SQL injection, path traversal, weak crypto, broad CORS/auth bypasses, and leaking sensitive data in logs.
- Error handling: prefer explicit exception types, preserve useful context, avoid swallowing exceptions, and ensure retries/timeouts are bounded.
- Typing and contracts: keep public function signatures typed, avoid unnecessary Any, validate external inputs with Pydantic or clear invariants, and keep return types consistent.
- FastAPI patterns: validate request data, avoid blocking I/O in async endpoints, use dependency injection consistently, and return appropriate HTTP status codes.
- Database and state: check transaction boundaries, idempotency, uniqueness assumptions, migrations/schema compatibility, and race conditions.
- Tests: require focused tests for changed behavior, security-sensitive paths, regression cases, and error branches; avoid brittle tests that only assert implementation details.
- Maintainability: prefer small functions, clear names, simple branching, no unrelated refactors, and no duplicate logic unless it preserves clarity.
- Observability: ensure important failures have actionable logs without exposing secrets.
- Dependencies and config: question new dependencies, unpinned runtime assumptions, unsafe defaults, and config values that should be environment-driven.
"""


def build_review_guidelines(review_input: PullRequestReviewInput) -> str:
    if any(file_path.endswith(".py") for file_path in review_input.files):
        return PYTHON_REVIEW_GUIDELINES
    return ""
