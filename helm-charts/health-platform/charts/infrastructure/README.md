# Infrastructure Layer Helm Chart

Complete data layer infrastructure for the Health Data AI Platform, optimized for Oracle Cloud Infrastructure Always Free tier.

## Overview

This Helm chart deploys all stateful infrastructure services required by the Health Data AI Platform:

- **PostgreSQL** (2 instances): Health data and WebAuthn authentication databases
- **Redis** (2 instances): Rate limiting/caching and session storage
- **MinIO**: S3-compatible object storage for data lake
- **RabbitMQ**: Message queue for asynchronous processing

## Architecture

```
health-data namespace
├── PostgreSQL (health-data)    - 60 GB, 300m CPU, 1Gi RAM
├── PostgreSQL (webauthn-auth)  - 20 GB, 150m CPU, 512Mi RAM
├── Redis (health)              - 5 GB, 100m CPU, 256Mi RAM
├── Redis (auth)                - 5 GB, 100m CPU, 256Mi RAM
├── MinIO (data lake)           - 80 GB, 200m CPU, 512Mi RAM
└── RabbitMQ (message queue)    - 15 GB, 300m CPU, 512Mi RAM
```

**Total Resources:**
- CPU Requests: 1150m (1.15 vCPU)
- Memory Requests: ~3 Gi
- Storage: 185 Gi
- Fits within Oracle Always Free tier limits (4 vCPU, 24 GB RAM, 200 GB storage)

## Prerequisites

1. **Kubernetes Cluster**: OKE (Oracle Kubernetes Engine) or any Kubernetes 1.24+
2. **StorageClass**: `oci-bv` (OCI Block Volume) must be available
3. **Helm**: Version 3.13 or later
4. **kubectl**: Configured to access your cluster

### Optional (for production):
- **cert-manager**: For automatic SSL/TLS certificates
- **NGINX Ingress Controller**: For external access to MinIO and RabbitMQ
- **Sealed Secrets**: For encrypting secrets in Git

## Installation

### 1. Add Bitnami Repository

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
```

### 2. Install Infrastructure Chart

#### Development/Testing:

```bash
# Install with default values
helm install infrastructure . \
  --namespace health-data \
  --create-namespace

# Or specify custom values
helm install infrastructure . \
  -f values.yaml \
  --namespace health-data \
  --create-namespace
```

#### Production:

```bash
# First, update secrets in values-production.yaml
# Replace all CHANGE_ME values with actual secrets

# Install with production values
helm install infrastructure . \
  -f values-production.yaml \
  --namespace health-data \
  --create-namespace
```

### 3. Verify Installation

```bash
# Check all pods are running
kubectl get pods -n health-data

# Expected output:
# NAME                                    READY   STATUS    RESTARTS   AGE
# infrastructure-postgresql-health-0      1/1     Running   0          3m
# infrastructure-postgresql-auth-0        1/1     Running   0          3m
# infrastructure-redis-health-master-0    1/1     Running   0          3m
# infrastructure-redis-auth-master-0      1/1     Running   0          3m
# infrastructure-minio-xxxxx              1/1     Running   0          3m
# infrastructure-rabbitmq-0               1/1     Running   0          3m

# Check persistent volumes
kubectl get pvc -n health-data

# Check services
kubectl get svc -n health-data
```

## Configuration

### Default Values

See [values.yaml](values.yaml) for all configurable options.

Key configuration sections:

```yaml
# Resource allocation (Oracle Always Free optimized)
postgresql-health:
  resources:
    requests:
      cpu: 300m
      memory: 1Gi

# Storage configuration
postgresql-health:
  persistence:
    storageClass: "oci-bv"
    size: 60Gi

# Security settings
secrets:
  postgresqlHealth:
    adminPassword: "changeme"  # CHANGE IN PRODUCTION!
```

### Production Overrides

See [values-production.yaml](values-production.yaml) for production-ready configuration.

**IMPORTANT**: Replace all `CHANGE_ME` values with actual secrets before deploying to production.

### Generating Strong Passwords

```bash
# Generate 32-character password
openssl rand -base64 32

# Generate RabbitMQ Erlang cookie (exactly 32 characters)
openssl rand -base64 24
```

## Service Connections

### From Application Pods

All services are accessible via Kubernetes DNS:

#### PostgreSQL Health Database

```yaml
env:
  - name: DATABASE_URL
    value: "postgresql://healthapi:$(POSTGRES_PASSWORD)@infrastructure-postgresql-health.health-data.svc.cluster.local:5432/healthdb"
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: postgresql-health-secret
        key: password
