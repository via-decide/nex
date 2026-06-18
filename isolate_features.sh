#!/bin/bash
cd /Users/dharamdaxini/Downloads/via/nex_repo

git fetch origin
git checkout main
git pull origin main

# Create the isolated sandbox branch
git checkout -b sandbox/unshipped-features

# Branches to merge
branches=(
  "origin/simba/build-a-zero-dependency-pure-python-neural-netwo"
  "origin/simba/create-topic-cluster-organizer"
  "origin/simba/create-a-sovereign-decision-intelligence-extract"
  "origin/codex/add-research-framing-layer-around-markdown-content-2026-05-03-czawp5"
)

for branch in "${branches[@]}"; do
  echo "Merging $branch..."
  git merge --no-edit "$branch" || {
    echo "Conflict detected in $branch. Resolving by taking PR changes (theirs)..."
    git checkout --theirs .
    git add .
    git commit -m "Auto-resolved conflict in favor of feature branch $branch"
  }
done

git push origin sandbox/unshipped-features
echo "Features isolated in branch sandbox/unshipped-features and pushed."
