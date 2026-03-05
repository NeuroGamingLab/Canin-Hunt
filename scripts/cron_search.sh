#!/usr/bin/env bash
# Run Royal Canin sales search. Use from cron for automation every 6 hours.
# Crontab example: 0 */6 * * * /path/to/Canin-Hunt/scripts/cron_search.sh

set -e
cd "$(dirname "$0")/.."
.venv/bin/python scripts/run_search.py --search
