# Branch protection for origin/main (requires gh auth / GH_TOKEN).
# Run from repo root after CI is green:
#
#   bash scripts/protect-main-branch.sh
#
# Or paste into GitHub → Settings → Branches → Add rule for `main`:
# - Require a pull request before merging
# - Require status checks: CI / Unit Tests, CI / Frontend Lint Typecheck Build,
#   CI / Trading Core Regression, CI / Lint & Format
# - Require branches to be up to date
# - Do not allow force pushes
# - Do not allow deletions

set -euo pipefail

REPO="${GITHUB_REPOSITORY:-QuantForg1/QuantForg}"

gh api -X PUT "repos/${REPO}/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Unit Tests",
      "Lint & Format",
      "Frontend Lint Typecheck Build",
      "Trading Core Regression"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF

echo "Branch protection applied to main (if API permitted)."
