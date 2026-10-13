"""OpenAI Responses API with Pydantic structured outputs.

One client per process, bounded concurrency, SDK-level retries with backoff,
and token-usage capture per call.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from common.config import CACHE_READ_FACTOR, CACHE_WRITE_FACTOR, PRICES, Config

T = TypeVar("T", bound=BaseModel)

SDK_MAX_RETRIES = 4


class LLMError(RuntimeError):
    """The model returned no parseable structured output (refusal, truncation)."""


@dataclass
class Usage:
    input: int = 0
    cached: int = 0
    cache_write: int = 0
    output: int = 0

    def __iadd__(self, other: "Usage") -> "Usage":
        self.input += other.input
        self.cached += other.cached
        self.cache_write += other.cache_write
        self.output += other.output
        return self


def cost_usd(model: str, usage: Usage) -> float:
    """Cost of `usage` at the dated price table; 0.0 for a model missing from the table.

    `input` is the total input token count, of which `cached` were read from and
    `cache_write` written to the cache.
    """
    if model not in PRICES:
        return 0.0
    p_in, p_out = PRICES[model]
    plain = max(usage.input - usage.cached - usage.cache_write, 0)
    per_million = (
        plain * p_in
        + usage.cached * p_in * CACHE_READ_FACTOR
        + usage.cache_write * p_in * CACHE_WRITE_FACTOR
        + usage.output * p_out
    )
    return per_million / 1_000_000


@dataclass
class LLMResult:
    parsed: BaseModel
    usage: Usage
    latency_ms: int
    model: str = ""


def usage_from_response(response) -> Usage:
    u = getattr(response, "usage", None)
    if u is None:
        return Usage()
    in_details = getattr(u, "input_tokens_details", None)
    return Usage(
        input=getattr(u, "input_tokens", 0) or 0,
        cached=getattr(in_details, "cached_tokens", 0) or 0,
        cache_write=getattr(in_details, "cache_write_tokens", 0) or 0,
        output=getattr(u, "output_tokens", 0) or 0,
    )


@dataclass
class LLM:
    config: Config
    client: Optional[AsyncOpenAI] = None
    total_usage: dict = field(default_factory=dict)  # model -> Usage
    _sem: Optional[asyncio.Semaphore] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = AsyncOpenAI(
                api_key=self.config.openai_api_key or None,
                max_retries=SDK_MAX_RETRIES,
            )

    def _semaphore(self) -> asyncio.Semaphore:
        # Created lazily so it binds to the running event loop.
        if self._sem is None:
            self._sem = asyncio.Semaphore(self.config.max_concurrency)
        return self._sem

    async def parse(
        self, *, model: str, system: str, user: str, schema: Type[T]
    ) -> LLMResult:
        """One structured-output call. Raises LLMError if nothing was parsed."""
        return await self.parse_input(
            model=model,
            input=[
                {"role": "developer", "content": system},
                {"role": "user", "content": user},
            ],
            schema=schema,
        )

    async def parse_input(
        self, *, model: str, input: list, schema: Type[T]
    ) -> LLMResult:
        """Like `parse`, with the caller building the message list (content parts, cache breakpoints)."""
        async with self._semaphore():
            t0 = time.perf_counter()
            response = await self.client.responses.parse(
                model=model, input=input, text_format=schema
            )
            latency_ms = int((time.perf_counter() - t0) * 1000)
        parsed = response.output_parsed
        if parsed is None:
            raise LLMError(
                f"{model} returned no parsed output (status={getattr(response, 'status', '?')})"
            )
        usage = usage_from_response(response)
        self.total_usage.setdefault(model, Usage())
        self.total_usage[model] += usage
        return LLMResult(parsed=parsed, usage=usage, latency_ms=latency_ms, model=model)

    async def prewarm(self, *, model: str, input: list) -> Usage:
        """Send a shared prefix once, with a minimal output, so later calls can read it from cache."""
        async with self._semaphore():
            response = await self.client.responses.create(
                model=model, input=input, max_output_tokens=16
            )
        usage = usage_from_response(response)
        self.total_usage.setdefault(model, Usage())
        self.total_usage[model] += usage
        return usage
