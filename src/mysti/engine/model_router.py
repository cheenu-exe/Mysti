"""Model router: selects the best LLM model for a given task.

Phase E implements:
- Task-based model selection (speed vs quality)
- Model registry with capabilities and costs
- Fallback chains
- Cost tracking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a single model."""

    model_id: str
    name: str
    max_tokens: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    average_latency_ms: float = 500.0
    quality_score: float = 0.8  # 0-1, higher = better
    capabilities: list[str] = field(default_factory=lambda: ["general"])

    @property
    def supports_code(self) -> bool:
        return "code" in self.capabilities

    @property
    def supports_complex(self) -> bool:
        return "complex" in self.capabilities or "advanced" in self.capabilities


@dataclass
class ModelRouting:
    """Result of model selection."""

    model_id: str
    reason: str
    estimated_latency_ms: float
    estimated_cost: float
    quality_score: float


# Default model registry
DEFAULT_MODELS = [
    ModelConfig(
        model_id="gpt-4o-mini",
        name="GPT-4o Mini",
        max_tokens=4096,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
        average_latency_ms=300,
        quality_score=0.85,
        capabilities=["general", "fast"],
    ),
    ModelConfig(
        model_id="gpt-4o",
        name="GPT-4o",
        max_tokens=4096,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
        average_latency_ms=800,
        quality_score=0.95,
        capabilities=["general", "code", "complex", "advanced"],
    ),
    ModelConfig(
        model_id="claude-3-haiku",
        name="Claude 3 Haiku",
        max_tokens=4096,
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00125,
        average_latency_ms=250,
        quality_score=0.80,
        capabilities=["general", "fast"],
    ),
    ModelConfig(
        model_id="claude-3.5-sonnet",
        name="Claude 3.5 Sonnet",
        max_tokens=4096,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        average_latency_ms=600,
        quality_score=0.92,
        capabilities=["general", "code", "complex"],
    ),
]


class ModelRouter:
    """Selects the best model for a task based on classification.

    Considers:
    - Task complexity (simple → fast model, complex → quality model)
    - Task domain (code → code-capable model)
    - Cost efficiency
    - Latency requirements
    """

    def __init__(self, models: list[ModelConfig] | None = None) -> None:
        self.models = models or DEFAULT_MODELS
        self._cost_tracker: dict[str, float] = {}

    def get_model(self, model_id: str) -> ModelConfig | None:
        """Look up a model by ID."""
        for model in self.models:
            if model.model_id == model_id:
                return model
        return None

    def list_models(self) -> list[ModelConfig]:
        """Return all available models."""
        return list(self.models)

    def route(
        self,
        intent: str = "discussion",
        complexity: str = "medium",
        domain: str = "general",
    ) -> ModelRouting:
        """Select the best model for a task.

        Args:
            intent: Task intent (question, command, discussion, research).
            complexity: Task complexity (simple, medium, complex).
            domain: Task domain (general, code, research, memory).

        Returns:
            ModelRouting with selected model and reasoning.
        """
        # Score each model
        scored: list[tuple[ModelConfig, float, str]] = []

        for model in self.models:
            score = 0.0
            reasons = []

            # Quality baseline
            score += model.quality_score * 0.4

            # Complexity matching
            if complexity == "complex":
                if model.supports_complex:
                    score += 0.3
                    reasons.append("handles complex tasks")
                else:
                    score -= 0.1
            elif complexity == "simple":
                # Prefer fast models for simple tasks
                if "fast" in model.capabilities:
                    score += 0.2
                    reasons.append("fast for simple tasks")
                else:
                    score += 0.1

            # Domain matching
            if domain == "code":
                if model.supports_code:
                    score += 0.2
                    reasons.append("code-capable")
                else:
                    score -= 0.05

            # Cost efficiency (lower cost = higher score)
            total_cost = model.cost_per_1k_input + model.cost_per_1k_output
            if total_cost < 0.001:
                score += 0.1
                reasons.append("cost-efficient")
            elif total_cost > 0.01:
                score -= 0.05

            # Latency
            if model.average_latency_ms < 400:
                score += 0.05
                reasons.append("low latency")

            scored.append((model, score, ", ".join(reasons) if reasons else "balanced choice"))

        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            # Fallback to first model
            model = self.models[0] if self.models else ModelConfig(model_id="unknown", name="Unknown")
            return ModelRouting(
                model_id=model.model_id,
                reason="Fallback: no models available",
                estimated_latency_ms=model.average_latency_ms,
                estimated_cost=0.0,
                quality_score=model.quality_score,
            )

        best_model, best_score, reason = scored[0]

        # Estimate cost for a typical request (1k input, 500 output tokens)
        estimated_cost = (
            best_model.cost_per_1k_input * 1.0
            + best_model.cost_per_1k_output * 0.5
        )

        # Track cost
        self._cost_tracker[best_model.model_id] = (
            self._cost_tracker.get(best_model.model_id, 0.0) + estimated_cost
        )

        return ModelRouting(
            model_id=best_model.model_id,
            reason=reason or f"Best match for {complexity} {domain} {intent}",
            estimated_latency_ms=best_model.average_latency_ms,
            estimated_cost=round(estimated_cost, 6),
            quality_score=best_model.quality_score,
        )

    def get_cost_report(self) -> dict[str, float]:
        """Return accumulated cost per model."""
        return dict(self._cost_tracker)

    def reset_costs(self) -> None:
        """Reset cost tracking."""
        self._cost_tracker.clear()
