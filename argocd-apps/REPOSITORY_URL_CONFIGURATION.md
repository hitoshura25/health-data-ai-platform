# Repository URL Configuration Guide

## Overview

All ArgoCD Application manifests in this repository contain a `repoURL` field that must be configured to match your GitHub repository. This guide explains how to update these URLs consistently across all environments.

## Repository URL Locations

The repository URL appears in the following files:

### ArgoCD Project
- `argocd-apps/projects/health-platform-project.yaml` (line 20)

### Development Environment
- `argocd-apps/applications/dev/health-api.yaml` (line 15)
- `argocd-apps/applications/dev/etl-engine.yaml` (line 15)
- `argocd-apps/applications/dev/webauthn-stack.yaml` (line 15)
- `argocd-apps/applications/dev/infrastructure.yaml` (line 12)

### Staging Environment
- `argocd-apps/applications/staging/health-api.yaml` (line 15)

### Production Environment
- `argocd-apps/applications/production/health-api.yaml` (line 15)

## Quick Update Script

Use this script to update all repository URLs at once:

```bash
#!/bin/bash
# update-repo-urls.sh

OLD_URL="https://github.com/hitoshura25/health-data-ai-platform"
NEW_URL="https://github.com/your-org/your-repo"  # UPDATE THIS

echo "Updating repository URLs from:"
echo "  $OLD_URL"
echo "to:"
echo "  $NEW_URL"
echo ""

# Find and replace in all ArgoCD application manifests
find argocd-apps -name "*.yaml" -type f -exec sed -i \
  "s|$OLD_URL|$NEW_URL|g" {} +

# Verify changes
echo "Updated files:"
grep -r "$NEW_URL" argocd-apps/ --include="*.yaml" | cut -d: -f1 | sort | uniq

echo ""
echo "Done! Please review the changes with 'git diff' before committing."
```

### Usage

1. Save the script as `scripts/update-repo-urls.sh`
2. Make it executable: `chmod +x scripts/update-repo-urls.sh`
3. Edit `NEW_URL` in the script to match your repository
4. Run: `./scripts/update-repo-urls.sh`
5. Review changes: `git diff argocd-apps/`
6. Commit: `git add argocd-apps/ && git commit -m "chore: update repository URLs"`

## Manual Update

If you prefer to update manually:

1. **Find all occurrences:**
   ```bash
   grep -r "repoURL:" argocd-apps/ --include="*.yaml"
   ```

2. **Update each file:**
   - Open each file listed above
   - Find the line with `repoURL: https://github.com/hitoshura25/health-data-ai-platform`
   - Replace with your repository URL
   - Save the file

3. **Verify consistency:**
   ```bash
   # All repoURL values should be identical
   grep -h "repoURL:" argocd-apps/applications/**/*.yaml | sort | uniq -c
   ```

## Production Best Practices

### Option 1: Separate GitOps Repository (Recommended)

For production deployments, consider using a separate repository for GitOps manifests:

**Benefits:**
- Decouple application code from deployment configurations
- Separate access control for code vs deployment
- Cleaner audit trail for production changes
- Different release cycles for app code vs manifests

**Implementation:**
1. Create a new repository: `your-org/health-platform-gitops`
2. Move `argocd-apps/` and `helm-charts/` to the new repository
3. Update `repoURL` in all manifests to point to the GitOps repository
4. Configure ArgoCD repository credentials for both repositories

### Option 2: Centralized Configuration (Alternative)

Use ArgoCD's repository credentials feature to abstract the URL:

1. **Add repository to ArgoCD:**
   ```bash
   argocd repo add https://github.com/your-org/your-repo \
     --name health-platform-repo \
     --username <username> \
     --password <github-token>
   ```

2. **Use short form in manifests:**
   ```yaml
   spec:
     source:
       repoURL: health-platform-repo  # Short name instead of full URL
   ```

   **Note:** This requires ArgoCD v2.5+ and may not work with all tools.

### Option 3: Environment Variables in CI/CD

For automated deployments, use environment variables:

1. **Template the repoURL:**
   ```yaml
   spec:
     source:
       repoURL: ${ARGOCD_REPO_URL}
   ```

2. **Substitute during deployment:**
   ```bash
   envsubst < application.yaml | kubectl apply -f -
   ```

## Verification

After updating URLs, verify ArgoCD can access the repository:

```bash
# Test repository connection
argocd repo list

# Refresh applications
argocd app list
argocd app sync <app-name> --dry-run

# Check application health
argocd app get <app-name>
```

## Troubleshooting

### ArgoCD Cannot Access Repository

**Error:** `repository not found` or `authentication failed`

**Solution:**
1. Verify repository URL is correct
2. Check repository credentials in ArgoCD:
   ```bash
   argocd repo list
   ```
3. Add/update credentials:
   ```bash
   argocd repo add https://github.com/your-org/your-repo \
     --username <username> \
     --password <github-token>
   ```

### Inconsistent Repository URLs

**Error:** Different URLs across environments

**Solution:**
```bash
# Find all unique repository URLs
grep -h "repoURL:" argocd-apps/ -r --include="*.yaml" | sort | uniq

# Should show only ONE unique URL (or two if using separate GitOps repo)
```

## Maintenance

When forking or migrating this repository:

1. Run the update script immediately after forking
2. Test in a development environment first
3. Update CI/CD workflows to use new repository URL
4. Update documentation references
5. Inform team members of the new repository location

---

**Last Updated:** 2025-11-22
**Maintained By:** Health Data AI Platform Team
