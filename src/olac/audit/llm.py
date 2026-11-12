"""LLM extraction with structured output and evidence verification.

Uses any OpenAI-compatible endpoint (OpenAI, Azure, local vLLM/Ollama with OPENAI_BASE_URL).
Set OPENAI_API_KEY and optionally OLAC_LLM_MODEL. Every reported finding must quote the text
verbatim; quotes that cannot be located are downgraded by `verify_evidence`.
"""

from __future__ import annotations

import json
import os

from olac.audit.schema import FIELDS, Finding, PaperAudit, verify_evidence

SYSTEM = (
    "You audit the methods sections of nonhuman-primate neuroscience papers against the ARRIVE 2.0 "
    "guidelines. For each item, decide whether the TEXT explicitly reports it. Be strict: absence of "
    "evidence means reported=false. When reported=true you MUST copy a verbatim quote (max 300 "
    "characters) from the TEXT as evidence, and give a short normalised value when a value hint is "
    "provided. Give a confidence between 0 and 1. Return JSON only."
)

MAX_CHARS = 60_000


def _schema() -> dict:
    item = {
        "type": "object",
        "properties": {
            "reported": {"type": "boolean"},
            "value": {"type": ["string", "null"]},
            "evidence": {"type": ["string", "null"]},
            "confidence": {"type": "number"},
        },
        "required": ["reported", "value", "evidence", "confidence"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {k: item for k in FIELDS},
        "required": list(FIELDS),
        "additionalProperties": False,
    }


def _items() -> str:
    lines = []
    for k, v in FIELDS.items():
        hint = f" Value: {v['value_hint']}." if v.get("value_hint") else ""
        lines.append(f"- {k}: {v['question']}{hint}")
    return "\n".join(lines)


def extract(pmcid: str, text: str, model: str | None = None, client=None) -> PaperAudit:
    if client is None:
        from openai import OpenAI

        client = OpenAI()
    model = model or os.environ.get("OLAC_LLM_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "arrive_audit", "schema": _schema(), "strict": True},
        },
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"ITEMS:\n{_items()}\n\nTEXT:\n{text[:MAX_CHARS]}"},
        ],
    )
    data = json.loads(resp.choices[0].message.content)
    audit = PaperAudit(
        pmcid=pmcid,
        backend=f"llm:{model}",
        findings={k: Finding(**data[k]) for k in FIELDS},
    )
    return verify_evidence(audit, text)
