# ArgoCD Applications & Projects

This directory contains ArgoCD resource definitions for GitOps-based deployment of the Health Data AI Platform.

## Directory Structure

```
argocd-apps/
├── README.md                          # This file
├── projects/                          # ArgoCD AppProjects
│   └── health-platform-project.yaml  # Main AppProject for all services
└── applications/                      # ArgoCD Applications
    ├── README.md                      # Application deployment guide
    ├── dev/                          # Development environment
    │   ├── infrastructure.yaml
    │   ├── health-api.yaml
    │   ├── etl-engine.yaml
    │   └── webauthn-stack.yaml
    ├── staging/                      # Staging environment
    │   └── health-api.yaml
    └── production/                   # Production environment
        └── health-api.yaml
```

## Quick Start

### 1. Install ArgoCD

```bash
# Create namespace
kubectl create namespace argocd

# Install ArgoCD using our Helm chart
helm install argocd ../helm-charts/argocd/ \
  --namespace argocd \
  --create-namespace

# Wait for ArgoCD to be ready
kubectl wait --for=condition=available --timeout=300s \
  deployment/argocd-server -n argocd

# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

### 2. Access ArgoCD UI

```bash
# Port-forward to access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Login via CLI
argocd login localhost:8080 --username admin --insecure
```

### 3. Create AppProject

```bash
# Apply the health-platform AppProject
kubectl apply -f projects/health-platform-project.yaml

# Verify
argocd proj get health-platform
```

### 4. Deploy Applications

**Development Environment:**
```bash
# Deploy all dev applications
kubectl apply -f applications/dev/

# Watch sync status
argocd app list
argocd app sync --async infrastructure-dev health-api-dev etl-engine-dev webauthn-stack-dev
```

**Staging Environment:**
```bash
# Deploy staging applications
kubectl apply -f applications/staging/

# Verify sync
argocd app get health-api-staging
```

**Production Environment:**
```bash
# Apply production application definitions (manual sync required)
kubectl apply -f applications/production/

# Manually sync when ready
argocd app sync health-api-production --prune --timeout 600
```

## Environment Strategy

| Environment | Auto-Sync | Self-Heal | Prune | Sync Policy | Use Case |
|------------|-----------|-----------|-------|-------------|----------|
| Development | ✅ Yes | ✅ Yes | ✅ Yes | Automatic | Continuous deployment for testing |
| Staging | ✅ Yes | ✅ Yes | ✅ Yes | Automatic | Pre-production validation |
| Production | ❌ No | ❌ No | ⚠️ Manual | Manual approval | Stable production with controlled deployments |

## AppProject Configuration

The `health-platform` AppProject defines:

- **Source Repositories**: GitHub repo + Helm chart repositories (Bitnami, Prometheus, etc.)
- **Destinations**: All `health-platform-*` namespaces
- **Cluster Resources**: Namespaces, ClusterRoles, StorageClasses, CRDs
- **RBAC Roles**:
  - `developer`: Read-only access to applications and logs
  - `admin`: Full access to applications and repositories

## Application Configuration

Each Application manifest includes:

- **Source**: Git repository, path to Helm chart, values files
- **Destination**: Kubernetes cluster and namespace
- **Sync Policy**: Automated vs. manual, prune settings, retry logic
- **Health Checks**: Kubernetes resource health status
- **Ignore Differences**: Fields to ignore during sync (e.g., HPA-managed replicas)

### Customizing Applications

To modify an application:

1. Edit the YAML file in this directory
2. Apply changes: `kubectl apply -f applications/{env}/{service}.yaml`
3. ArgoCD will detect the change and update the Application resource
4. Sync the application if needed: `argocd app sync {app-name}`

## Common Operations

### Check Application Status

```bash
# List all applications
argocd app list

# Get detailed status
argocd app get health-api-production

# Watch sync progress
argocd app sync health-api-production --async
argocd app wait health-api-production --health
```

### Manual Sync

```bash
# Sync a single application
argocd app sync health-api-production

# Sync with pruning (remove deleted resources)
argocd app sync health-api-production --prune

# Dry-run to preview changes
argocd app sync health-api-production --dry-run
```

### View Differences

```bash
# See what would change
argocd app diff health-api-production

# Preview sync plan
argocd app manifests health-api-production
```

### Rollback

```bash
# View history
argocd app history health-api-production

# Rollback to previous version
argocd app rollback health-api-production

# Rollback to specific revision
argocd app rollback health-api-production 5
```

### Refresh & Hard Refresh

```bash
# Refresh application (re-check Git)
argocd app refresh health-api-production

# Hard refresh (bypass cache)
argocd app refresh health-api-production --hard
```

## Notifications

Applications are annotated for Slack notifications:

- `on-deployed`: Sent when application is successfully deployed
- `on-health-degraded`: Sent when application health degrades

Configure notifications in ArgoCD:

```bash
# Create notification secret
kubectl create secret generic argocd-notifications-secret \
  -n argocd \
  --from-literal=slack-token=<YOUR_SLACK_BOT_TOKEN>

# Configure notification templates (see CICD.md)
```

## Troubleshooting

### Application Stuck in "Progressing"

```bash
# Check sync status
argocd app get health-api-production

# View events
kubectl get events -n health-platform-production --sort-by='.lastTimestamp'

# Check pod status
kubectl get pods -n health-platform-production
kubectl logs -f deployment/health-api -n health-platform-production
```

### Sync Failed

```bash
# View sync errors
argocd app get health-api-production

# Try manual sync with prune
argocd app sync health-api-production --prune --force

# If all else fails, delete and recreate
kubectl delete -f applications/production/health-api.yaml
kubectl apply -f applications/production/health-api.yaml
```

### Out of Sync Despite Auto-Sync

```bash
# Check ignored differences
argocd app get health-api-dev

# Hard refresh to bypass cache
argocd app refresh health-api-dev --hard

# Verify sync policy
kubectl get application health-api-dev -n argocd -o yaml
```

## Best Practices

1. **Environment Promotion**:
   - Test in dev first
   - Promote to staging for validation
   - Deploy to production during maintenance window

2. **Sync Policies**:
   - Use auto-sync for dev/staging
   - Require manual approval for production
   - Enable pruning carefully (can delete resources)

3. **Health Checks**:
   - Define proper liveness/readiness probes
   - Configure health check timeouts appropriately
   - Monitor application health in ArgoCD UI

4. **Rollbacks**:
   - Test rollback procedures regularly
   - Keep at least 3 revisions in history
   - Document rollback procedures for each service

5. **Security**:
   - Use separate AppProjects for different teams
   - Implement RBAC for access control
   - Audit application changes regularly

## Additional Resources

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [ArgoCD Best Practices](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/)
- [Main CI/CD Documentation](../CICD.md)
- [Helm Charts](../helm-charts/health-platform/)

---

**Questions?** Contact the platform team or create an issue in the repository.
