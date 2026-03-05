#!/usr/bin/env python3
"""
Multi-engine search for Canin-Hunt. Tries engines in order until one returns results.
Supported: DuckDuckGo, Google, Bing, Brave, SerpAPI, Searx/SearxNG, Yahoo (via Bing/Searx).

Set env vars for API keys; engines without keys are skipped (except DuckDuckGo and optional Searx URL).
"""
import os
import re
from typing import Any, List, Optional

# Default query used by run_search
DEFAULT_QUERY = "Royal Canin canned cat food on sale"


def _norm(r: dict) -> dict:
    """Normalize to {title, href, body}."""
    return {
        "title": (r.get("title") or r.get("name") or "").strip(),
        "href": (r.get("href") or r.get("url") or r.get("link") or "").strip(),
        "body": (r.get("body") or r.get("snippet") or r.get("content") or r.get("description") or "").strip(),
    }


def search_duckduckgo(query: str, max_results: int = 10) -> List[dict]:
    """DuckDuckGo (no key). Uses backend='auto' to try Google/Bing fallbacks."""
    try:
        from ddgs import DDGS
        raw = DDGS().text(query, max_results=max_results, backend="auto")
    except ImportError:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                raw = ddgs.text(query, max_results=max_results, backend="auto")
        except ImportError:
            return []
    try:
        results = raw if isinstance(raw, list) else list(raw)
        return [_norm(r) for r in results if r.get("href") or r.get("title")]
    except Exception:
        return []