```

#### Redis Health Cache

```yaml
env:
  - name: REDIS_URL
    value: "redis://:$(REDIS_PASSWORD)@infrastructure-redis-health-master.health-data.svc.cluster.local:6379"
  - name: REDIS_PASSWORD
    valueFrom:
      secretKeyRef:
        name: redis-health-secret
        key: password
```

#### MinIO Data Lake

```yaml
env:
  - name: S3_ENDPOINT_URL
    value: "http://infrastructure-minio.health-data.svc.cluster.local:9000"
  - name: S3_ACCESS_KEY
    valueFrom:
      secretKeyRef:
        name: minio-secret
        key: root-user
  - name: S3_SECRET_KEY
    valueFrom:
      secretKeyRef:
        name: minio-secret
        key: root-password
```

#### RabbitMQ Message Queue

```yaml
env:
  - name: RABBITMQ_URL
    value: "amqp://user:$(RABBITMQ_PASSWORD)@infrastructure-rabbitmq.health-data.svc.cluster.local:5672/"
  - name: RABBITMQ_PASSWORD
    valueFrom:
      secretKeyRef:
        name: rabbitmq-secret
        key: rabbitmq-password
```

## Database Initialization

### PostgreSQL Health Database

```bash
# Connect to database
kubectl exec -it infrastructure-postgresql-health-0 -n health-data -- psql -U healthapi -d postgres

# Create database
CREATE DATABASE healthdb;
\c healthdb

# Create tables
CREATE TABLE health_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    raw_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_id ON health_records(user_id);
CREATE INDEX idx_created_at ON health_records(created_at);

\q
```

### PostgreSQL Auth Database

```bash
# Connect to auth database
kubectl exec -it infrastructure-postgresql-auth-0 -n health-data -- psql -U webauthn -d postgres

# Create database
CREATE DATABASE webauthn;
\c webauthn

# Create tables (based on WebAuthn schema)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE credentials (
    id BYTEA PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    public_key BYTEA NOT NULL,
    sign_count BIGINT DEFAULT 0
);

\q
```

### MinIO Bucket Setup

```bash
# Port-forward MinIO
kubectl port-forward svc/infrastructure-minio 9000:9000 -n health-data

# Install MinIO client (mc)
brew install minio/stable/mc
# or: wget https://dl.min.io/client/mc/release/linux-amd64/mc

# Configure alias
mc alias set health-minio http://localhost:9000 admin YOUR_MINIO_PASSWORD

# Create buckets
mc mb health-minio/health-data
mc mb health-minio/processed-data
mc mb health-minio/backups

# Verify
mc ls health-minio
```

## Monitoring

All services export Prometheus metrics via ServiceMonitors:

```bash
# Check ServiceMonitors are created
kubectl get servicemonitor -n health-data

# View metrics endpoints
kubectl get svc -n health-data -l app.kubernetes.io/component=metrics
```

### Metrics Endpoints

- PostgreSQL: `http://infrastructure-postgresql-health-metrics:9187/metrics`
- Redis: `http://infrastructure-redis-health-metrics:9121/metrics`
- MinIO: `http://infrastructure-minio:9000/minio/v2/metrics/cluster`
- RabbitMQ: `http://infrastructure-rabbitmq:15692/metrics`

## Upgrading

### Update Chart Dependencies

```bash
helm dependency update
```

### Upgrade Release

```bash
# Dry-run to see changes
helm upgrade infrastructure . \
  -f values-production.yaml \
  --namespace health-data \
  --dry-run --debug

# Apply upgrade
helm upgrade infrastructure . \
  -f values-production.yaml \
  --namespace health-data

# Watch rollout
kubectl rollout status statefulset/infrastructure-postgresql-health -n health-data
```

## Backup and Restore

### PostgreSQL Backup

```bash
# Manual backup
kubectl exec -it infrastructure-postgresql-health-0 -n health-data -- \
  pg_dump -U healthapi -d healthdb > healthdb-backup-$(date +%Y%m%d).sql

# Restore from backup
kubectl exec -i infrastructure-postgresql-health-0 -n health-data -- \
  psql -U healthapi -d healthdb < healthdb-backup-20250119.sql
```

### MinIO Backup

```bash
# Mirror bucket to local
mc mirror health-minio/health-data ./backups/health-data

# Restore from local
mc mirror ./backups/health-data health-minio/health-data
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod events
kubectl describe pod infrastructure-postgresql-health-0 -n health-data

# Common issue: PVC not bound
kubectl get pvc -n health-data
# Solution: Verify StorageClass exists
kubectl get storageclass

# Check logs
kubectl logs infrastructure-postgresql-health-0 -n health-data
```

