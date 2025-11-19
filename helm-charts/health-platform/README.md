# Health Data AI Platform - Helm Charts

Complete Kubernetes deployment for the Health Data AI Platform, optimized for Oracle Cloud Infrastructure Always Free tier.

## Overview

This is an umbrella Helm chart that deploys the entire Health Data AI Platform stack:

- **Infrastructure Layer** (Module 2): PostgreSQL, Redis, MinIO, RabbitMQ
- **WebAuthn Stack** (Module 3): Authentication services (coming soon)
- **Health API** (Module 4): FastAPI health data upload service (coming soon)
- **ETL Engine** (Module 4): Clinical narrative processing (coming soon)
- **Observability** (Module 5): Prometheus, Grafana, Loki (coming soon)

## Quick Start

### Prerequisites

1. **Kubernetes Cluster**: OKE (Oracle Kubernetes Engine) 1.24+ or any Kubernetes cluster
2. **Helm**: Version 3.13 or later
3. **kubectl**: Configured to access your cluster
4. **StorageClass**: `oci-bv` (OCI Block Volume) for Oracle Cloud

### Installation

```bash
# 1. Add Bitnami repository
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# 2. Navigate to chart directory
cd helm-charts/health-platform

# 3. Update dependencies
helm dependency update

# 4. Install (development)
helm install health-platform . \
  --namespace health-data \
  --create-namespace

# 5. Install (production)
# First, edit values-production.yaml and replace all CHANGE_ME secrets
helm install health-platform . \
  -f values-production.yaml \
  --namespace health-data \
  --create-namespace
```

### Verify Installation

```bash
# Check all pods
kubectl get pods -n health-data

# Check services
kubectl get svc -n health-data

# Check persistent volumes
kubectl get pvc -n health-data

# View resource usage
kubectl top pods -n health-data
kubectl top nodes
```

## Architecture

### Current Implementation (Module 2)

