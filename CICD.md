# CI/CD Pipeline Documentation
# Health Data AI Platform - GitOps & Continuous Deployment

## Overview

This document describes the CI/CD pipeline for the Health Data AI Platform, implementing GitOps principles with ArgoCD for continuous deployment and GitHub Actions for continuous integration.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Developer Push to GitHub                                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub Actions (CI)                                         │
│  ├─ Run Tests (pytest, coverage)                            │
│  ├─ Build Multi-arch Docker Images (arm64 + amd64)          │
│  ├─ Push to GitHub Container Registry (ghcr.io)             │
│  ├─ Update Helm Chart Values (image tags)                   │
│  └─ Commit Back to Repository [skip ci]                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  ArgoCD (CD - GitOps Controller)                             │
│  ├─ Watches Git Repository for Changes                      │
│  ├─ Detects Updated Helm Chart Values                       │
│  ├─ Syncs Applications to Kubernetes (OKE)                  │
│  └─ Health Checks & Auto-Rollback on Failure                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Oracle OKE Cluster (Production)                             │
│  ├─ Development Environment (auto-sync)                     │
│  ├─ Staging Environment (auto-sync)                         │
│  └─ Production Environment (manual approval)                │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. GitHub Actions Workflows

Located in `.github/workflows/`, these workflows handle continuous integration:

#### Docker Build Workflows

**`docker-build-health-api.yml`**
- **Trigger**: Push to `main` or PR affecting `services/health-api-service/`
- **Actions**:
  - Run Python tests with coverage
  - Build multi-arch Docker image (arm64 + amd64)
  - Push to `ghcr.io/<owner>/health-api`
  - Update Helm chart image tag
- **Platforms**: linux/arm64, linux/amd64 (Oracle Ampere A1 + compatibility)

**`docker-build-etl-engine.yml`**
- **Trigger**: Push to `main` or PR affecting `services/etl-narrative-engine/`
- **Actions**:
  - Spin up RabbitMQ service for tests
  - Run Python tests with coverage
  - Build multi-arch Docker image (arm64 + amd64)
  - Push to `ghcr.io/<owner>/etl-engine`
  - Update Helm chart image tag

**`docker-build-webauthn.yml`**
- **Trigger**: Push to `main` or PR affecting `webauthn-stack/example-service/`
- **Actions**:
  - Build multi-arch Docker image for WebAuthn example service
  - Push to `ghcr.io/<owner>/webauthn-example-service`
  - Update Helm chart image tag

#### Helm Workflows

**`helm-lint-test.yml`**
- **Trigger**: Push to `main` or PR affecting `helm-charts/`
- **Actions**:
  - Lint all Helm charts
  - Run Helm unittest tests
  - Template charts with dev/production values
  - Validate Kubernetes manifests with kubeval
  - Security scanning with Checkov and TruffleHog
- **Charts Tested**: infrastructure, health-api, etl-engine, webauthn-stack, observability

#### Deployment Workflow

**`deploy-to-oke.yml`**
- **Trigger**: Manual workflow dispatch
- **Inputs**:
  - `environment`: dev, staging, or production
  - `chart_version`: Helm chart version (optional)
  - `dry_run`: Preview changes without applying
- **Actions**:
  - Configure OCI CLI for Oracle Cloud
  - Set up kubectl for OKE cluster
  - Deploy with Helm (with atomic rollback on failure)
  - Run smoke tests
  - Verify deployment health

### 2. ArgoCD GitOps

#### Installation

ArgoCD Helm chart located in `helm-charts/argocd/`:

```bash
# Install ArgoCD
helm install argocd helm-charts/argocd/ \
  --namespace argocd \
  --create-namespace \
  --values helm-charts/argocd/values-production.yaml

# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
```

**Key Features**:
- High availability (2 replicas for server and repo-server)
- Metrics and monitoring enabled
- ApplicationSet controller for managing multiple apps
- Notifications controller for Slack/email alerts

#### AppProject

Located in `argocd-apps/projects/health-platform-project.yaml`:

