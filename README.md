# Canin-Hunt

Search for **Royal Canin canned cat food** on sale at online pet stores. Each run is documented so you (or an agent) can compare runs and spot deals.

**Contributors:** [NeuroGamingLab](https://github.com/NeuroGamingLab) · [OpenClaw](https://github.com/OpenClaw) — see [CONTRIBUTORS.md](CONTRIBUTORS.md).

## GitHub Pages

The latest run from the **runs/** folder is published as a static site:

- **Live site:** [https://neurogaminglab.github.io/Canin-Hunt/](https://neurogaminglab.github.io/Canin-Hunt/)
- The page loads **data/findings.json** and shows the **latest run** (same data as the most recent file in **runs/**). Sorted by price, cheapest first.

**Enable Pages** (if not already): Repo **Settings → Pages → Source**: *Deploy from a branch* → Branch: **main** → Folder: **/docs** → Save.

**Keeping the site updated:** A GitHub Actions workflow runs the search every 6 hours and commits new runs to **data/** and **runs/**, so the Pages site reflects the latest results. You can also run it manually: **Actions → Update runs for GitHub Pages → Run workflow**.

## Quick start

1. **Create and use the project virtual environment** (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **View the webpage**  
   Open `index.html` in a browser. It uses embedded data if `data/findings.json` isn’t available (e.g. when opened as `file://`).  
   For the full experience (including the **Run another search** button), start the app server:
   ```bash
   python app.py
   ```
   Then open http://localhost:8001

3. **Run a search** (optional)  
   With the venv activated, add a new run from a live web search:
   ```bash
   python scripts/run_search.py --search
   ```
   Or add a run from an existing JSON file:
   ```bash
   python scripts/run_search.py --run-file runs/run_20250304_001.json
   ```

## Search engines

Search tries **multiple engines** in order until one returns results. Configure with `SEARCH_ENGINES` (comma-separated) and API keys where needed.

| Engine | Env vars | Notes |
|--------|----------|--------|
| **DuckDuckGo** | — | Default, no key; uses backend='auto' (Google/Bing fallbacks). |
| **Google** | `GOOGLE_API_KEY`, `GOOGLE_CX` | [Custom Search JSON API](https://developers.google.com/custom-search/v1/overview). |
| **Bing** | `BING_SUBSCRIPTION_KEY` | [Bing Web Search API](https://www.microsoft.com/en-us/bing/apis/bing-web-search-api) (Azure). |
| **Brave** | `BRAVE_API_KEY` | [Brave Search API](https://brave.com/search/api/). |
| **SerpAPI** | `SERPAPI_KEY`, optional `SERPAPI_ENGINE` (google, bing, yahoo) | Paid; [serpapi.com](https://serpapi.com/). |
| **Searx / SearxNG** | `SEARX_URL` | Self-host or public instance; e.g. `https://your-searx.instance/search`. |
| **Yahoo** | Uses SerpAPI (engine=yahoo) or Bing | No separate key; powered by Bing or SerpAPI. |

**Example:** use Google then Bing then DuckDuckGo:

```bash
export GOOGLE_API_KEY=your_key
export GOOGLE_CX=your_cx
export BING_SUBSCRIPTION_KEY=your_bing_key
export SEARCH_ENGINES=google,bing,duckduckgo
python scripts/run_search.py --search
```

Default order (if `SEARCH_ENGINES` is unset) is: duckduckgo, google, bing, brave, serpapi, searx, yahoo. Engines missing required keys are skipped.

## Automation ON — cron every 6 hours

Searches run **automatically every 6 hours** via cron. The **webpage always shows the latest run** (most recent search results).

- **In-app scheduler** (when running `python app.py`):
  ```bash
  ENABLE_AUTO_SEARCH=1 AUTO_SEARCH_INTERVAL_HOURS=6 python app.py
  ```
  Runs a search every 6 hours (configurable). Each run is appended to `data/findings.json` and saved under `runs/`.

- **Cron** (recommended — every 6 hours; use your real project path):
  ```bash
  crontab -e
  ```
  Add: `0 */6 * * * /path/to/Canin-Hunt/scripts/cron_search.sh`  
  Or: `0 */6 * * * cd /path/to/Canin-Hunt && .venv/bin/python scripts/run_search.py --search`  
  The **webpage shows the latest run** (most recent search results).

**Do you still need the button?** Yes, but it’s optional when automation is on. Use the button to run a search **now** without waiting for the next 6‑hour run.

## Layout

- **`instruction.txt`** — Objective and rules for the search and output.
- **`data/findings.json`** — All runs; each run has `run_id`, `run_date`, and `findings[]` (store, product, price, link).
- **`runs/`** — One JSON file per run (`run_YYYYMMDD_HHMM.json`) for comparison.
- **`scripts/run_search.py`** — Script to run a search or add a run from a file; appends to `data/findings.json` and writes `runs/<run_id>.json`.
- **`scripts/cron_search.sh`** — Cron-friendly wrapper; run from crontab for automation every 6 hours.
- **`scripts/ml_utils.py`** — ML features: effective price from promos, deal score, anomaly detection, buy-now insight, product matching (see **ML features** below).
- **`scripts/search_engines.py`** — Multi-engine search: DuckDuckGo, Google, Bing, Brave, SerpAPI, Searx, Yahoo (see **Search engines** below).
- **`docs/index.html`** — GitHub Pages site; shows latest run with ML badges and insights.

## ML features (enhancement/ml branch)

When adding or enriching runs, each finding can get:

1. **Deal score** (0–1) — Compares price to history; higher = better deal. Shown as “Good deal” when ≥ 0.6.
2. **Effective price** — Parses “Buy 3 Get 1 FREE”, “35% off”, etc. into a comparable price for fair ranking.
4. **Price anomaly** — Flags suspiciously low or high vs history (“Verify price”).
5. **Buy now vs wait** — “Below average - good time to buy” / “Above average - consider waiting” from historical average.
6. **Product matching** — `canonical_product` id so the same product across stores can be compared.

**Backfill existing runs:** `python scripts/run_search.py --enrich-ml` (writes ML fields into `data/findings.json` and syncs `docs/data/`).

## Webpage

The page shows the **latest run** only. Each finding is a card with:

- **Store** — Retailer name  
- **Product** — Royal Canin canned product  
- **Price** — Sale or discount description  
- **Link** — URL to the product or deal  

Theme: dark background, Space Grotesk + JetBrains Mono, blue accent, card layout.

## Why "Search returned no results"?

The search uses the `duckduckgo-search` library with **backend='auto'** so it can use several providers (DuckDuckGo, Google, Bing, etc.). You can still see no results when:

- **DuckDuckGo is rate-limited** — very common; the library tries other backends automatically.
- **All backends fail** — e.g. network issues, blocking, or temporary outages.

**What to do:** Wait a minute and click **Run another search** again, or run `python scripts/run_search.py --search` from the terminal. Existing runs in `data/findings.json` are unchanged.
