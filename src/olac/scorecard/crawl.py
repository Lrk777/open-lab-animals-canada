"""Polite, bounded crawler that finds each university's public pages about animal research.

Discovery order: configured seeds, then sitemap URLs containing animal-related terms, then a
keyword-guided breadth-first crawl from the homepage. Respects robots.txt, waits between
requests, stays on the university's own domain, and stops at MAX_PAGES per institution.

Output: data/raw/scorecard/pages/<id>.jsonl  (url, title, text, fetched_utc)
"""

from __future__ import annotations

import gzip
import json
import re
import sys
import time
import urllib.robotparser
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup

from olac.paths import CONFIG, RAW

UA = "OpenLabAnimalsCanada-Scorecard/0.1 (academic transparency research; contact in repo README)"
OUT = RAW / "scorecard" / "pages"
MAX_PAGES = 40
MAX_FETCHES = 160
DELAY_S = 1.0
TIMEOUT = 20

KEYWORDS = re.compile(
    r"animal[-_ ]?(care|research|ethics|use|services|welfare|facilit)|research[-_ ]ethics|"
    r"\bacc\b|\bauacc\b|animaux|vivarium|veterinary[-_ ]services|comparative[-_ ]medicine",
    re.I,
)
NAV_HINTS = re.compile(r"research|ethic|integrity|compliance|recherche|about|services|vpr", re.I)
SKIP = re.compile(r"\.(pdf|jpe?g|png|gif|svg|zip|docx?|xlsx?|pptx?|mp4|mp3|ics)(\?|$)|/(login|cas|events?/\d)", re.I)


class Fetcher:
    def __init__(self, domain: str):
        self.domain = domain
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA
        self.robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self.last = 0.0
        self.count = 0

    def _allowed(self, url: str) -> bool:
        host = urlparse(url).netloc
        if host not in self.robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(f"https://{host}/robots.txt", timeout=TIMEOUT)
                rp.parse(r.text.splitlines() if r.ok else [])
            except requests.RequestException:
                rp.parse([])
            self.robots[host] = rp
        return self.robots[host].can_fetch(UA, url)

    def get(self, url: str) -> requests.Response | None:
        if self.count >= MAX_FETCHES or not self._allowed(url):
            return None
        wait = DELAY_S - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()
        self.count += 1
        try:
            r = self.session.get(url, timeout=TIMEOUT, allow_redirects=True)
        except requests.RequestException:
            return None
        if not r.ok or not on_domain(r.url, self.domain):
            return None
        return r


def on_domain(url: str, domain: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host == domain or host.endswith("." + domain)


def sitemap_urls(f: Fetcher, limit_maps: int = 12) -> list[str]:
    found: list[str] = []
    queue = deque()
    robots = f.get(f"https://www.{f.domain}/robots.txt") or f.get(f"https://{f.domain}/robots.txt")
    if robots is not None:
        queue.extend(re.findall(r"(?im)^sitemap:\s*(\S+)", robots.text))
    if not queue:
        queue.extend([f"https://www.{f.domain}/sitemap.xml", f"https://{f.domain}/sitemap.xml"])
    seen = 0
    while queue and seen < limit_maps:
        sm = queue.popleft()
        seen += 1
        r = f.get(sm)
        if r is None:
            continue
        body = r.content
        if sm.endswith(".gz"):
            try:
                body = gzip.decompress(body)
            except OSError:
                continue
        locs = re.findall(rb"<loc>\s*([^<]+?)\s*</loc>", body)
        for loc in (x.decode("utf-8", "ignore") for x in locs):
            if loc.endswith(".xml") or loc.endswith(".xml.gz"):
                if KEYWORDS.search(loc) or "page" in loc or "research" in loc:
                    queue.appendleft(loc)
                else:
                    queue.append(loc)
            elif KEYWORDS.search(loc):
                found.append(loc)
    return found


def extract(html: str) -> tuple[str, str, list[tuple[str, str]]]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title = (soup.title.string or "").strip() if soup.title else ""
    main = soup.find("main") or soup.find(id=re.compile("content|main", re.I)) or soup.body or soup
    text = re.sub(r"\s+", " ", main.get_text(" ", strip=True))
    links = [(a.get("href", ""), a.get_text(" ", strip=True)) for a in soup.find_all("a", href=True)]
    return title, text, links


def crawl(uni: dict) -> dict:
    domain = uni["domain"]
    f = Fetcher(domain)
    pages: list[dict] = []
    seen: set[str] = set()
    frontier: deque[tuple[str, int]] = deque((s, 0) for s in uni.get("seeds", []))
    home_status = None
    for home in (f"https://www.{domain}/", f"https://{domain}/"):
        try:
            home_status = f.session.get(home, timeout=TIMEOUT).status_code
        except requests.RequestException:
            continue
        if home_status < 400:
            break
    for u in sitemap_urls(f)[:30]:
        frontier.append((u, 0))
    for host in (f"www.{domain}", domain):
        frontier.extend([(f"https://{host}/", 0), (f"https://{host}/research/", 0)])

    while frontier and len(pages) < MAX_PAGES and f.count < MAX_FETCHES:
        url, depth = frontier.popleft()
        url = url.split("#")[0]
        if url in seen or SKIP.search(url) or not on_domain(url, domain):
            continue
        seen.add(url)
        r = f.get(url)
        if r is None or "html" not in r.headers.get("content-type", ""):
            continue
        title, text, links = extract(r.text)
        relevant = bool(KEYWORDS.search(url) or KEYWORDS.search(title) or re.search(r"animal", text[:4000], re.I))
        if relevant:
            pages.append(
                {
                    "url": r.url,
                    "title": title,
                    "text": text[:60000],
                    "fetched_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                }
            )
        if depth >= 3:
            continue
        for href, label in links:
            nxt = urljoin(r.url, href).split("#")[0]
            if nxt in seen or not on_domain(nxt, domain) or SKIP.search(nxt):
                continue
            if KEYWORDS.search(nxt) or KEYWORDS.search(label):
                frontier.appendleft((nxt, depth + 1))
            elif NAV_HINTS.search(nxt) and depth < 2:
                frontier.append((nxt, depth + 1))

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{uni['id']}.jsonl", "w") as fh:
        for p in pages:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    # Bot protection (HTTP 403 challenge pages) is respected, not bypassed: such institutions are
    # reported as "not assessed" and need manual review rather than being scored zero.
    status = "blocked" if home_status in (401, 403, 429) and not pages else "ok"
    meta = {"id": uni["id"], "pages": len(pages), "fetches": f.count, "home_status": home_status,
            "crawl_status": status, "crawled_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    (OUT / f"{uni['id']}.meta.json").write_text(json.dumps(meta))
    return meta


def run(only: list[str] | None = None, workers: int = 6) -> None:
    unis = yaml.safe_load((CONFIG / "universities.yaml").read_text())["universities"]
    if only:
        unis = [u for u in unis if u["id"] in only]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(crawl, unis):
            print(f"{res['id']:>10}: {res['pages']:>3} relevant pages ({res['fetches']} fetches, "
                  f"home HTTP {res['home_status']}, {res['crawl_status']})", flush=True)


if __name__ == "__main__":
    run(only=sys.argv[1:] or None)