```
┌─────────────────────────────────────────────────────────┐
│  health-data namespace                                  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Data Layer (StatefulSets)                         │ │
│  │                                                     │ │
│  │  ┌─────────────┐  ┌────────┐  ┌────────┐          │ │
│  │  │ PostgreSQL  │  │ Redis  │  │ MinIO  │          │ │
│  │  │ (2 inst)    │  │(2 inst)│  │        │          │ │
│  │  └─────────────┘  └────────┘  └────────┘          │ │
│  │                                                     │ │
│  │  ┌────────────┐                                    │ │
│  │  │ RabbitMQ   │                                    │ │
│  │  └────────────┘                                    │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Full Platform Architecture (When Complete)

```
┌──────────────────────────────────────────────────────────┐
│  Oracle Kubernetes Engine (OKE)                          │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Ingress Layer                                      │  │
│  │  - NGINX Ingress Controller                        │  │
│  │  - cert-manager (Let's Encrypt SSL)                │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Application Layer                                  │  │
│  │  - WebAuthn Stack (health-auth namespace)          │  │
│  │  - Health API (health-api namespace)               │  │
│  │  - ETL Engine (health-etl namespace)               │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Data Layer (health-data namespace)                 │  │
│  │  - PostgreSQL, Redis, MinIO, RabbitMQ              │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Observability (health-observability namespace)     │  │
│  │  - Prometheus, Grafana, Jaeger, Loki               │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Chart Structure

```
health-platform/
├── Chart.yaml                    # Umbrella chart definition
├── values.yaml                   # Default values for all components
├── values-production.yaml        # Production overrides
├── .helmignore                   # Files to exclude from packaging
├── README.md                     # This file
└── charts/
    ├── infrastructure/           # Module 2: Data layer (COMPLETE)
    │   ├── Chart.yaml
    │   ├── values.yaml
    │   ├── values-production.yaml
    │   ├── templates/
    │   │   └── secrets.yaml
    │   └── README.md
    │
    ├── webauthn-stack/          # Module 3: Authentication (TODO)
    ├── health-api/              # Module 4: API service (TODO)
    ├── etl-engine/              # Module 4: ETL processing (TODO)
    └── observability/           # Module 5: Monitoring (TODO)
```

## Components

### Infrastructure Layer (✅ Complete)

**Location:** `charts/infrastructure/`

Provides the data layer for the platform:
- PostgreSQL (health-data): 60 GB, primary database
- PostgreSQL (webauthn-auth): 20 GB, authentication
- Redis (health): 5 GB, rate limiting and caching
- Redis (auth): 5 GB, session storage
- MinIO: 80 GB, S3-compatible data lake
- RabbitMQ: 15 GB, message queue

**Resources:** 1.15 vCPU, 3 GB RAM, 185 GB storage

See [charts/infrastructure/README.md](charts/infrastructure/README.md) for details.

### WebAuthn Stack (⏳ Coming Soon)

**Module 3** - Authentication services

Will include:
- WebAuthn server (FIDO2 passwordless authentication)
- Envoy gateway (zero-trust entry point)
- Integration with PostgreSQL auth and Redis sessions

### Health API (⏳ Coming Soon)

**Module 4** - FastAPI health data upload service

Will include:
- FastAPI application deployment
- HorizontalPodAutoscaler for auto-scaling
- Ingress configuration
- Integration with health-data database

### ETL Engine (⏳ Coming Soon)

**Module 4** - Clinical narrative processing

Will include:
- ETL processing service
- CronJobs for scheduled data processing
- Integration with data lake and database

### Observability Stack (⏳ Coming Soon)

**Module 5** - Monitoring and observability

Will include:
- Prometheus (metrics collection)
- Grafana (visualization and dashboards)
- Loki (log aggregation)
- Promtail (log shipping)

Note: Jaeger (tracing) will be shared with WebAuthn stack.

## Configuration

### Default Values

The umbrella chart provides default values for all components. See [values.yaml](values.yaml).

To enable/disable components:

```yaml
infrastructure:
  enabled: true   # Data layer (currently the only implemented module)

webauthn-stack:
  enabled: false  # Enable after Module 3 implementation

health-api:
  enabled: false  # Enable after Module 4 implementation

etl-engine:
  enabled: false  # Enable after Module 4 implementation

observability:
  enabled: false  # Enable after Module 5 implementation
```

### Production Configuration

Production values include:
- Strong password placeholders (CHANGE_ME values)
- Resource limits optimized for Oracle Always Free tier
- Ingress configurations with SSL/TLS
- ServiceMonitors for Prometheus integration

Edit [values-production.yaml](values-production.yaml) before deploying to production.

### Secrets Management

**⚠️ SECURITY WARNING**: Never commit plaintext secrets to Git!

For production:

1. **Option 1: Sealed Secrets** (Recommended)
   ```bash
   # Install Sealed Secrets controller
   helm install sealed-secrets sealed-secrets/sealed-secrets \
     --namespace kube-system

   # Create and seal secrets
   kubectl create secret generic postgresql-health-secret \
     --from-literal=postgres-password=$(openssl rand -base64 32) \
     --dry-run=client -o yaml | \
     kubeseal -o yaml > postgresql-health-sealed.yaml

   # Apply sealed secret
   kubectl apply -f postgresql-health-sealed.yaml
   ```

2. **Option 2: OCI Vault** (Oracle Cloud native)
   - Use OCI Vault to store secrets
   - Use External Secrets Operator to sync to Kubernetes

3. **Option 3: HashiCorp Vault** (Multi-cloud)
   - External Vault instance
   - Vault Agent injector for pods

## Resource Allocation

### Oracle Always Free Tier Limits

- **Compute:** 4 ARM vCPUs (Ampere A1)
- **Memory:** 24 GB RAM
- **Storage:** 200 GB block volumes

### Current Allocation (Module 2 only)

| Component | CPU Request | Memory Request | Storage |
|-----------|-------------|----------------|---------|
| Infrastructure | 1150m (1.15 vCPU) | ~3 Gi | 185 Gi |
| **Available** | **2850m (2.85 vCPU)** | **~21 Gi** | **15 Gi** |

### Future Allocation (All Modules)

| Component | CPU Request | Memory Request | Storage |
|-----------|-------------|----------------|---------|
| Infrastructure | 1150m | ~3 Gi | 185 Gi |
| WebAuthn Stack | 550m | ~1.5 Gi | 0 Gi |
| Health API | 500m | ~0.5 Gi | 0 Gi |
| ETL Engine | 500m | ~1 Gi | 0 Gi |
| Observability | 1300m | ~5 Gi | 25 Gi* |
| **Total** | **4000m (4 vCPU)** | **~11 Gi** | **210 Gi*** |

*Note: Observability storage will use existing capacity with short retention periods

## Deployment Scenarios

### Development Environment

```bash
# Minimal deployment (infrastructure only)
helm install health-platform . \
  --set infrastructure.enabled=true \
  --set webauthn-stack.enabled=false \
  --set health-api.enabled=false \
  --namespace health-data \
  --create-namespace
```

### Staging Environment

```bash
# Full deployment with development values
helm install health-platform . \
  --set infrastructure.enabled=true \
  --set webauthn-stack.enabled=true \
  --set health-api.enabled=true \
  --set etl-engine.enabled=true \
  --namespace health-data \
  --create-namespace
```

### Production Environment

```bash
# Full deployment with production values and secrets
# First: Replace all CHANGE_ME values in values-production.yaml

helm install health-platform . \
  -f values-production.yaml \
  --namespace health-data \
  --create-namespace
```

## Upgrading

### Update Dependencies

```bash
# Update Bitnami charts to latest versions
helm repo update

# Update chart dependencies
cd helm-charts/health-platform
helm dependency update
```

### Upgrade Release

```bash
# Dry-run to preview changes
helm upgrade health-platform . \
  -f values-production.yaml \
  --namespace health-data \
  --dry-run --debug

# Apply upgrade
helm upgrade health-platform . \
  -f values-production.yaml \
  --namespace health-data

# Rollback if needed
helm rollback health-platform --namespace health-data
```

## Troubleshooting

### Common Issues

1. **Pods stuck in Pending**
   ```bash
   kubectl describe pod <pod-name> -n health-data
   # Common causes:
   # - Insufficient resources (CPU/memory)
   # - PVC not binding (check StorageClass)
   ```

2. **PVC not binding**
   ```bash
   kubectl get pvc -n health-data
   kubectl get storageclass
   # Ensure 'oci-bv' StorageClass exists
   ```

3. **Secrets not found**
   ```bash
   kubectl get secrets -n health-data
   # Ensure secrets are created before deploying chart
   ```

4. **Resource limits exceeded**
   ```bash
   kubectl top nodes
   kubectl top pods -n health-data
   # Adjust resource requests/limits in values.yaml
   ```

### Debug Commands

```bash
# View all resources
kubectl get all -n health-data

# Check pod logs
kubectl logs <pod-name> -n health-data

# Describe resources
kubectl describe pod <pod-name> -n health-data
kubectl describe pvc <pvc-name> -n health-data

# Test connections
kubectl run -it --rm debug \
  --image=busybox \
  --restart=Never \
  -n health-data \
  -- sh
```

## Uninstalling

```bash
# Remove the release
helm uninstall health-platform --namespace health-data

# Optional: Delete PVCs (⚠️ DATA LOSS!)
kubectl delete pvc --all -n health-data

# Optional: Delete namespace
kubectl delete namespace health-data
```

## Development

### Testing Chart Changes

```bash
# Lint the chart
helm lint .

# Template the chart (dry-run)
helm template health-platform . \
  -f values-production.yaml \
  --debug

# Install with dry-run
helm install health-platform . \
  -f values-production.yaml \
  --namespace health-data \
  --dry-run --debug
```

### Creating New Subcharts

```bash
# Create new subchart
helm create charts/my-new-service

# Add to Chart.yaml dependencies
# dependencies:
#   - name: my-new-service
#     version: 1.0.0
#     repository: file://./charts/my-new-service
#     condition: my-new-service.enabled
```

## Documentation

- **Module 2 Spec**: [specs/kubernetes-implementation-modules/helm-infrastructure-module.md](../../specs/kubernetes-implementation-modules/helm-infrastructure-module.md)
- **K8s Production Spec**: [specs/kubernetes-production-implementation-spec.md](../../specs/kubernetes-production-implementation-spec.md)
- **Infrastructure Chart**: [charts/infrastructure/README.md](charts/infrastructure/README.md)

## Implementation Status

| Module | Status | Description |
|--------|--------|-------------|
| Module 1 | ⏳ Pending | Terraform OKE cluster provisioning |
| **Module 2** | **✅ Complete** | **Helm infrastructure layer** |
| Module 3 | ⏳ Pending | Helm WebAuthn stack |
| Module 4 | ⏳ Pending | Helm health services |
| Module 5 | ⏳ Pending | Observability stack |
| Module 6 | ⏳ Pending | Security & RBAC |
| Module 7 | ⏳ Pending | GitOps & CI/CD |
| Module 8 | ⏳ Pending | Disaster recovery |

## Contributing

1. Create a feature branch
2. Make changes to charts
3. Test with `helm lint` and `helm template`
4. Submit pull request

## Support

- **Issues**: https://github.com/yourusername/health-data-ai-platform/issues
- **Documentation**: See `docs/` directory
- **Slack**: #health-platform-k8s (if applicable)

## License

MIT License - see LICENSE file for details

---

**Health Data AI Platform** - Production-ready Kubernetes deployment on Oracle Cloud Infrastructure Always Free tier ($0/month)
