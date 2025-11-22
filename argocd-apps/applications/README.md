# ArgoCD Applications

This directory contains ArgoCD Application manifests for deploying the Health Data AI Platform across multiple environments.

## Directory Structure

```
applications/
├── dev/                    # Development environment (auto-sync enabled)
│   ├── infrastructure.yaml
│   ├── health-api.yaml
│   ├── etl-engine.yaml
│   └── webauthn-stack.yaml
├── staging/               # Staging environment (auto-sync enabled)
│   └── health-api.yaml
└── production/           # Production environment (manual sync only)
    └── health-api.yaml
```

## Environment Strategy

### Development
- **Auto-sync**: Enabled
- **Self-heal**: Enabled
- **Prune**: Enabled
- **Purpose**: Continuous deployment for development and testing

### Staging
- **Auto-sync**: Enabled
- **Self-heal**: Enabled
- **Prune**: Enabled
- **Purpose**: Pre-production validation

### Production
- **Auto-sync**: Disabled (manual sync required)
- **Self-heal**: Disabled
- **Sync Windows**: Prevents deployments Mon-Fri 8am-5pm
- **Purpose**: Stable production environment with controlled deployments

## Applying Applications

### Install AppProject First
```bash
kubectl apply -f ../projects/health-platform-project.yaml
```

### Deploy to Development
```bash
kubectl apply -f dev/
```

### Deploy to Staging
```bash
kubectl apply -f staging/
```

### Deploy to Production (Manual Sync Required)
```bash
# Apply the application definition
kubectl apply -f production/health-api.yaml

# Sync manually via CLI
argocd app sync health-api-production

# Or via UI at https://argocd.yourdomain.com
```

## Adding New Services

To add a new service to ArgoCD:

1. Create application manifests in each environment directory
2. Update the AppProject if needed (for new namespaces)
3. Apply the manifests: `kubectl apply -f {env}/{service}.yaml`

## Monitoring

Check application status:
```bash
argocd app list
argocd app get health-api-dev
argocd app history health-api-dev
```

## Rollback

```bash
# View history
argocd app history health-api-production

# Rollback to previous version
argocd app rollback health-api-production

# Rollback to specific revision
argocd app rollback health-api-production 5
```
