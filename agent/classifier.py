"""Tag classifier via the OpenAI Decisions API (spec §5.1) and rule selection (§5.2).

The SDK installed here predates `client.decisions`, so the endpoint is called with the
client's generic `post`; the wire format is `{model, input, questions[]}` -> `{answers[]}`.
Code, not the model, decides which tags apply.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List

from common.config import Config
from common.llm import LLM
from common.prompts import load_prompt
from common.schemas import Rule

PROMPT = "agent/classify_tags"
REQUEST_TIMEOUT_S = 30


@dataclass
class ClassifierResult:
    status: str  # ok | fallback
    probabilities: Dict[str, float] = field(default_factory=dict)
    threshold: float = 0.0
    tags: List[str] = field(default_factory=list)
    fallback_all_rules: bool = False
    error: str = ""
    latency_ms: int = 0
    input_tokens: int = 0


def tag_vocabulary(rules: List[Rule]) -> Dict[str, List[str]]:
    """tag -> `applies_when` texts of the conditional rules that carry it (insertion-ordered, de-duplicated)."""
    vocab: Dict[str, List[str]] = {}
    for r in rules:
        if r.scope != "conditional":
            continue
        for tag in r.tags:
            texts = vocab.setdefault(tag, [])
            if r.applies_when not in texts:
                texts.append(r.applies_when)
    return vocab


def build_questions(vocab: Dict[str, List[str]]) -> List[dict]:
    template = load_prompt(PROMPT)
    return [
        {
            "type": "predicate",
            "name": tag,
            "instructions": template.replace("{tag}", tag).replace(
                "{applies_when}", " / or ".join(w.rstrip(".") for w in whens)
            ),
        }
        for tag, whens in vocab.items()
    ]


def _fallback(config: Config, error: str, latency_ms: int = 0) -> ClassifierResult:
    return ClassifierResult(
        status="fallback",
        threshold=config.classifier_threshold,
        fallback_all_rules=True,
        error=error,
        latency_ms=latency_ms,
    )


def interpret_answers(
    answers: object, vocab: Dict[str, List[str]], threshold: float
) -> ClassifierResult:
    """Pure function: Decisions `answers` -> selected tags, or a fallback on anything unexpected.

    Answers are matched by echoed name; names outside the vocabulary are ignored.
    A refusal, or any vocabulary tag without a numeric probability, triggers the fallback.
    """
    cfg_threshold = threshold
    if not isinstance(answers, list):
        return ClassifierResult(status="fallback", threshold=cfg_threshold, fallback_all_rules=True,
                                error="response has no `answers` list")
    probs: Dict[str, float] = {}
    for a in answers:
        if not isinstance(a, dict):
            continue
        if a.get("type") == "refusal":
            return ClassifierResult(status="fallback", threshold=cfg_threshold, fallback_all_rules=True,
                                    error=f"refusal on question {a.get('name')!r}")
        name = a.get("name")
        p = a.get("probability")
        if name in vocab and a.get("type") == "predicate" and isinstance(p, (int, float)) and not isinstance(p, bool):
            probs[name] = float(p)
    missing = [t for t in vocab if t not in probs]
    if missing:
        return ClassifierResult(status="fallback", probabilities=probs, threshold=cfg_threshold,
                                fallback_all_rules=True, error=f"missing answers for: {', '.join(missing)}")
    tags = [t for t in vocab if probs[t] >= threshold]
    return ClassifierResult(status="ok", probabilities=probs, threshold=cfg_threshold, tags=tags)


async def classify(llm: LLM, text: str, rules: List[Rule]) -> ClassifierResult:
    """Never raises. No conditional tags -> nothing to classify (status ok, no tags)."""
    cfg = llm.config
    vocab = tag_vocabulary(rules)
    if not vocab:
        return ClassifierResult(status="ok", threshold=cfg.classifier_threshold)
    t0 = time.perf_counter()
    try:
        body = {"model": cfg.classifier_model, "input": text, "questions": build_questions(vocab)}
        raw = await asyncio.wait_for(
            llm.client.post("/decisions", body=body, cast_to=object), REQUEST_TIMEOUT_S
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        answers = raw.get("answers") if isinstance(raw, dict) else None
        result = interpret_answers(answers, vocab, cfg.classifier_threshold)
        result.latency_ms = latency_ms
        usage = raw.get("usage") if isinstance(raw, dict) else None
        if isinstance(usage, dict):
            result.input_tokens = int(usage.get("input_tokens") or 0)
        return result
    except Exception as e:  # noqa: BLE001 - fail-safe: any failure runs all rules
        return _fallback(cfg, f"{type(e).__name__}: {e}", int((time.perf_counter() - t0) * 1000))


def select_rules(rules: List[Rule], tags: List[str], fallback_all_rules: bool) -> List[Rule]:
    """`always` ∪ `conditional` rules sharing a tag; on fallback, every rule."""
    if fallback_all_rules:
        return list(rules)
    chosen = set(tags)
    return [r for r in rules if r.scope == "always" or (r.scope == "conditional" and chosen & set(r.tags))]
