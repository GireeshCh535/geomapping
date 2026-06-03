#!/usr/bin/env bash
# Merge main into master, then push master to trigger ECS deploy (GitHub Actions).
# Usage: git checkout master && ./scripts/merge-main-to-master.sh

set -e
if [[ $(git branch --show-current) != master ]]; then
  echo "Switch to master first: git checkout master"
  exit 1
fi
git merge main -m "Merge main into master"
echo "Done. Commit if needed, then: git push origin master"
