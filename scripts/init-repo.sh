#!/usr/bin/env bash
#
# FedClear — initialize the public GitHub repo under YOUR OWN identity.
# Run this locally on your machine (not in any shared environment).
#
# Prereqs:
#   - git installed and configured with YOUR name/email:
#       git config --global user.name  "Karthik Kapula"
#       git config --global user.email "<your-github-email>"
#   - GitHub CLI (gh) authenticated as YOU:  gh auth login
#
# Why "under your own identity": for AgentHack Section 8 verification and for a
# clean, independently-attributable contribution record, every commit must be
# yours. Do not use a shared account.

set -euo pipefail

REPO_NAME="fedclear"
DESCRIPTION="FedClear — Agentic ATO Compliance Adjudication (UiPath AgentHack 2026, Track 1: Maestro Case)"

cd "$(dirname "$0")/.."

git init
git add .
git commit -m "chore: scaffold FedClear repo (Apache-2.0, README, security, coding-agent evidence)"
git branch -M main

# Create the PUBLIC repo on GitHub and push.
gh repo create "$REPO_NAME" --public --source=. --remote=origin \
  --description "$DESCRIPTION" --push

echo
echo "Done. Next:"
echo "  1. Confirm Apache-2.0 shows in the repo 'About' box on GitHub."
echo "  2. Paste the repo URL into the Devpost submission + Confluence Submission Record."
echo "  3. Keep all future commits under your own identity."
