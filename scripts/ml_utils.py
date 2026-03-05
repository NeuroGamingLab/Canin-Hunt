#!/usr/bin/env python3
"""
ML-powered features for Canin-Hunt findings:
1. Deal scoring (good vs normal vs bad)
2. Effective price from promo text (Buy 3 Get 1 FREE, % off, etc.)
4. Price anomaly detection (suspiciously low/high)
5. Buy now vs wait (price vs historical average)
6. Product matching (canonical product id for same product across stores)
"""
import re
from datetime import datetime, timedelta
from typing import Any, List, Optional


def parse_effective_price(price_text: str, price_numeric: Optional[float] = None) -> Optional[float]:
    """
    Parse promo text into a comparable effective price (e.g. per unit or per deal).
    Handles: "Buy 3 Get 1 FREE", "35% off", "$20 off", explicit $ amounts.
    """
    if not price_text:
        return price_numeric
    text = price_text.lower().strip()
    # Explicit dollar amount (e.g. "~$39 for 4", "case from $52.56")
    dollar = re.search(r'\$[\d,]+(?:\.\d{1,2})?', text)
    base_price = float(dollar.group(0).replace("$", "").replace(",", "")) if dollar else price_numeric
    if base_price is None:
        return None

    # Buy N Get M FREE → effective discount
    buy_get = re.search(r'buy\s*(\d+)\s*get\s*(\d+)\s*free', text)
    if buy_get:
        n, m = int(buy_get.group(1)), int(buy_get.group(2))
        if n + m > 0:
            # You pay for n, get n+m units → effective price per unit = base_price * n / (n+m) for "for n" total
            # If "~$39 for 4" and "buy 3 get 1 free" → 4 units for $39, effective $39/4
            for_match = re.search(r'(?:for|@)\s*\$?[\d,]+(?:\.\d+)?\s*(?:for\s*)?(\d+)', text)
            units = int(for_match.group(1)) if for_match else (n + m)
            total_paid = base_price if re.search(r'\d+\s*for\s*\$', text) or ' for ' in text else base_price * n  # assume base is per n
            return round(total_paid / units, 2) if units else base_price

    # X% off
    pct = re.search(r'(\d+)\s*%\s*off', text)
    if pct and base_price:
        p = int(pct.group(1)) / 100.0
        return round(base_price * (1 - p), 2)

    return round(base_price, 2) if base_price else None


def canonical_product(product_name: str) -> str:
    """
    Normalize product name to a canonical id for matching same product across stores.
    """
    if not product_name:
        return ""
    s = product_name.lower().strip()
    s = re.sub(r"\s+", " ", s)
    # Remove common suffixes/variants for matching
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)  # trailing (various), (3-oz), etc.
    s = re.sub(r",\s*case of \d+", "", s)
    s = re.sub(r"\s*—?\s*\.\.\.$", "", s)
    # First 50 chars of normalized name as key (enough to group "Royal Canin Indoor Adult Morsels...")
    return s[:50].strip() if s else ""


def _historical_findings(runs: list[dict]) -> list[dict]:
    """Flatten runs into list of findings with run_date."""
    out = []
    for run in runs or []:
        run_date = run.get("run_date") or ""
        for f in run.get("findings") or []:
            out.append({**f, "run_date": run_date})
    return out


def _prices_for_product(historical: List[dict], canonical_id: str) -> List[float]:
    """Get all price_numeric and effective_price values for a product."""
    prices = []
    for h in historical:
        h_cid = h.get("canonical_product") or canonical_product(h.get("product") or "")
        if canonical_id and h_cid != canonical_id:
            continue
        p = h.get("effective_price") or h.get("price_numeric")
        if p is not None:
            prices.append(float(p))
    return prices


def compute_deal_score(finding: dict, historical: List[dict]) -> Optional[float]:
    """
    Score 0–1: 1 = best deal (lowest price vs history), 0 = worst.
    Uses effective_price or price_numeric; compares to historical for same product or global.
    """
    price = finding.get("effective_price") or finding.get("price_numeric")
    if price is None:
        return None
    price = float(price)
    cid = finding.get("canonical_product") or canonical_product(finding.get("product") or "")
    prices = _prices_for_product(historical, cid)
    if not prices:
        prices = [h.get("effective_price") or h.get("price_numeric") for h in historical if (h.get("effective_price") or h.get("price_numeric")) is not None]
    if not prices:
        return 0.5  # no history: neutral
    lo, hi = min(prices), max(prices)
    if hi <= lo:
        return 1.0 if price <= lo else 0.0
    # Lower price = higher score; linear in [0,1]
    return round(1.0 - (price - lo) / (hi - lo), 2)


def detect_price_anomaly(finding: dict, historical: List[dict]) -> Optional[str]:
    """
    Flag suspiciously low or high price vs history. Returns "low", "high", or None.
    Uses IQR: outlier if price < Q1 - 1.5*IQR or > Q3 + 1.5*IQR.
    """
    price = finding.get("effective_price") or finding.get("price_numeric")
    if price is None:
        return None
    price = float(price)
    cid = finding.get("canonical_product") or canonical_product(finding.get("product") or "")
    prices = _prices_for_product(historical, cid)
    if not prices:
        prices = [h.get("effective_price") or h.get("price_numeric") for h in historical if (h.get("effective_price") or h.get("price_numeric")) is not None]
    if len(prices) < 3:
        return None
    s = sorted(prices)
    n = len(s)
    q1 = s[n // 4]
    q3 = s[(3 * n) // 4]
    iqr = q3 - q1
    if iqr <= 0:
        return None
    if price < q1 - 1.5 * iqr:
        return "low"
    if price > q3 + 1.5 * iqr:
        return "high"
    return None


def price_insight(finding: dict, runs: List[dict]) -> Optional[str]:
    """
    "Buy now vs wait": compare current price to recent historical average.
    """
    price = finding.get("effective_price") or finding.get("price_numeric")
    if price is None:
        return None
    price = float(price)
    historical = _historical_findings(runs)
    cid = finding.get("canonical_product") or canonical_product(finding.get("product") or "")
    prices = _prices_for_product(historical, cid)
    if not prices:
        return None
    avg = sum(prices) / len(prices)
    if price < avg * 0.9:
        return "Below average - good time to buy"
    if price > avg * 1.1:
        return "Above average - consider waiting"
    return "Near average price"


def enrich_findings_with_ml(findings: List[dict], runs: List[dict]) -> None:
    """
    Mutate each finding in place: add effective_price, deal_score, price_anomaly, price_insight, canonical_product.
    """
    historical = _historical_findings(runs)
    for f in findings:
        # 2. Effective price from promo text
        pn = f.get("price_numeric")
        ep = parse_effective_price(f.get("price") or "", pn)
        if ep is not None:
            f["effective_price"] = ep
        # 6. Canonical product
        f["canonical_product"] = canonical_product(f.get("product") or "")
        # 1. Deal score
        f["deal_score"] = compute_deal_score(f, historical)
        # 4. Anomaly
        f["price_anomaly"] = detect_price_anomaly(f, historical)
        # 5. Buy now vs wait
        f["price_insight"] = price_insight(f, runs)
