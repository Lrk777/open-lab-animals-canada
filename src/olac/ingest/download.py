"""Fetch every upstream file listed in config/sources.yaml and write a SHA-256 manifest."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import requests
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential

from olac.paths import CONFIG, RAW

USER_AGENT = "open-lab-animals-canada/0.1 (+https://github.com/; research data pipeline)"
MANIFEST = RAW / "manifest.json"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
def _get(url: str) -> bytes:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    return r.content


def _targets() -> list[tuple[str, str, Path]]:
    cfg = yaml.safe_load((CONFIG / "sources.yaml").read_text())
    out: list[tuple[str, str, Path]] = []
    ex = cfg["ccac_excel"]
    for year in ex["years"]:
        for n in (1, 2):
            out.append(
                (
                    "ccac_excel",
                    ex["url_template"].format(year=year, n=n),
                    RAW / ex["dest"].format(year=year, n=n),
                )
            )
    for key in ("ccac_pdf", "usda_aphis", "uk_home_office"):
        for year, url in cfg[key]["urls"].items():
            out.append((key, url, RAW / cfg[key]["dest"].format(year=year)))
    for name, url in cfg["ccac_pages"]["urls"].items():
        out.append(("ccac_pages", url, RAW / cfg["ccac_pages"]["dest"].format(name=name)))
    fund = cfg["funding"]
    for name, url in fund["urls"].items():
        out.append(("funding", url, RAW / fund["dest"].format(name=name)))
    for fy, url in _cihr_urls(fund["cihr_ckan_dataset"], fund["cihr_fiscal_years"]).items():
        out.append(("funding", url, RAW / fund["dest"].format(name=f"cihr_{fy}.xlsx")))
    return out


def _cihr_urls(dataset: str, years: list[str]) -> dict[str, str]:
    try:
        res = requests.get(
            "https://open.canada.ca/data/api/action/package_show", params={"id": dataset}, timeout=60
        ).json()["result"]["resources"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        print(f"[warn] CIHR resource list unavailable: {exc}")
        return {}
    urls = {}
    for r in res:
        for fy in years:
            if r["url"].endswith(f"irsc_{fy}.xlsx"):
                urls[fy] = r["url"]
    return urls


def run(force: bool = False) -> dict:
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    changed = []
    for source, url, dest in _targets():
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not force:
            content = dest.read_bytes()
        else:
            try:
                content = _get(url)
            except Exception as exc:  # noqa: BLE001
                print(f"[warn] {url}: {exc}")
                continue
            dest.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()
        key = str(dest.relative_to(RAW))
        previous = manifest.get(key, {})
        retrieved = previous.get("retrieved_utc")
        if previous.get("sha256") != sha:
            changed.append(key)
            retrieved = datetime.now(UTC).isoformat(timespec="seconds")
        manifest[key] = {
            "source": source,
            "url": url,
            "sha256": sha,
            "bytes": len(content),
            "retrieved_utc": retrieved,
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"{len(manifest)} files in manifest, {len(changed)} new or changed")
    return {"changed": changed}


if __name__ == "__main__":
    import sys

    run(force="--force" in sys.argv)
