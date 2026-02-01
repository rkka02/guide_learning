from __future__ import annotations

import json
import re
from typing import Any, Callable, Sequence

from llm.base import Message


Responder = Callable[[Sequence[Message], str], str]


def demo_responder(messages: Sequence[Message], model: str) -> str:
    """
    Deterministic responder for local demos (no network).

    It inspects the system prompt to guess which agent is calling.
    """
    system = (messages[0]["content"] if messages else "").lower()
    user = (messages[1]["content"] if len(messages) > 1 else "")

    if "learning planner" in system:
        return json.dumps(
            {
                "knowledge_points": [
                    {
                        "knowledge_title": "Transformer Overview & Building Blocks",
                        "knowledge_summary": (
                            "Transformer replaces recurrence with attention. The core block is: "
                            "LayerNorm → Self-Attention → residual, then LayerNorm → MLP → residual. "
                            "This enables parallel training and strong long-range dependency modeling."
                        ),
                        "user_difficulty": "Keeping track of the block order (LN/attention/MLP/residual) and why it works.",
                    },
                    {
                        "knowledge_title": "Self-Attention (Q, K, V)",
                        "knowledge_summary": (
                            "Scaled dot-product attention: softmax(QK^T / sqrt(d_k)) V. "
                            "Q queries choose what to read, K keys index content, V values carry content."
                        ),
                        "user_difficulty": "What Q/K/V represent and why scaling by sqrt(d_k) matters.",
                    },
                    {
                        "knowledge_title": "Multi-Head Attention",
                        "knowledge_summary": (
                            "Multiple attention heads run in parallel with different learned projections, "
                            "then concatenate and project. Heads can specialize in different relations "
                            "(local/global, syntax/semantics)."
                        ),
                        "user_difficulty": "Why multiple smaller heads can be better than one big head.",
                    },
                    {
                        "knowledge_title": "Positional Information (Sinusoidal, Learned, RoPE)",
                        "knowledge_summary": (
                            "Since attention is permutation-invariant, Transformers inject position via "
                            "positional encodings/embeddings (or relative methods like RoPE/ALiBi)."
                        ),
                        "user_difficulty": "How position is represented and how different schemes affect generalization.",
                    },
                    {
                        "knowledge_title": "Masking & Decoder-only vs Encoder-Decoder",
                        "knowledge_summary": (
                            "Decoder-only models use causal masking so each token attends only to past tokens. "
                            "Encoder-decoder adds cross-attention from decoder to encoder outputs for seq2seq tasks."
                        ),
                        "user_difficulty": "Where masks apply (self-attention vs cross-attention) and why.",
                    },
                ]
            }
        )

    if "interactive learning designer" in system:
        title = "Interactive Plan (Demo)"
        m = re.search(r"^\\s*Title:\\s*(.+)\\s*$", user, flags=re.MULTILINE)
        if not m:
            m = re.search(r"^\\s*-\\s*Title:\\s*(.+)\\s*$", user, flags=re.MULTILINE)
        if m:
            title = m.group(1).strip()

        return json.dumps(
            {
                "title": title,
                "concept": "Transformers replace recurrence with attention, enabling parallelism.",
                "key_points": [
                    "Self-attention lets each token attend to all others.",
                    "Blocks use attention + MLP with residual connections.",
                    "Positional encoding injects order information.",
                ],
                "example_problem": "Explain how self-attention differs from RNN recurrence.",
                "example_answer": "Self-attention computes token interactions in parallel; RNNs pass state sequentially.",
                "check_question": "In your own words, why does attention help with long-range dependencies?",
                "next_hint": "Move on when you can explain Q/K/V intuitively.",
            }
        )

    if "intelligent learning assistant" in system:
        return (
            "Transformers mainly learn relationships via **self-attention**.\n\n"
            "- If you're confused, try mapping the question to: **Q/K/V**, **masking**, or **positional info**.\n"
            "- What part feels unclear: the formula, the intuition, or where it is used in the block?"
        )

    if "learning summary expert" in system:
        return (
            "# Learning Summary (FakeLLM)\n\n"
            "- You completed a guided path on Transformer architecture.\n"
            "- Suggested next step: implement a tiny attention module and print attention weights for a toy sentence.\n"
        )

    return "Unknown call."


class FakeLLMClient:
    """LLMClient-compatible fake for tests/demos."""

    def __init__(self, responder: Responder = demo_responder):
        self._responder = responder

    async def complete(
        self,
        *,
        messages: Sequence[Message],
        model: str,
        temperature: float,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        return self._responder(messages, model)
