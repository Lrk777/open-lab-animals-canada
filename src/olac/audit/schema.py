"""Extraction schema: ARRIVE 2.0 Essential 10 items plus primate-welfare reporting items.

Every field is a `Finding`: whether the paper reports the item, the value if any, and a verbatim
evidence quote. A finding marked reported=True without a quote that appears in the source text
is downgraded by `verify_evidence`, which is the main guard against LLM hallucination.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field


class Finding(BaseModel):
    reported: bool = Field(description="True only if the methods text explicitly reports this item.")
    value: str | None = Field(default=None, description="Short normalised value, e.g. 'single', '2', 'yes'.")
    evidence: str | None = Field(default=None, description="Verbatim quote (<= 300 chars) from the text.")
    confidence: float | None = Field(default=None, ge=0, le=1)


FieldGroup = Literal["arrive_essential", "primate_welfare", "oversight"]

FIELDS: dict[str, dict] = {
    # ARRIVE 2.0 Essential 10 (items most relevant to methods sections)
    "sample_size": {
        "group": "arrive_essential",
        "arrive": "E2",
        "question": "Is the number of animals stated?",
        "value_hint": "integer number of animals",
    },
    "sample_size_justification": {
        "group": "arrive_essential",
        "arrive": "E2b",
        "question": "Is the choice of sample size justified (power analysis or rationale)?",
    },
    "inclusion_exclusion": {
        "group": "arrive_essential",
        "arrive": "E3",
        "question": "Are inclusion/exclusion criteria or excluded animals/data reported?",
    },
    "randomisation": {
        "group": "arrive_essential",
        "arrive": "E4",
        "question": "Is randomisation (of animals, trials, or conditions) described?",
    },
    "blinding": {
        "group": "arrive_essential",
        "arrive": "E5",
        "question": "Is blinding/masking of experimenters or analysts described?",
    },
    "statistical_methods": {
        "group": "arrive_essential",
        "arrive": "E7",
        "question": "Are statistical methods described?",
    },
    "animal_sex": {
        "group": "arrive_essential",
        "arrive": "E8",
        "question": "Is the sex of the animals reported?",
        "value_hint": "male / female / both",
    },
    "animal_age_or_weight": {
        "group": "arrive_essential",
        "arrive": "E8",
        "question": "Is age or weight of the animals reported?",
    },
    "animal_source": {
        "group": "arrive_essential",
        "arrive": "E8",
        "question": "Is the source/supplier/origin of the animals reported?",
    },
    # Primate welfare items (ARRIVE 2.0 Recommended Set: R15 housing and husbandry, R16 animal care and monitoring)
    "housing_type": {
        "group": "primate_welfare",
        "arrive": "R15",
        "question": "Is the social housing condition reported (single, pair, group)?",
        "value_hint": "single / pair / group / mixed",
    },
    "enrichment": {
        "group": "primate_welfare",
        "arrive": "R15",
        "question": "Is environmental enrichment described?",
    },
    "fluid_or_food_control": {
        "group": "primate_welfare",
        "arrive": "R15",
        "question": "Is the fluid/food regime stated (controlled/restricted, or ad libitum)?",
        "value_hint": "controlled / ad_libitum",
    },
    "fluid_control_detail": {
        "group": "primate_welfare",
        "arrive": "R15",
        "question": "If fluid/food is controlled, are amounts, minimums, or monitoring (weight, hydration) reported?",
    },
    "implant_described": {
        "group": "primate_welfare",
        "arrive": "E9",
        "question": "Are head posts, recording chambers, eye coils or other implants described?",
        "value_hint": "headpost / chamber / eye coil / array / other",
    },
    "surgery_count": {
        "group": "primate_welfare",
        "arrive": "E9",
        "question": "Is the number of surgeries per animal reported?",
    },
    "anaesthesia_analgesia": {
        "group": "primate_welfare",
        "arrive": "R16",
        "question": "Are anaesthesia and post-operative analgesia described?",
    },
    "welfare_monitoring_endpoints": {
        "group": "primate_welfare",
        "arrive": "R16",
        "question": "Are welfare monitoring, adverse events or humane endpoints described?",
    },
    "animal_reuse": {
        "group": "primate_welfare",
        "arrive": "R16",
        "question": "Is prior or subsequent use of the same animals in other studies reported?",
    },
    "animal_fate": {
        "group": "primate_welfare",
        "arrive": "R16",
        "question": "Is the fate of the animals at the end of the study reported (euthanised, retained)?",
    },
    # Oversight (ARRIVE 2.0 R14 ethical statement)
    "ethics_approval": {
        "group": "oversight",
        "arrive": "R14",
        "question": "Is approval by an animal care/ethics committee stated?",
    },
    "ccac_guidelines": {
        "group": "oversight",
        "arrive": "R14",
        "question": "Is compliance with CCAC guidelines (or equivalent national guidelines) stated?",
    },
}


class PaperAudit(BaseModel):
    pmcid: str
    backend: str
    findings: dict[str, Finding]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[‐-‒–—]", "-", s)).strip().lower()


def verify_evidence(audit: PaperAudit, source: str) -> PaperAudit:
    """Downgrade any reported finding whose quote cannot be found verbatim in the source."""
    src = _norm(source)
    for f in audit.findings.values():
        if f.reported:
            if not f.evidence or _norm(f.evidence)[:200] not in src:
                f.reported = False
                f.value = "unverified_quote"
                f.confidence = 0.0
    return audit