**Permissions**:
- Source repos: GitHub repository + Helm charts (Bitnami, Prometheus, Grafana, Jaeger)
- Destinations: All health-platform namespaces
- RBAC: Developer (read-only) and Admin (full access) roles

```bash
# Apply AppProject
kubectl apply -f argocd-apps/projects/health-platform-project.yaml
```

#### Applications

Located in `argocd-apps/applications/{env}/`:

**Development** (`dev/`):
- Auto-sync: ✅ Enabled
- Self-heal: ✅ Enabled
- Prune: ✅ Enabled
- Apps: infrastructure, health-api, etl-engine, webauthn-stack

**Staging** (`staging/`):
- Auto-sync: ✅ Enabled
- Self-heal: ✅ Enabled
- Prune: ✅ Enabled
- Apps: health-api (others to be added)

**Production** (`production/`):
- Auto-sync: ❌ Disabled (manual sync required)
- Self-heal: ❌ Disabled
- Sync Windows: Prevents deployments Mon-Fri 8am-5pm
- Apps: health-api (others to be added)

```bash
# Apply applications for dev environment
kubectl apply -f argocd-apps/applications/dev/

# Apply applications for production (manual sync required)
kubectl apply -f argocd-apps/applications/production/
argocd app sync health-api-production
```

### 3. Multi-Arch Docker Images

All Docker images support both **arm64** (Oracle Ampere A1) and **amd64** (x86_64) architectures.

**Multi-stage Build Pattern**:
```dockerfile
# Build stage - compile dependencies
FROM python:3.11-slim AS builder
RUN pip install --user -r requirements.txt

# Runtime stage - minimal image
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
# Application code and config
```

**Benefits**:
- Smaller image size (build tools not in runtime image)
- Better layer caching
- Security (minimal attack surface)
- Oracle Ampere A1 compatibility (arm64)

### 4. Helm Unit Tests

Located in `helm-charts/health-platform/charts/{chart}/tests/`:

**Test Coverage**:
- Deployment configuration
- Service configuration
- Resource limits
- Environment variables
- Security context
- Probes (liveness, readiness)

**Running Tests**:
```bash
# Install helm unittest plugin
helm plugin install https://github.com/helm-unittest/helm-unittest.git

# Run tests for a specific chart
cd helm-charts/health-platform/charts/health-api
helm unittest .

# Run tests for all charts
for chart in helm-charts/health-platform/charts/*/; do
  echo "Testing $chart..."
  helm unittest "$chart"
done
```

## Workflows

### Continuous Integration (CI)

**On Pull Request**:
1. Developer creates PR with code changes
2. GitHub Actions triggered:
   - Run tests (unit, integration)
   - Build Docker images (no push)
   - Lint Helm charts
   - Security scans
3. PR requires all checks to pass before merge

**On Push to Main**:
1. Code merged to `main` branch
2. GitHub Actions triggered:
   - Run tests with coverage
   - Build multi-arch Docker images
   - Push images to `ghcr.io`
   - Update Helm chart values with new image tags
   - Commit changes back to repo with `[skip ci]`

### Continuous Deployment (CD)

**Development Environment**:
1. ArgoCD detects Helm chart value changes (new image tags)
2. Auto-syncs applications to Kubernetes
3. Deploys new versions immediately
4. Self-heals if manual changes detected

**Staging Environment**:
1. Same as development
2. Used for pre-production validation

**Production Environment**:
1. ArgoCD detects changes but does NOT auto-sync
2. Administrator reviews changes in ArgoCD UI
3. Manual sync approval required
4. Sync window prevents deployments during business hours
5. Atomic deployment with auto-rollback on failure

### Manual Deployment to OKE

**Using GitHub Actions**:
```bash
# Navigate to Actions → Deploy to Oracle OKE → Run workflow
# Select environment: dev, staging, or production
# Optional: dry-run to preview changes
```

**Using ArgoCD CLI**:
```bash
# Login to ArgoCD
argocd login argocd.yourdomain.com

# Sync application
argocd app sync health-api-production

# Wait for sync to complete
argocd app wait health-api-production --health

# View deployment status
argocd app get health-api-production
```

