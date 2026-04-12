"""CostTable — frozen per-model cost rates.

Token prices vary by model and change over time. A :class:`CostTable`
holds per-model USD rates per million tokens and exposes a single
``cost_for(turn)`` helper so the tracker can compute cost without
hard-coding any numbers.

The table supports a wildcard ``*`` entry so callers can set a default
without enumerating every model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from adk_fluent._usage._turn import TurnUsage

__all__ = ["CostTable", "ModelRate"]


@dataclass(frozen=True, slots=True)
class ModelRate:
    """USD rate per million tokens for one model.

    Attributes:
        input_per_million: USD per million input tokens.
        output_per_million: USD per million output tokens.
    """

    input_per_million: float = 0.0
    output_per_million: float = 0.0

    def cost_for(self, input_tokens: int, output_tokens: int) -> float:
        """Return the USD cost for the given token counts."""
        return (
            (input_tokens / 1_000_000) * self.input_per_million
            + (output_tokens / 1_000_000) * self.output_per_million
        )


@dataclass(frozen=True, slots=True)
class CostTable:
    """Frozen mapping of model name → :class:`ModelRate`.

    Attributes:
        rates: Mapping of model name to rate. The key ``"*"`` is used as
            the default when a model is not listed explicitly.
    """

    rates: Mapping[str, ModelRate] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Force an immutable view so the table is genuinely frozen.
        object.__setattr__(self, "rates", MappingProxyType(dict(self.rates)))

    @staticmethod
    def flat(input_per_million: float, output_per_million: float) -> CostTable:
        """Return a table with one wildcard rate.

        Convenience constructor for callers who only care about one
        model or want a uniform rate for everything.
        """
        return CostTable(
            rates={
                "*": ModelRate(
                    input_per_million=input_per_million,
                    output_per_million=output_per_million,
                )
            }
        )

    def rate_for(self, model: str) -> ModelRate:
        """Return the :class:`ModelRate` for ``model``.

        Falls back to the ``"*"`` wildcard entry, or a zero rate if
        neither exists.
        """
        if model in self.rates:
            return self.rates[model]
        if "*" in self.rates:
            return self.rates["*"]
        return ModelRate()

    def cost_for(self, turn: TurnUsage) -> float:
        """Return the USD cost of a :class:`TurnUsage` record."""
        return self.rate_for(turn.model).cost_for(
            turn.input_tokens, turn.output_tokens
        )

    def with_rate(
        self,
        model: str,
        *,
        input_per_million: float,
        output_per_million: float,
    ) -> CostTable:
        """Return a new table with an extra / overridden rate."""
        new_rates = dict(self.rates)
        new_rates[model] = ModelRate(
            input_per_million=input_per_million,
            output_per_million=output_per_million,
        )
        return CostTable(rates=new_rates)
