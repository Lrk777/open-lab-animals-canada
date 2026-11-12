"""Deterministic regex baseline. Every extracted field carries the matched sentence as evidence."""

from __future__ import annotations

import re

from olac.audit.schema import FIELDS, Finding, PaperAudit

N = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d{1,3})"
NHP = r"(?:monkeys?|macaques?|animals|marmosets?)"

PATTERNS: dict[str, list[str]] = {
    "sample_size": [
        rf"\b{N}\s+(?:adult\s+|juvenile\s+|male\s+|female\s+|rhesus\s+|cynomolgus\s+|\(\w+\)\s+)*{NHP}\b",
        rf"\b{NHP}\s*\(n\s*=\s*\d+",
        r"\bn\s*=\s*\d+\s+(?:monkeys|macaques|animals)\b",
    ],
    "sample_size_justification": [r"power (analysis|calculation)", r"sample size (was|were) (chosen|determined|based)",
                                  r"(two|2)[- ]animal (standard|convention)", r"consistent with (the )?(standard|convention|previous)[^.]{0,60}(two|2|number of) (monkeys|animals)"],
    "inclusion_exclusion": [r"\bexclud(ed|ing|e)\b", r"inclusion criteri", r"\bwere (removed|discarded) from (the )?analys"],
    "randomisation": [r"\brandomi[sz]ed\b", r"\brandom(ly)? (order|interleaved|assigned|selected|sequence)", r"pseudo-?random"],
    "blinding": [r"\bblind(ed|ing)?\b(?! spot)", r"\bmasked to\b", r"unaware of (the )?(condition|group|treatment)"],
    "statistical_methods": [r"\b(t-?test|anova|wilcoxon|mann[- ]whitney|regression|mixed[- ]effects?|bootstrap|permutation test|chi-?square|kruskal)", r"statistical (analys|test|significance)"],
    "animal_sex": [r"\b(male|female)s?\b[^.]{0,40}\b(monkeys?|macaques?|rhesus|animals)\b", r"\b(monkeys?|macaques?|animals)\b[^.]{0,30}\b(male|female)s?\b", r"\b[MF]\s*,\s*\d+(\.\d+)?\s*kg"],
    "animal_age_or_weight": [r"\b\d+(\.\d+)?\s*(-|–|to)?\s*\d*(\.\d+)?\s*kg\b", r"\baged?\s+\d+", r"\b\d+\s*(years?|yrs?)\s*(old|of age)", r"\bage[d]?[: ]+\d"],
    "animal_source": [r"\b(purchased|obtained|acquired|supplied) from\b", r"\b(primate (research )?center|world wide primates|covance|charles river|labs of virginia|alpha genesis)", r"\bbred (in|at) (our|the)"],
    "housing_type": [r"\b(single|singly|individually|pair|socially|group)[- ]?(housed|housing)\b", r"\bhoused (singly|individually|in pairs|in groups|socially|alone)"],
    "enrichment": [r"\benrichment\b", r"\btoys?\b", r"\bforaging\b", r"\bpuzzle feeders?\b"],
    "fluid_or_food_control": [r"\b(fluid|water|food)[- ](intake )?(control|restrict|regulat|schedul|depriv)",
                              r"\b(controlled|restricted|regulated|limited) (daily )?(access to |intake of )?(fluid|water|food)",
                              r"\b(fluid|water|food|liquid) (intake|consumption|access) (was|were) (controlled|restricted|regulated|limited|monitored)",
                              r"\bon (a )?(fluid|water)[- ](control|restriction|regulation)",
                              r"\b(access to|intake of) (water|fluids?) (was|were) (controlled|restricted|regulated)",
                              r"\b(water|fluid) and food regulation",
                              r"\b(ad libitum|unlimited|free|constant|unrestricted) access to (food and )?(water|fluids?)",
                              r"\b(water|fluids?) (was|were) (provided|available) ad libitum",
                              r"\bnot on (water|fluid) (deprivation|restriction|control)"],
    "fluid_control_detail": [r"\b\d+\s*(ml|mL)/kg", r"\bminimum (daily )?(fluid|water)", r"\b(body )?weight(s)? (was|were) (monitored|recorded|checked)", r"\bhydration\b", r"\b\d+\s*(ml|mL)\b[^.]{0,40}(per day|daily|/day)"],
    "implant_described": [r"\bhead[- ]?(post|holder|restraint|cap|fixation|implant)", r"\brecording chambers?\b", r"\b(scleral )?search coils?\b|\beye coils?\b", r"\b(utah|microelectrode|floating) arrays?\b", r"\bcraniotomy\b"],
    "surgery_count": [rf"\b{N}\s+(separate\s+|aseptic\s+|sterile\s+)?surger(y|ies)", r"\b(first|second|third|subsequent|additional) surger(y|ies)", r"\bin a (single|separate) surgery\b"],
    "anaesthesia_analgesia": [r"\banaesthe|\banesthe", r"\banalges", r"\b(buprenorphine|meloxicam|ketamine|isoflurane|propofol)\b"],
    "welfare_monitoring_endpoints": [r"\bhumane end ?points?\b", r"\b(monitored|checked) daily\b", r"\bveterinar(y|ian)\b[^.]{0,80}\b(monitor|care|staff|supervision)", r"\badverse (events?|effects?)\b", r"\bwelfare\b"],
    "animal_reuse": [r"\b(same|these) (monkeys|animals|macaques)\b[^.]{0,60}\b(previous|prior|other|earlier) (stud|experiment|report|publication)", r"\b(were|was) (also )?used in (previous|prior|other|earlier) (stud|experiment)", r"\b(previously|also) (described|reported|used)\b[^.]{0,60}\b(monkey|animal|macaque)"],
    "animal_fate": [r"\b(euthani[sz]ed|sacrificed|perfused|killed)\b", r"\b(remain(s|ed)?|were returned to|retired to) (the colony|a sanctuary|active)"],
    "ethics_approval": [r"\banimal care (committee|and use)", r"\b(ACC|IACUC|AUP|AUC)\b", r"\bapproved by\b[^.]{0,100}\b(committee|board|council)", r"\bethic(s|al) (approval|committee|board)"],
    "ccac_guidelines": [r"canadian council on animal care", r"\bCCAC\b", r"\bguide for the care and use of laboratory animals\b", r"\bNIH guide\b", r"\bdirective 2010/63"],
}
_COMPILED = {k: [re.compile(p, re.I) for p in v] for k, v in PATTERNS.items()}
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def _sentence(text: str, start: int, end: int) -> str:
    a = text.rfind(". ", 0, start)
    b = text.find(". ", end)
    a = 0 if a < 0 else a + 2
    b = len(text) if b < 0 else b + 1
    return text[a:b][:300]


