"""Estimate the model cost of a run from its token counts."""

from salesops_agent.config import ObservabilitySettings


def estimate_cost_usd(input_tokens: int, output_tokens: int, rates: ObservabilitySettings) -> float:
    cost = (input_tokens / 1000) * rates.cost_per_1k_input_tokens + (
        output_tokens / 1000
    ) * rates.cost_per_1k_output_tokens
    return round(cost, 6)
