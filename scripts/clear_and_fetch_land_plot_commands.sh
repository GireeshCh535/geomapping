#!/usr/bin/env bash
# Clear and fetch land/plot/developer data from 1acre-be.
# Run from project root: ./scripts/clear_and_fetch_land_plot_commands.sh
# Or run a section by uncommenting the block you need.

set -e
cd "$(dirname "$0")/.."

# --- Tokens (user = lands/plots, developer = developer-lands/developer-plots) ---
USER_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxODAyOTYzMDIxLCJpYXQiOjE3NzE0MjcwMjEsImp0aSI6IjgzMGMzNzAwMWI2MzQ5ZmFiMmEwNzQ3NzE0ZTRhMTNhIiwidXNlcl9pZCI6Mjk1NTcsInRva2VuX3ZlcnNpb24iOjEsImRldmljZV90eXBlIjoiZGVza3RvcCIsInNlc3Npb25faWQiOiI1ZjFhODg4OC1hNzUwLTQzNzEtOTUwMS1hNWZmY2U0NWUwMmQifQ.2xD3024AK4gadAGEFiZOqdT_Q7Cm0TV97cRwLqkGG_A"
DEV_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxODAyOTY0MzE4LCJpYXQiOjE3NzE0MjgzMTgsImp0aSI6ImM1NTA2NTJiMzU5YzRlODdhZmNiYjRhNDI1NzdiZjkyIiwidXNlcl9pZCI6NDUsInRva2VuX3ZlcnNpb24iOjEsImRldmljZV90eXBlIjoiZGVza3RvcCIsInNlc3Npb25faWQiOiJhZDk4Njc2NS1iOTA3LTRjN2MtOGExNi1hNzk3YmVjNzZhMDQifQ.INrhSW5zk2PrNw5EXmSLQAlD-R9cyLklAnaQWcm7Emw"

# --- 1. Clear ALL tables and fetch everything (only if one token works for all 4 endpoints) ---
# python manage.py pull_land_plot_from_api --clear-first --token "$USER_TOKEN"

# --- 2. Clear and fetch per type ---
# python manage.py pull_land_plot_from_api --clear-before-fetch --lands-only --token "$USER_TOKEN"
# python manage.py pull_land_plot_from_api --clear-before-fetch --plots-only --token "$USER_TOKEN"
# python manage.py pull_land_plot_from_api --clear-before-fetch --developer-lands-only --token "$DEV_TOKEN"
# python manage.py pull_land_plot_from_api --clear-before-fetch --developer-plots-only --token "$DEV_TOKEN"

# --- 3. Full clear then fetch all (recommended: user token for lands/plots, dev token for developer) ---
echo "Step A: Clearing all synced tables and fetching lands + plots..."
python manage.py pull_land_plot_from_api --clear-first --lands-only --plots-only --token "$USER_TOKEN"
echo "Step B: Fetching developer lands + developer plots..."
python manage.py pull_land_plot_from_api --developer-lands-only --developer-plots-only --token "$DEV_TOKEN"
echo "Done."
