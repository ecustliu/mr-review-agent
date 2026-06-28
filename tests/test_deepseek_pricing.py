from app.review.pricing import estimate_deepseek_cost_usd


def test_estimate_deepseek_cost_uses_cache_hit_miss_and_output_prices() -> None:
    cost = estimate_deepseek_cost_usd(
        model="deepseek-v4-flash",
        prompt_cache_hit_tokens=1_000_000,
        prompt_cache_miss_tokens=1_000_000,
        completion_tokens=1_000_000,
    )

    assert cost == 0.0028 + 0.14 + 0.28


def test_estimate_deepseek_cost_maps_legacy_chat_to_flash_pricing() -> None:
    cost = estimate_deepseek_cost_usd(
        model="deepseek-chat",
        prompt_cache_hit_tokens=0,
        prompt_cache_miss_tokens=1_000_000,
        completion_tokens=1_000_000,
    )

    assert cost == 0.14 + 0.28
