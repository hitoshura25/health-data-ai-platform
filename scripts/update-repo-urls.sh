#!/bin/bash
# update-repo-urls.sh
# Updates all ArgoCD repository URLs consistently across the platform

set -e

OLD_URL="https://github.com/hitoshura25/health-data-ai-platform"
NEW_URL="${1:-}"  # Accept URL as first argument

if [ -z "$NEW_URL" ]; then
  echo "Usage: $0 <new-repository-url>"
  echo ""
  echo "Example:"
  echo "  $0 https://github.com/your-org/your-repo"
  echo ""
  echo "Current repository URLs in use:"
  grep -h "repoURL:" argocd-apps/ -r --include="*.yaml" | sort | uniq
  exit 1
fi

echo "Updating repository URLs"
echo "========================"
echo "FROM: $OLD_URL"
echo "TO:   $NEW_URL"
echo ""

# Confirm with user
read -p "Continue with this update? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

# Find and replace in all ArgoCD application manifests
echo "Updating files..."
find argocd-apps -name "*.yaml" -type f -exec sed -i \
  "s|$OLD_URL|$NEW_URL|g" {} +

# Verify changes
echo ""
echo "✓ Updated files:"
grep -r "$NEW_URL" argocd-apps/ --include="*.yaml" | cut -d: -f1 | sort | uniq

echo ""
echo "✓ Verification - All repoURL values:"
grep -h "repoURL:" argocd-apps/ -r --include="*.yaml" | sort | uniq

echo ""
echo "✓ Done! Review changes with 'git diff argocd-apps/' before committing."
