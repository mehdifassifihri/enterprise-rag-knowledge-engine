#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Reads ignored .env via Settings; never enables shell tracing or prints keys.
.venv/bin/python scripts/demo_portfolio.py
.venv/bin/python scripts/demo_mcp.py