**Using Helm Directly** (emergency only):
```bash
# Configure kubectl for OKE
# (requires OCI CLI configured)

# Deploy with Helm
cd helm-charts/health-platform
helm upgrade --install health-platform-production . \
  --namespace health-platform-production \
  --values values-production.yaml \
  --create-namespace \
  --wait \
  --atomic
```

## Environment Configuration

### Development (`values-dev.yaml`)
- Low resource limits
- Debug logging enabled
- In-memory storage where possible
- Single replicas
- No resource quotas

### Staging (`values-staging.yaml`)
- Production-like resource limits
- Info-level logging
- Persistent storage
- Multiple replicas (2)
- Resource quotas enabled

### Production (`values-production.yaml`)
- High resource limits
- Warn/error logging only
- Persistent storage with backups
- Multiple replicas (3+)
- Autoscaling enabled (HPA)
- Resource quotas enforced

## Secrets Management

### GitHub Secrets

Required secrets for GitHub Actions workflows:

**For Oracle OKE Deployment**:
- `OCI_USER_OCID`: Oracle Cloud user OCID
- `OCI_FINGERPRINT`: API key fingerprint
- `OCI_TENANCY_OCID`: Oracle Cloud tenancy OCID
- `OCI_REGION`: OCI region (e.g., `us-phoenix-1`)
- `OCI_PRIVATE_KEY`: Private API key
- `OKE_CLUSTER_OCID`: Oracle Kubernetes Engine cluster OCID

**For ArgoCD**:
- `ARGOCD_PASSWORD`: ArgoCD admin password (for CLI operations)

### Kubernetes Secrets

**Image Pull Secrets**:
```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=<github-username> \
  --docker-password=<github-token> \
  --namespace=health-platform-production
```

**Application Secrets**:
- Database passwords (PostgreSQL, Redis)
- S3 credentials (MinIO)
- Message queue credentials (RabbitMQ)
- JWT signing keys (WebAuthn)

These are managed via Kubernetes Secrets and mounted into pods.

## Monitoring & Observability

### ArgoCD Monitoring

**Metrics**:
- Application sync status
- Deployment health
- Git sync errors
- Kubernetes resource status

**Notifications**:
- Slack notifications on deployment success/failure
- Email alerts for health degradation
- Webhook integrations available

**Configure Notifications**:
```bash
# Install argocd-notifications
kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj-labs/argocd-notifications/stable/manifests/install.yaml

# Configure Slack secret
kubectl create secret generic argocd-notifications-secret \
  -n argocd \
  --from-literal=slack-token=<SLACK_BOT_TOKEN>
```

### Application Monitoring

**Prometheus Metrics**:
- Exposed by all services on `/metrics` endpoint
- Scraped by Prometheus in observability namespace
- Visualized in Grafana dashboards

**Distributed Tracing**:
- Jaeger integration for all services
- OpenTelemetry instrumentation
- Trace IDs in logs

**Logging**:
- Structured JSON logging
- Centralized log aggregation (Loki)
- Log correlation with trace IDs

## Rollback Procedures

### ArgoCD Rollback

```bash
# View deployment history
argocd app history health-api-production

# Rollback to previous version
argocd app rollback health-api-production

# Rollback to specific revision
argocd app rollback health-api-production 5

# Verify rollback
argocd app get health-api-production
kubectl get pods -n health-platform-production
```

### Helm Rollback

```bash
# View Helm release history
helm history health-platform-production -n health-platform-production

# Rollback to previous release
helm rollback health-platform-production -n health-platform-production

# Rollback to specific revision
helm rollback health-platform-production 3 -n health-platform-production
```

### Emergency Rollback

If both ArgoCD and Helm fail:

```bash
# Scale down problematic deployment
kubectl scale deployment health-api \
  --replicas=0 \
  -n health-platform-production

# Manually edit deployment to previous image tag
kubectl edit deployment health-api -n health-platform-production
# Change image tag to previous known-good version

# Scale back up
kubectl scale deployment health-api \
  --replicas=3 \
  -n health-platform-production
```