### Connection Issues

```bash
# Test DNS resolution
kubectl run -it --rm debug \
  --image=busybox \
  --restart=Never \
  -n health-data \
  -- nslookup infrastructure-postgresql-health.health-data.svc.cluster.local

# Test PostgreSQL connection
kubectl run -it --rm psql-test \
  --image=postgres:15-alpine \
  --restart=Never \
  --namespace=health-data \
  -- psql -h infrastructure-postgresql-health -U healthapi -d healthdb

# Test Redis connection
kubectl run -it --rm redis-test \
  --image=redis:7-alpine \
  --restart=Never \
  --namespace=health-data \
  -- redis-cli -h infrastructure-redis-health-master ping
```

### Storage Issues

```bash
# Check disk usage
kubectl exec -it infrastructure-postgresql-health-0 -n health-data -- df -h

# Expand PVC (if StorageClass supports it)
kubectl edit pvc data-infrastructure-postgresql-health-0 -n health-data
# Change size: 60Gi -> 80Gi
```

### Resource Constraints

```bash
# Check resource usage
kubectl top pods -n health-data
kubectl top nodes

# If resources are exhausted:
# 1. Reduce resource requests in values.yaml
# 2. Or scale down replicas (already at minimum for free tier)
# 3. Or add more nodes (requires paid tier)
```

## Uninstalling

```bash
# Remove the release
helm uninstall infrastructure --namespace health-data

# WARNING: This will NOT delete PVCs by default
# To also delete PVCs (DESTRUCTIVE - data loss!):
kubectl delete pvc --all -n health-data

# Delete namespace
kubectl delete namespace health-data
```

## Security

### Secrets Management

**Development:**
- Secrets are defined in `values.yaml` (NOT secure for production)

**Production:**
- Use Sealed Secrets to encrypt secrets before committing to Git
- Or use OCI Vault with External Secrets Operator
- Never commit plaintext secrets

### Example: Creating Sealed Secrets

```bash
# Install Sealed Secrets controller
helm install sealed-secrets sealed-secrets/sealed-secrets \
  --namespace kube-system

# Create and seal a secret
kubectl create secret generic postgresql-health-secret \
  --from-literal=postgres-password=$(openssl rand -base64 32) \
  --from-literal=password=$(openssl rand -base64 32) \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > postgresql-health-sealed.yaml

# Apply sealed secret
kubectl apply -f postgresql-health-sealed.yaml -n health-data
```

### Pod Security

All pods run with:
- Non-root user (UID 1001)
- Read-only root filesystem (where possible)
- Dropped capabilities
- No privilege escalation

## Resource Limits

### Oracle Always Free Tier Allocation

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit | Storage |
|---------|-------------|-----------|----------------|--------------|---------|
| PostgreSQL (health) | 300m | 500m | 1Gi | 2Gi | 60Gi |
| PostgreSQL (auth) | 150m | 300m | 512Mi | 1Gi | 20Gi |
| Redis (health) | 100m | 200m | 256Mi | 512Mi | 5Gi |
| Redis (auth) | 100m | 200m | 256Mi | 512Mi | 5Gi |
| MinIO | 200m | 400m | 512Mi | 1Gi | 80Gi |
| RabbitMQ | 300m | 500m | 512Mi | 1Gi | 15Gi |
| **Total** | **1150m** | **2100m** | **~3Gi** | **~6Gi** | **185Gi** |

**Remaining for applications:** ~2.85 vCPU, ~18 GB RAM, ~15 GB storage

## Support

- **Issues**: https://github.com/hitoshura25/health-data-ai-platform/issues
- **Documentation**: https://github.com/hitoshura25/health-data-ai-platform/tree/main/docs
- **Kubernetes Spec**: `specs/kubernetes-production-implementation-spec.md`

## License

MIT License - see LICENSE file for details

## Related Documentation

- [Module 2 Implementation Guide](../../../../specs/kubernetes-implementation-modules/helm-infrastructure-module.md)
- [Kubernetes Production Spec](../../../../specs/kubernetes-production-implementation-spec.md)
- [Bitnami PostgreSQL Chart](https://github.com/bitnami/charts/tree/main/bitnami/postgresql)
- [Bitnami Redis Chart](https://github.com/bitnami/charts/tree/main/bitnami/redis)
- [Bitnami MinIO Chart](https://github.com/bitnami/charts/tree/main/bitnami/minio)
- [Bitnami RabbitMQ Chart](https://github.com/bitnami/charts/tree/main/bitnami/rabbitmq)