def _value(field: str, text: str, m: re.Match) -> str | None:
    s = m.group(0).lower()
    if field == "housing_type":
        if re.search(r"single|singly|individual|alone", s):
            return "single"
        if "pair" in s:
            return "pair"
        if re.search(r"group|social", s):
            return "group"
    if field == "fluid_or_food_control":
        return "ad_libitum" if re.search(r"ad libitum|unlimited|free access|constant|unrestricted|not on", s) else "controlled"
    if field == "animal_sex":
        return "male" if "female" not in s else ("female" if "male" not in s.replace("female", "") else "both")
    if field == "sample_size":
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                 "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
        tok = re.search(r"\d+|" + "|".join(words), s)
        if tok:
            return str(words.get(tok.group(0), tok.group(0)))
    if field == "implant_described":
        for k in ("head", "chamber", "coil", "array", "craniotomy"):
            if k in s:
                return {"head": "headpost", "coil": "eye coil"}.get(k, k)
    return None


def extract(pmcid: str, text: str) -> PaperAudit:
    findings = {}
    for field in FIELDS:
        hit = None
        for pat in _COMPILED[field]:
            m = pat.search(text)
            if m:
                hit = m
                break
        if hit:
            findings[field] = Finding(
                reported=True,
                value=_value(field, text, hit),
                evidence=_sentence(text, hit.start(), hit.end()),
                confidence=None,
            )
        else:
            findings[field] = Finding(reported=False)
    return PaperAudit(pmcid=pmcid, backend="rules", findings=findings)