def search_google(query: str, max_results: int = 10) -> List[dict]:
    """Google Custom Search JSON API. Needs GOOGLE_API_KEY and GOOGLE_CX."""
    key = os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CX")
    if not key or not cx:
        return []
    try:
        import urllib.request
        import urllib.parse
        url = "https://www.googleapis.com/customsearch/v1?key=%s&cx=%s&q=%s&num=%s" % (
            urllib.parse.quote(key), urllib.parse.quote(cx),
            urllib.parse.quote(query), min(max_results, 10))
        req = urllib.request.Request(url, headers={"User-Agent": "Canin-Hunt/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            import json as _json
            data = _json.loads(resp.read().decode())
        items = data.get("items") or []
        return [_norm({"title": i.get("title"), "href": i.get("link"), "body": i.get("snippet")}) for i in items]
    except Exception:
        return []


def search_bing(query: str, max_results: int = 10) -> List[dict]:
    """Bing Web Search API (Azure). Needs BING_SUBSCRIPTION_KEY."""
    key = os.environ.get("BING_SUBSCRIPTION_KEY")
    if not key:
        return []
    try:
        import urllib.request
        import urllib.parse
        url = "https://api.bing.microsoft.com/v7.0/search?q=%s&count=%s" % (
            urllib.parse.quote(query), min(max_results, 50))
        req = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": key, "User-Agent": "Canin-Hunt/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            import json as _json
            data = _json.loads(resp.read().decode())
        items = (data.get("webPages") or {}).get("value") or []
        return [_norm({"title": i.get("name"), "href": i.get("url"), "body": i.get("snippet")}) for i in items]
    except Exception:
        return []


def search_brave(query: str, max_results: int = 10) -> List[dict]:
    """Brave Search API. Needs BRAVE_API_KEY."""
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        return []
    try:
        import urllib.request
        import urllib.parse
        url = "https://api.search.brave.com/res/v1/web/search?q=%s&count=%s" % (
            urllib.parse.quote(query), min(max_results, 20))
        req = urllib.request.Request(url, headers={"X-Subscription-Token": key, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            import json as _json
            data = _json.loads(resp.read().decode())
        results = data.get("web", {}).get("results") or []
        return [_norm({"title": r.get("title"), "href": r.get("url"), "body": r.get("description")}) for r in results]
    except Exception:
        return []


def search_serpapi(query: str, max_results: int = 10) -> List[dict]:
    """SerpAPI (paid). Supports Google, Bing, etc. Needs SERPAPI_KEY. Optional SERPAPI_ENGINE (google, bing, yahoo)."""
    key = os.environ.get("SERPAPI_KEY")
    if not key:
        return []
    engine = os.environ.get("SERPAPI_ENGINE", "google")
    try:
        import urllib.request
        import urllib.parse
        url = "https://serpapi.com/search?engine=%s&q=%s&num=%s&api_key=%s" % (
            urllib.parse.quote(engine), urllib.parse.quote(query), min(max_results, 100), urllib.parse.quote(key))
        req = urllib.request.Request(url, headers={"User-Agent": "Canin-Hunt/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            import json as _json
            data = _json.loads(resp.read().decode())
        # SerpAPI organic results
        results = data.get("organic_results") or []
        return [_norm({"title": r.get("title"), "href": r.get("link"), "body": r.get("snippet")}) for r in results]
    except Exception:
        return []


def search_searx(query: str, max_results: int = 10) -> List[dict]:
    """Searx / SearxNG (self-host or public instance). Set SEARX_URL (e.g. https://search.bus-hit.me)."""
    base = (os.environ.get("SEARX_URL") or "").rstrip("/")
    if not base:
        return []
    try:
        import urllib.request
        import urllib.parse
        url = "%s/search?q=%s&format=json&categories=general" % (base, urllib.parse.quote(query))
        req = urllib.request.Request(url, headers={"User-Agent": "Canin-Hunt/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            import json as _json
            data = _json.loads(resp.read().decode())
        results = data.get("results") or []
        out = []
        for r in results[:max_results]:
            out.append(_norm({"title": r.get("title"), "href": r.get("url"), "body": r.get("content")}))
        return out
    except Exception:
        return []


def search_yahoo(query: str, max_results: int = 10) -> List[dict]:
    """Yahoo: use SerpAPI with engine=yahoo, or Bing (Yahoo is powered by Bing)."""
    if os.environ.get("SERPAPI_KEY"):
        key_orig = os.environ.get("SERPAPI_ENGINE")
        os.environ["SERPAPI_ENGINE"] = "yahoo"
        try:
            return search_serpapi(query, max_results)
        finally:
            if key_orig is not None:
                os.environ["SERPAPI_ENGINE"] = key_orig
            else:
                os.environ.pop("SERPAPI_ENGINE", None)
    return search_bing(query, max_results)


# Registry: name -> function
ENGINES = {
    "duckduckgo": search_duckduckgo,
    "google": search_google,
    "bing": search_bing,
    "brave": search_brave,
    "serpapi": search_serpapi,
    "searx": search_searx,
    "yahoo": search_yahoo,
}


def search(
    query: str = DEFAULT_QUERY,
    max_results: int = 10,
    engine_order: Optional[List[str]] = None,
) -> List[dict]:
    """
    Run search across one or more engines. Tries each engine in order until one returns results.
    engine_order: list of names (e.g. ["google", "bing", "duckduckgo"]). Default from env SEARCH_ENGINES or all.
    """
    if engine_order is None:
        order_str = os.environ.get("SEARCH_ENGINES", "").strip().lower()
        engine_order = [x.strip() for x in order_str.split(",") if x.strip()] if order_str else list(ENGINES.keys())
    for name in engine_order:
        fn = ENGINES.get(name)
        if not fn:
            continue
        try:
            results = fn(query, max_results=max_results)
            if results:
                return results
        except Exception:
            continue
    return []


def available_engines() -> List[str]:
    """Return list of engine names that have required config (or need no config)."""
    out = []
    if True:
        out.append("duckduckgo")  # no key
    if os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CX"):
        out.append("google")
    if os.environ.get("BING_SUBSCRIPTION_KEY"):
        out.append("bing")
    if os.environ.get("BRAVE_API_KEY"):
        out.append("brave")
    if os.environ.get("SERPAPI_KEY"):
        out.append("serpapi")
    if os.environ.get("SEARX_URL"):
        out.append("searx")
    if os.environ.get("BING_SUBSCRIPTION_KEY") or os.environ.get("SERPAPI_KEY"):
        out.append("yahoo")
    return out
