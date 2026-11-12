"""arrive-check: ARRIVE 2.0 + primate-welfare reporting checklist for a methods section.

Examples:
  arrive-check methods.txt
  arrive-check --pmcid PMC1234567
  cat methods.txt | arrive-check - --format json
  arrive-check methods.txt --backend llm --model gpt-4o-mini

Exit code is 0 when every Essential item is reported, 1 otherwise, so the tool can gate a
submission checklist in an editorial or animal-care-committee workflow.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from olac.audit import rules
from olac.audit.schema import FIELDS, PaperAudit

GROUP_TITLES = {
    "arrive_essential": "ARRIVE 2.0 Essential items",
    "primate_welfare": "Primate housing, husbandry and procedures",
    "oversight": "Ethical oversight",
}


def _load_text(args) -> tuple[str, str]:
    if args.pmcid:
        from olac.audit.corpus import fetch_fulltext

        doc = fetch_fulltext(args.pmcid)
        if not doc:
            raise SystemExit(f"Could not fetch open-access full text for {args.pmcid}")
        return args.pmcid, doc.get("methods") or doc.get("body", "")
    if args.path == "-":
        return "stdin", sys.stdin.read()
    p = Path(args.path)
    return p.stem, p.read_text(errors="ignore")


def audit_text(doc_id: str, text: str, backend: str = "rules", model: str | None = None) -> PaperAudit:
    if backend == "llm":
        from olac.audit import llm

        return llm.extract(doc_id, text, model=model)
    return rules.extract(doc_id, text)


def render_markdown(a: PaperAudit) -> str:
    out = [f"# Reporting checklist: {a.pmcid}", "", f"Backend: `{a.backend}`", ""]
    for group, title in GROUP_TITLES.items():
        items = [(k, f) for k, f in a.findings.items() if FIELDS[k]["group"] == group]
        done = sum(f.reported for _, f in items)
        out += [f"## {title} ({done}/{len(items)})", ""]
        for k, f in items:
            box = "[x]" if f.reported else "[ ]"
            val = f" - **{f.value}**" if f.value and f.reported else ""
            out.append(f"- {box} {FIELDS[k]['question']} (`{k}`, ARRIVE {FIELDS[k]['arrive']}){val}")
            if f.reported and f.evidence:
                out.append(f"  > {f.evidence.strip()}")
        out.append("")
    missing = [k for k, f in a.findings.items() if not f.reported]
    if missing:
        out += ["## Suggested additions", ""]
        out += [f"- {FIELDS[k]['question']}" for k in missing]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="arrive-check", description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", help="text file with the methods section, or - for stdin")
    ap.add_argument("--pmcid", help="fetch an open-access paper from Europe PMC instead")
    ap.add_argument("--backend", choices=["rules", "llm"], default="rules")
    ap.add_argument("--model", default=None)
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)
    if not args.path and not args.pmcid:
        ap.error("give a file path, '-', or --pmcid")

    doc_id, text = _load_text(args)
    a = audit_text(doc_id, text, args.backend, args.model)
    if args.format == "json":
        print(json.dumps(a.model_dump(), indent=2))
    else:
        print(render_markdown(a))
    essential_missing = [k for k, f in a.findings.items() if FIELDS[k]["group"] == "arrive_essential" and not f.reported]
    return 1 if essential_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