## Troubleshooting

### GitHub Actions Failures

**Build Failures**:
- Check logs in GitHub Actions UI
- Verify Docker buildx is configured correctly
- Check if base images are accessible
- Verify requirements.txt dependencies

**Test Failures**:
- Review test output in Actions logs
- Check if service dependencies (RabbitMQ, etc.) started correctly
- Verify environment variables are set

**Image Push Failures**:
- Verify GITHUB_TOKEN has packages:write permission
- Check GitHub Container Registry status
- Verify image name follows ghcr.io conventions

### ArgoCD Sync Failures

**Application Out of Sync**:
```bash
# Check sync status
argocd app get health-api-production

# View detailed sync errors
argocd app sync health-api-production --dry-run

# Force sync (use with caution)
argocd app sync health-api-production --force --prune
```

**Health Check Failures**:
```bash
# Check application health
argocd app get health-api-production

# View pod status in namespace
kubectl get pods -n health-platform-production

# Check pod logs
kubectl logs -f deployment/health-api -n health-platform-production

# Describe pod for events
kubectl describe pod <pod-name> -n health-platform-production
```

### Deployment Issues

**ImagePullBackOff**:
- Verify image exists in ghcr.io registry
- Check image pull secret is configured
- Verify network connectivity from OKE to ghcr.io

**CrashLoopBackOff**:
- Check pod logs: `kubectl logs <pod-name>`
- Verify environment variables and secrets
- Check resource limits (OOMKilled)
- Verify health check endpoints

**Pending Pods**:
- Check node resources: `kubectl describe nodes`
- Verify PVC bindings if using persistent storage
- Check resource quotas and limits

## Best Practices

### Development Workflow

1. **Feature Branch Development**:
   - Create feature branch from `main`
   - Develop and test locally
   - Push and create PR

2. **Pull Request Review**:
   - CI checks must pass
   - Code review required
   - Update tests as needed

3. **Merge to Main**:
   - Squash and merge
   - CI builds and pushes images
   - ArgoCD deploys to dev automatically

4. **Promotion to Staging**:
   - Monitor dev deployment
   - Staging auto-syncs from main
   - Run integration tests

5. **Production Deployment**:
   - Manual approval required
   - Deploy during maintenance window
   - Monitor closely, ready to rollback

### Helm Chart Updates

1. **Version Bumping**:
   - Increment chart version in Chart.yaml
   - Document changes in Chart.yaml annotations
   - Update appVersion if application version changed

2. **Values Updates**:
   - Never commit secrets to values files
   - Use separate values files per environment
   - Document all configurable options

3. **Testing**:
   - Write Helm unittest tests for new templates
   - Run `helm lint` before committing
   - Test with `helm template` and validate output

### Security

1. **Image Security**:
   - Use official base images
   - Multi-stage builds to minimize attack surface
   - Run as non-root user
   - Regular security scanning (Trivy, Snyk)

2. **Secrets Management**:
   - Never commit secrets to Git
   - Use Kubernetes Secrets
   - Rotate secrets regularly
   - Use external secret managers (Vault) for production

3. **RBAC**:
   - Principle of least privilege
   - Separate roles for dev and prod
   - Regular access reviews

## Resources

### Documentation
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Helm Documentation](https://helm.sh/docs/)
- [GitHub Actions Documentation](https://docs.github.com/actions)
- [Oracle OKE Documentation](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)

### Monitoring Dashboards
- ArgoCD UI: `https://argocd.yourdomain.com`
- Grafana: `https://grafana.yourdomain.com`
- Jaeger: `https://jaeger.yourdomain.com`
- Prometheus: `https://prometheus.yourdomain.com`

### Support Channels
- GitHub Issues: For bugs and feature requests
- Slack: #health-platform-ops (team communications)
- PagerDuty: Production alerts

---

**Last Updated**: 2025-11-20
**Maintained By**: Health Data AI Platform Team
