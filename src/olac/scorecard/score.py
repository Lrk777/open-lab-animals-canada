"""Score each university against config/scorecard_rubric.yaml.

Automated detection produces a *candidate* score with an evidence snippet and URL for every
indicator. A human reviewer confirms or overrides each cell in data/scorecard/review.csv;
the published scorecard uses reviewed values where they exist and marks the rest "unverified".

Outputs:
  data/processed/scorecard_evidence.csv  university x indicator with url, snippet, auto_hit
  data/processed/scorecard.csv           university totals, rank, verification coverage
  data/scorecard/review.csv              reviewer worksheet (created once, never overwritten)
"""

from __future__ import annotations

import json
import re

import pandas as pd
import yaml
from bs4 import BeautifulSoup

from olac.paths import CONFIG, DATA, PROCESSED, RAW

PAGES = RAW / "scorecard" / "pages"
REVIEW = DATA / "scorecard" / "review.csv"

# A page counts as "about animal research" only if it is titled/URL'd that way or mentions
# animals repeatedly; this filters out navigation menus that merely link to such pages.
ANIMAL_PAGE = re.compile(r"animal|animaux|vivarium|comparative medicine", re.I)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower().replace("é", "e").replace("’", "'"))


def ccac_lists() -> tuple[set[str], dict[str, str]]:
    part = (RAW / "scorecard" / "ccac_participating_institutions.html").read_text()
    soup = BeautifulSoup(part, "lxml")
    body = soup.get_text("\n")
    start = body.find("leading the way in institutional transparency")
    end = body.find("Not on the list?")
    participants = {_norm(x) for x in body[start:end].splitlines()[1:] if x.strip()}

    cert = BeautifulSoup((RAW / "scorecard" / "ccac_certified_institutions.html").read_text(), "lxml")
    status: dict[str, str] = {}
    root = cert.find(id="cert-inst")
    for p in root.find_all("p") if root else []:
        ul = p.find_next_sibling("ul")
        if ul is None:
            continue
        first = ul.find("li")
        txt = first.get_text(" ", strip=True) if first else ""
        cat = "probationary" if "Probationary" in txt else "preliminary" if "Preliminary" in txt else "regular"
        status[_norm(p.get_text(strip=True))] = cat
    return participants, status


def load_pages(uid: str) -> list[dict]:
    path = PAGES / f"{uid}.jsonl"
    if not path.exists():
        return []
    pages, seen = [], set()
    for p in map(json.loads, path.read_text().splitlines()):
        key = p["url"].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        mentions = len(ANIMAL_PAGE.findall(p["text"]))
        p["is_animal_page"] = bool(ANIMAL_PAGE.search(p["url"]) or ANIMAL_PAGE.search(p["title"]) or mentions >= 8)
        pages.append(p)
    return [p for p in pages if p["is_animal_page"]]


def _snippet(text: str, m: re.Match, width: int = 140) -> str:
    a, b = max(0, m.start() - width), min(len(text), m.end() + width)
    return ("..." if a else "") + text[a:b].strip() + ("..." if b < len(text) else "")


def crawl_status(uid: str) -> str:
    meta = PAGES / f"{uid}.meta.json"
    return json.loads(meta.read_text())["crawl_status"] if meta.exists() else "ok"


def score_university(uni: dict, rubric: dict, participants: set[str], cert: dict[str, str]) -> list[dict]:
    pages = load_pages(uni["id"])
    status = crawl_status(uni["id"])
    if status == "ok" and not pages:
        # The crawler not finding a page is not evidence that none exists.
        status = "no_pages_found"
    rows = []
    for ind_id, ind in rubric["indicators"].items():
        hit, url, snippet = False, None, None
        if ind.get("source") == "ccac_participating_institutions":
            hit = _norm(uni["ccac_name"]) in participants
            url = "https://ccac.ca/en/animals-used-in-science/transparency/participating-institutions.html"
            snippet = "Listed" if hit else "Not listed"
        elif ind.get("source") == "ccac_certified_institutions":
            cat = cert.get(_norm(uni["ccac_name"]))
            hit = cat == "regular"
            url = "https://ccac.ca/en/certification/certified-institutions.html"
            snippet = f"Certificate category: {cat or 'not found'}"
        else:
            pats = [re.compile(p, re.I) for p in ind["patterns"]]
            for p in pages:
                for pat in pats:
                    m = pat.search(p["text"])
                    if m:
                        hit, url, snippet = True, p["url"], _snippet(p["text"], m)
                        break
                if hit:
                    break
        rows.append(
            {
                "university_id": uni["id"],
                "university": uni["name"],
                "u15": uni.get("u15", False),
                "indicator": ind_id,
                "label": ind["label"],
                "points": ind["points"],
                "auto_hit": hit,
                "evidence_url": url,
                "evidence_snippet": snippet,
                "pages_examined": len(pages),
                "crawl_status": status,
            }
        )
    return rows


def run() -> pd.DataFrame:
    rubric = yaml.safe_load((CONFIG / "scorecard_rubric.yaml").read_text())
    unis = yaml.safe_load((CONFIG / "universities.yaml").read_text())["universities"]
    participants, cert = ccac_lists()
    ev = pd.DataFrame([r for u in unis for r in score_university(u, rubric, participants, cert)])

    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    if not REVIEW.exists():
        ev[["university_id", "indicator", "auto_hit", "evidence_url"]].assign(
            reviewed_hit="", reviewer="", reviewed_on="", note=""
        ).to_csv(REVIEW, index=False)
    review = pd.read_csv(REVIEW, dtype=str).fillna("")
    review = review[review.reviewed_hit.isin(["True", "False", "true", "false", "1", "0"])]
    review["reviewed_hit"] = review.reviewed_hit.str.lower().isin(["true", "1"])
    ev = ev.merge(review[["university_id", "indicator", "reviewed_hit", "reviewer"]],
                  on=["university_id", "indicator"], how="left")
    ev["verified"] = ev.reviewed_hit.notna()
    ev["final_hit"] = ev.reviewed_hit.where(ev.verified, ev.auto_hit).astype(bool)
    ev["earned"] = ev.points * ev.final_hit
    ev.to_csv(PROCESSED / "scorecard_evidence.csv", index=False)

    max_pts = sum(i["points"] for i in rubric["indicators"].values())
    sc = ev.groupby(["university_id", "university", "u15", "crawl_status"], as_index=False).agg(
        points=("earned", "sum"),
        pages_examined=("pages_examined", "first"),
        verified_share=("verified", "mean"),
        primate_disclosure=("final_hit", lambda s: bool(s[ev.loc[s.index, "indicator"] == "primate_disclosure"].any())),
    )
    sc["score_0_100"] = (sc.points / max_pts * 100).round(0)
    assessed = (sc.crawl_status == "ok") | (sc.verified_share == 1)
    sc.loc[~assessed, "score_0_100"] = float("nan")
    sc["grade"] = pd.cut(sc.score_0_100, [-1, 29, 49, 69, 84, 100], labels=["E", "D", "C", "B", "A"])
    sc["grade"] = sc.grade.cat.add_categories("not assessed").fillna("not assessed")
    sc = sc.sort_values(["score_0_100", "university"], ascending=[False, True], na_position="last")
    sc["rank"] = sc.score_0_100.rank(ascending=False, method="min").astype("Int64")
    sc.to_csv(PROCESSED / "scorecard.csv", index=False)
    print(sc[["rank", "university", "score_0_100", "grade", "pages_examined", "crawl_status"]].to_string(index=False))
    return sc


if __name__ == "__main__":
    run()
