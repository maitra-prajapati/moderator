"""Optional, fail-closed, local Ollama tone suggestions. Not part of M4 rules."""

import json
import os

from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ToneProposal(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    start: int = Field(ge=0)
    end: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=250)
    replacement: str = Field(min_length=1, max_length=250)
    reason: str = Field(min_length=1, max_length=300)


class TonePayload(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    proposals: list[ToneProposal] = Field(max_length=3)


def suggest_tone(
    text: str,
    voice_traits: list[str],
    deterministic_findings: list,
    *,
    enabled: bool = False,
    timeout_seconds: float = 2.0,
) -> dict:
    """
    Return:
        {
            "status": "disabled" | "available" | "unavailable",
            "proposals": [...]
        }

    Only loopback HTTP is permitted.

    Invalid or unavailable model output cannot change
    deterministic findings.

    Suggestions never modify submitted text.
    """
    if not enabled:
        return {
            "status": "disabled",
            "proposals": [],
        }

    base = os.getenv(
        "MODERATOR_OLLAMA_URL",
        "http://127.0.0.1:11434",
    )

    parsed = urlsplit(base)

    if (
        parsed.scheme != "http"
        or parsed.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        return {
            "status": "unavailable",
            "proposals": [],
        }

    model = os.getenv(
        "MODERATOR_OLLAMA_MODEL",
        "llama3.2:3b",
    )

    if len(model) > 100 or not model.strip():
        return {
            "status": "unavailable",
            "proposals": [],
        }

    prompt = {
        "task": (
            "Propose up to 3 small style edits. "
            "Do not invent facts, citations, or policy."
        ),
        "voice_traits": voice_traits,
        "source_text_untrusted": text,
        "known_findings_read_only": [
            {
                "quote": f.span.quote,
                "category": f.category,
            }
            for f in deterministic_findings[:30]
        ],
        "output_schema": {
            "proposals": [
                {
                    "start": 0,
                    "end": 1,
                    "quote": "exact substring",
                    "replacement": "replacement text",
                    "reason": "style explanation",
                }
            ]
        },
    }

    payload = json.dumps(
        {
            "model": model,
            "stream": False,
            "format": "json",
            "prompt": json.dumps(
                prompt,
                ensure_ascii=False,
            ),
        }
    ).encode("utf-8")

    try:
        request = Request(
            base.rstrip("/") + "/api/generate",
            data=payload,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urlopen(
            request,
            timeout=min(
                5.0,
                max(0.1, timeout_seconds),
            ),
        ) as resp:
            raw = resp.read(65_537)

        if len(raw) > 65_536:
            raise ValueError("Oversized AI response")

        envelope = json.loads(raw)

        parsed_output = TonePayload.model_validate_json(
            envelope["response"]
        )

    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
    ):
        return {
            "status": "unavailable",
            "proposals": [],
        }

    proposals = []

    for p in parsed_output.proposals:
        if (
            p.end > len(text)
            or text[p.start:p.end] != p.quote
            or p.replacement == p.quote
        ):
            continue

        # Conservative safeguard against inventing numeric values.
        original_digits = {
            c
            for c in p.quote
            if c.isdigit()
        }

        new_digits = {
            c
            for c in p.replacement
            if c.isdigit()
        }

        if not new_digits.issubset(original_digits):
            continue

        proposals.append(p)

    return {
        "status": "available",
        "proposals": proposals,
    }