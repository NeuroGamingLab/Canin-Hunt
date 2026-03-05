#!/usr/bin/env python3
"""
Run search for Royal Canin canned cat food on sale.
Documents each finding per run so runs can be compared.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
DATA_FILE = PROJECT_ROOT / "data" / "findings.json"
RUNS_DIR = PROJECT_ROOT / "runs"


def load_findings():
    if not DATA_FILE.exists():
        return {"runs": []}
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_findings(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def run_id_for_now():
    return datetime.now().strftime("run_%Y%m%d_%H%M")


def parse_price_numeric(text: str):
    """Extract first dollar amount from text (e.g. $52.56, $20, ($10 back), Save $5) for comparison. Returns float or None."""
    if not text:
        return None
    import re
    # Match $XX.XX or $XX in any context (parentheses, "Save $X", "up to $20", etc.)
    m = re.search(r'\$[\d,]+(?:\.\d{1,2})?', text)
    if not m:
        return None
    s = m.group(0).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def ensure_price_numeric(finding: dict) -> dict:
    """Set price_numeric from price text if not already set."""
    if "price_numeric" in finding and finding["price_numeric"] is not None:
        return finding
    p = parse_price_numeric(finding.get("price") or "")
    finding["price_numeric"] = p
    return finding


def sort_findings_by_price(findings: list[dict]) -> list[dict]:
    """Sort by effective_price or price_numeric (cheapest first), then by deal_score (highest). Items without price last."""
    def key(f):
        p = f.get("effective_price") or f.get("price_numeric")
        score = f.get("deal_score")
        return (p is None, p if p is not None else 0, -(score if score is not None else 0))
    return sorted(findings, key=key)


def add_run(findings: list[dict]) -> str:
    """Add a new run with the given findings. Enriched with ML features, sorted by price (cheapest first). Returns run_id."""
    for f in findings:
        ensure_price_numeric(f)
    data = load_findings()
    try:
        from scripts.ml_utils import enrich_findings_with_ml
        enrich_findings_with_ml(findings, data["runs"])
    except Exception:
        pass  # ML optional
    findings = sort_findings_by_price(findings)
    run_id = run_id_for_now()
    run = {
        "run_id": run_id,
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "findings": findings,
    }
    data["runs"].append(run)
    save_findings(data)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / f"{run_id}.json"
    with open(run_path, "w", encoding="utf-8") as f:
        json.dump(run, f, indent=2)
    return run_id


def search_online():
    """Perform a live search using configured engines (DuckDuckGo, Google, Bing, Brave, SerpAPI, Searx, Yahoo).
    Tries each engine in SEARCH_ENGINES order until one returns results. See scripts/search_engines.py and README.
    """
    try:
        from scripts.search_engines import search
    except Exception:
        try:
            from search_engines import search
        except Exception:
            # Fallback to DDG only if search_engines not available
            raw = None
            try:
                from ddgs import DDGS
                raw = DDGS().text("Royal Canin canned cat food on sale", max_results=10, backend="auto")
            except ImportError:
                try:
                    from duckduckgo_search import DDGS
                    with DDGS() as ddgs:
                        raw = ddgs.text("Royal Canin canned cat food on sale", max_results=10, backend="auto")
                except ImportError:
                    print("Install search dependency: pip install ddgs  (or pip install duckduckgo-search)")
                    return []
            if raw is None:
                return []
            results = raw if isinstance(raw, list) else list(raw)
            findings = []
            for r in results:
                link = r.get("href", "")
                title = r.get("title", "")
                body = r.get("body", "")
                store = _infer_store(link)
                price_text = (body[:120] + "...") if body and len(body) > 120 else (body or "Check link")
                findings.append(_finding(store, title, price_text, link))
            return findings

    results = search("Royal Canin canned cat food on sale", max_results=10)
    findings = []
    for r in results:
        link = r.get("href", "")
        title = r.get("title", "")
        body = r.get("body", "")
        store = _infer_store(link)
        price_text = (body[:120] + "...") if body and len(body) > 120 else (body or "Check link")
        findings.append(_finding(store, title, price_text, link))
    return findings


def _infer_store(link: str) -> str:
    link_lower = (link or "").lower()
    if "amazon" in link_lower:
        return "Amazon"
    if "chewy" in link_lower:
        return "Chewy"
    if "petsmart" in link_lower:
        return "PetSmart"
    if "petco" in link_lower:
        return "Petco"
    if "royalcanin" in link_lower:
        return "Royal Canin"
    return "See link"


def _finding(store: str, title: str, price_text: str, link: str) -> dict:
    return {
        "store": store,
        "product": (title[:80] + "...") if len(title) > 80 else title,
        "price": price_text,
        "link": link,
        "price_numeric": parse_price_numeric(price_text) or parse_price_numeric(title),
    }


def run_search_api():
    """Run live search, add a new run, and return result for API. Returns dict with run_id, findings_count, error (if any)."""
    findings = search_online()
    if not findings:
        return {
            "ok": False,
            "error": "Search returned no results.",
            "hint": "DuckDuckGo is often rate-limited; the script uses backend='auto' to try other backends. Retry in a minute or run again.",
            "run_id": None,
            "findings_count": 0,
        }
    run_id = add_run(findings)
    return {"ok": True, "run_id": run_id, "findings_count": len(findings), "error": None}


def main():
    import argparse
    p = argparse.ArgumentParser(description="Search and document Royal Canin canned cat food sales.")
    p.add_argument("--run-file", type=Path, help="Path to a run JSON file to add (run_YYYYMMDD_HHMM.json).")
    p.add_argument("--search", action="store_true", help="Run live web search and add as new run.")
    p.add_argument("--enrich-ml", action="store_true", help="Add ML fields (deal_score, effective_price, etc.) to all existing runs and save.")
    args = p.parse_args()

    if args.enrich_ml:
        data = load_findings()
        try:
            from scripts.ml_utils import enrich_findings_with_ml
            for run in data.get("runs", []):
                for f in run.get("findings", []):
                    ensure_price_numeric(f)
                enrich_findings_with_ml(run["findings"], [r for r in data["runs"] if r != run])
            save_findings(data)
            print("Enriched all runs with ML fields. Syncing docs/data for GitHub Pages...")
            docs_data = PROJECT_ROOT / "docs" / "data" / "findings.json"
            if docs_data.parent.exists():
                import shutil
                shutil.copy(DATA_FILE, docs_data)
            print("Done.")
        except Exception as e:
            print("Enrich failed:", e)
        return

    if args.run_file:
        with open(args.run_file, encoding="utf-8") as f:
            run = json.load(f)
        findings = list(run.get("findings", []))
        for f in findings:
            ensure_price_numeric(f)
        run_id = add_run(findings)
        print(f"Added run from file: {run_id} ({len(findings)} findings)")
        return

    if args.search:
        print("Searching for Royal Canin canned cat food on sale...")
        findings = search_online()
        if not findings:
            print("No results. Install: pip install ddgs  (or pip install duckduckgo-search). DuckDuckGo is often rate-limited; retry in a minute.")
            return
        run_id = add_run(findings)
        print(f"Added run: {run_id} ({len(findings)} findings)")
        return

    # Default: add the seed run if not already present
    data = load_findings()
    if not data["runs"]:
        seed = [
            {"store": "Amazon", "product": "Royal Canin Canned Cat Food (various)", "price": "Up to 50% off with Subscribe & Save + coupon", "link": "https://www.amazon.com/s?k=Royal+Canin+canned+cat+food", "price_numeric": None},
            {"store": "Premier Pet Supply", "product": "Royal Canin Canned Cat Food", "price": "Buy 3 Get 1 FREE (March sale) — ~$39 for 4", "link": "https://premierpetsupply.com/brighton/deals/march-sale-royal-canin-canned-cat-food-buy-3-get-1-free/", "price_numeric": 39},
            {"store": "Pet Supermarket", "product": "Royal Canin Weight Care Thin Slices In Gravy", "price": "35% off first Autoship & Save (up to $20)", "link": "https://www.petsupermarket.com/cat/food-treats/wet-food/royal-canin-feline-care-nutrition-weight-care-thin-slices-in-gravy-canned-cat-food-3-oz/FCM02681.html", "price_numeric": 20},
            {"store": "Royal Canin (direct)", "product": "Indoor Adult Morsels in Gravy", "price": "15% off first auto-ship — case from $52.56", "link": "https://www.royalcanin.com/us/cats/products/retail-products/indoor-adult-morsels-in-gravy-1279", "price_numeric": 52.56},
            {"store": "Pet Ark", "product": "Royal Canin Adult Instinctive Thin Slices in Gravy, case of 24", "price": "See site for current price", "link": "https://petarkharlem.com/shop/royal-canin-feline-health-nutrition-adult-instinctive-thin-slices-in-gravy-canned-cat-food-3-oz-case-of-24/", "price_numeric": None},
        ]
        add_run(seed)
        print("Initialized with seed run.")
    else:
        print("Usage: --run-file <path> to add a run from JSON, or --search to run live search.")
        print("Data:", DATA_FILE)
        print("Runs:", RUNS_DIR)


if __name__ == "__main__":
    main()
