#!/bin/bash
# Deploy landing page to GitHub Pages with clean (squashed) history.
# Usage: ./deploy.sh

set -e

cd "$(dirname "$0")"

# Check for changes
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  echo "Nothing to deploy — no changes detected."
  exit 0
fi

# Squash everything into a single commit
git checkout --orphan fresh-main
git add -A
git commit -m "Digital business card landing page"
git branch -D main
git branch -m main
git push --force origin main

echo ""
echo "Deployed! Site will update in ~1 minute:"
echo "  https://maxpolwin.github.io/businesscard/maxpolwin"
