from dataclasses import dataclass
from typing import Any, Optional

from app.review.schemas import LlmUsage


TOKENS_PER_MILLION = 1_000_000


@dataclass(frozen=True)
class DeepSeekPrice:
    input_cache_hit_usd_per_million: float
    input_cache_miss_usd_per_million: float
    output_usd_per_million: float


DEEPSEEK_PRICES: dict[str, DeepSeekPrice] = {
    "deepseek-v4-flash": DeepSeekPrice(
        input_cache_hit_usd_per_million=0.0028,
        input_cache_miss_usd_per_million=0.14,
        output_usd_per_million=0.28,
    ),
    "deepseek-v4-pro": DeepSeekPrice(
        input_cache_hit_usd_per_million=0.003625,
        input_cache_miss_usd_per_million=0.435,
        output_usd_per_million=0.87,
    ),
}

MODEL_ALIASES = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-flash",
}


def build_deepseek_usage(
    *,
    model: str,
    usage_payload: dict[str, Any],
    latency_ms: int,
) -> LlmUsage:
    prompt_tokens = _int_value(usage_payload.get("prompt_tokens"))
    completion_tokens = _int_value(usage_payload.get("completion_tokens"))
    total_tokens = _int_value(usage_payload.get("total_tokens")) or prompt_tokens + completion_tokens
    cache_hit_tokens = _int_value(usage_payload.get("prompt_cache_hit_tokens"))
    cache_miss_tokens = _int_value(usage_payload.get("prompt_cache_miss_tokens"))

    if cache_hit_tokens == 0 and cache_miss_tokens == 0:
        cache_miss_tokens = prompt_tokens

    estimated_cost = estimate_deepseek_cost_usd(
        model=model,
        prompt_cache_hit_tokens=cache_hit_tokens,
        prompt_cache_miss_tokens=cache_miss_tokens,
        completion_tokens=completion_tokens,
    )
    return LlmUsage(
        provider="deepseek",
        model=model,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        prompt_cache_hit_tokens=cache_hit_tokens,
        prompt_cache_miss_tokens=cache_miss_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost,
        pricing_note="Estimated from DeepSeek per-1M token pricing; actual billing may differ.",
    )


def estimate_deepseek_cost_usd(
    *,
    model: str,
    prompt_cache_hit_tokens: int,
    prompt_cache_miss_tokens: int,
    completion_tokens: int,
) -> Optional[float]:
    price = DEEPSEEK_PRICES.get(MODEL_ALIASES.get(model, model))
    if price is None:
        return None

    return (
        prompt_cache_hit_tokens / TOKENS_PER_MILLION * price.input_cache_hit_usd_per_million
        + prompt_cache_miss_tokens / TOKENS_PER_MILLION * price.input_cache_miss_usd_per_million
        + completion_tokens / TOKENS_PER_MILLION * price.output_usd_per_million
    )


def _int_value(value: Any) -> int:
    return int(value) if value is not None else 0
