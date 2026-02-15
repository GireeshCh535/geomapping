#!/usr/bin/env bash
# Merge main into master but keep production's deploy.yml, run_play.sh, nginx/conf.d/default.conf.
# Usage: run from repo root: ./scripts/merge-main-to-master.sh

set -e
if [[ $(git branch --show-current) != master ]]; then
  echo "Switch to master first: git checkout master"
  exit 1
fi
git merge main -m "Merge main into master"
git checkout HEAD^1 -- run_play.sh deploy.yml nginx/conf.d/default.conf
echo "Done. main merged into master; run_play.sh, deploy.yml, nginx/conf.d/default.conf restored to production versions (staged, not committed)."
