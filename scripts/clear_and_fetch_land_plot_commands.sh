#!/usr/bin/env bash
# Clear and fetch land/plot/developer data from 1acre-be.
# Run from project root: ./scripts/clear_and_fetch_land_plot_commands.sh
# Or run a section by uncommenting the block you need.

set -e
cd "$(dirname "$0")/.."

# --- Tokens (user = lands/plots, developer = developer-lands/developer-plots) ---
USER_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxODEwMDEyNjA4LCJpYXQiOjE3Nzg0NzY2MDgsImp0aSI6IjQ2MjEyZjViMDRmNzQ1OWQ5ZmM1NmU4ODg3MDYxNGMwIiwidXNlcl9pZCI6MjU1ODIsInRva2VuX3ZlcnNpb24iOjEsImRldmljZV90eXBlIjoiZGVza3RvcCIsInNlc3Npb25faWQiOiI5OTMzNGExMC1lNjUxLTQ2NzAtOWMzMS1jOTU3NzNmMWViZDIifQ.X4ujuqlt_Njz3Fk-QifBgcK7XJ5IuKIXLZU8nVfxRMY"
DEV_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxODEwMDE2NTUyLCJpYXQiOjE3Nzg0ODA1NTIsImp0aSI6IjVjZGMzZTFiM2VhNTRkYjFiYTY5MjlmNTc5YWY5YzE2IiwidXNlcl9pZCI6NDUsInRva2VuX3ZlcnNpb24iOjEsImRldmljZV90eXBlIjoiZGVza3RvcCIsInNlc3Npb25faWQiOiI2NDA3OGI0Ni1jNTc4LTRlODEtOTE3ZS01MmUyYzc5NjY2YjEifQ.I6oe5KJH-umSk2KUF3V7D1dbiQ6dfV_j-NRGUJsIaFA"

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
