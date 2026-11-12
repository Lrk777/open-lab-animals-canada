"""Build the audit corpus from Europe PMC.

Inclusion: open-access, non-review articles 2010-present with a Canadian affiliation whose
METHODS section mentions macaques/monkeys and neural/brain/visual work. Full-text JATS XML is
fetched for each paper and reduced to its methods text.

Outputs:
  data/processed/corpus.csv              pmcid, pmid, doi, year, journal, title, n_methods_chars, uses_nhp
  data/raw/corpus/fulltext/<pmcid>.json  {"methods": str, "body": str}   (gitignored)

Author names are deliberately not stored: the audit evaluates papers, not people.
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
from lxml import etree
from tenacity import retry, stop_after_attempt, wait_exponential

from olac.paths import PROCESSED, RAW

API = "https://www.ebi.ac.uk/europepmc/webservices/rest"
FULLTEXT = RAW / "corpus" / "fulltext"
QUERY = (
    'AFF:"Canada" AND METHODS:("Macaca mulatta" OR "Macaca fascicularis" OR "Macaca nemestrina" '
    "OR rhesus OR macaque OR macaques OR monkeys) AND METHODS:(neuron OR neurons OR cortex OR "
    "cortical OR brain OR saccade OR saccades OR visual OR neural OR recording OR recordings) "
    'AND PUB_YEAR:[2010 TO 2026] AND OPEN_ACCESS:y AND NOT PUB_TYPE:"review"'
)
UA = {"User-Agent": "open-lab-animals-canada/0.1 (reporting-quality research)"}

METHODS_TITLE = re.compile(
    r"method|materials|experimental procedures|animals|subjects|procedure|surgical|surgery", re.I
)
_NUM = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d{1,3})"
_ADJ = r"(?:adult|juvenile|young|aged|male|female|rhesus|cynomolgus|vervet|marmoset|squirrel|japanese|pig-tailed|\(\w+\)|,|and|\s)*"
# Positive evidence that the paper's own experiments used primates.
NHP_SUBJECTS = re.compile(
    rf"\b{_NUM}\s+{_ADJ}(?:monkeys|macaques|marmosets|vervets|nonhuman primates|non-human primates)\b"
    r"|\b(?:monkeys?|macaques?|animals)\b[^.]{0,60}\b(?:were|was)\b[^.]{0,30}\b(?:used|trained|implanted|housed|"
    r"tested|recorded|obtained|purchased|anesthetized|anaesthetized|euthanized|challenged|inoculated|dosed)\b"
    r"|\b(?:collected|recorded|obtained) from\s+(?:\w+\s+){0,4}(?:monkeys|macaques)\b",
    re.I,
)
LAB_CONTEXT = re.compile(
    r"primate chair|head ?(post|holder)|implant|surgery|surgical|anesthe|anaesthe|recording chamber|"
    r"animal care committee|IACUC|housed|fluid|juice|reward|electrode|craniotomy|euthan|perfus",
    re.I,
)
# Mentions that are not the paper's own primate experiments.
NOT_SUBJECTS = re.compile(
    r"free-ranging|wild (population|group)|field site|Mmul_\d|genome assembly|Vero cells|"
    r"monkey kidney|COS-7",
    re.I,
)
NEURO = re.compile(
    r"neuron|cortex|cortical|saccad|electrode|fixation|visual stimul|fMRI|brain|spike|LFP|"
    r"electrophysiolog|microstimulation|optogenet",
    re.I,
)


def uses_nhp(methods: str) -> bool:
    subjects = len(NHP_SUBJECTS.findall(methods))
    lab = bool(LAB_CONTEXT.search(methods))
    negatives = len(NOT_SUBJECTS.findall(methods))
    return subjects >= 1 and lab and negatives <= subjects // 2


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30))
def _get(url: str, **params) -> requests.Response:
    r = requests.get(url, params=params, headers=UA, timeout=60)
    if r.status_code == 404:
        return r
    r.raise_for_status()
    return r


def search(query: str = QUERY) -> pd.DataFrame:
    rows, cursor = [], "*"
    while True:
        d = _get(
            f"{API}/search", query=query, format="json", resultType="core", pageSize=1000, cursorMark=cursor
        ).json()
        for r in d["resultList"]["result"]:
            journal = (r.get("journalInfo") or {}).get("journal", {}).get("title")
            rows.append(
                {
                    "pmcid": r.get("pmcid"),
                    "pmid": r.get("pmid"),
                    "doi": r.get("doi"),
                    "year": int(r.get("pubYear")) if r.get("pubYear") else None,
                    "journal": journal,
                    "title": r.get("title"),
                    "pub_types": "; ".join((r.get("pubTypeList") or {}).get("pubType", [])),
                }
            )
        nxt = d.get("nextCursorMark")
        if not nxt or nxt == cursor or not d["resultList"]["result"]:
            break
        cursor = nxt
    df = pd.DataFrame(rows).dropna(subset=["pmcid"]).drop_duplicates("pmcid")
    return df


def _text(el) -> str:
    return re.sub(r"\s+", " ", " ".join(el.itertext())).strip()


def methods_from_jats(xml: bytes) -> tuple[str, str]:
    root = etree.fromstring(xml)
    body = root.find(".//body")
    if body is None:
        return "", ""
    secs = body.findall("./sec")
    methods = []
    for s in secs:
        title = s.findtext("title") or ""
        stype = s.get("sec-type", "")
        if METHODS_TITLE.search(title) or "method" in stype:
            methods.append(_text(s))
    full = _text(body)
    return " ".join(methods), full


def fetch_fulltext(pmcid: str) -> dict | None:
    path = FULLTEXT / f"{pmcid}.json"
    if path.exists():
        return json.loads(path.read_text())
    r = _get(f"{API}/{pmcid}/fullTextXML")
    if r.status_code != 200 or not r.content.strip().startswith(b"<"):
        return None
    try:
        methods, body = methods_from_jats(r.content)
    except etree.XMLSyntaxError:
        return None
    doc = {"methods": methods, "body": body}
    path.write_text(json.dumps(doc))
    time.sleep(0.3)
    return doc


def run(limit: int | None = None) -> pd.DataFrame:
    FULLTEXT.mkdir(parents=True, exist_ok=True)
    cache = RAW / "corpus" / "search_results.csv"
    if cache.exists() and "--refresh" not in sys.argv:
        meta = pd.read_csv(cache)
    else:
        meta = search()
        meta.to_csv(cache, index=False)
    print(f"{len(meta)} search hits")
    if limit:
        meta = meta.head(limit)
    def _safe(pmcid):
        try:
            return fetch_fulltext(pmcid)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] {pmcid}: {exc}", flush=True)
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        docs = list(pool.map(_safe, meta.pmcid))
    n_chars, uses, neuro = [], [], []
    for doc in docs:
        m = (doc or {}).get("methods") or (doc or {}).get("body", "")
        n_chars.append(len(m))
        uses.append(uses_nhp(m))
        neuro.append(len(NEURO.findall(m)) >= 3)
    meta["n_methods_chars"] = n_chars
    meta["uses_nhp"] = uses
    meta["is_neuro"] = neuro
    meta["has_methods"] = meta.n_methods_chars > 500
    meta.to_csv(PROCESSED / "corpus.csv", index=False)
    inc = meta[meta.uses_nhp & meta.has_methods]
    print(f"{len(inc)} papers with NHP subjects and a methods section ({int(inc.is_neuro.sum())} neuroscience); by year:")
    print(inc.groupby("year").size().to_string())
    return meta


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run(limit=int(args[0]) if args else None)
