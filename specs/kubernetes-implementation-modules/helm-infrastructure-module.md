# Module 2: Helm Charts - Infrastructure Layer
## PostgreSQL, Redis, MinIO, RabbitMQ Deployment

**Estimated Time:** 1 week
**Dependencies:** Module 1 (OKE cluster running)
**Deliverables:** Data layer services deployed and operational

---

## Objectives

Deploy all stateful infrastructure services required by the Health Data AI Platform:
1. PostgreSQL (2 instances: health-data, webauthn-auth)
2. Redis (2 instances: health, webauthn)
3. MinIO (S3-compatible data lake)
4. RabbitMQ (message queue)

All services configured for the Oracle Always Free tier resource constraints.

---

## Architecture Overview

```
health-data namespace:
├── PostgreSQL (health-data)
│   ├── StatefulSet (1 primary pod)
│   ├── PVC: 60 GB
│   ├── Resources: 300m CPU, 1Gi RAM
│   └── Service: postgresql-health:5432
│
├── PostgreSQL (webauthn-auth)
│   ├── StatefulSet (1 primary pod)
│   ├── PVC: 20 GB
│   ├── Resources: 150m CPU, 512Mi RAM
│   └── Service: postgresql-auth:5432
│
├── Redis (health)
│   ├── StatefulSet (1 master pod)
│   ├── PVC: 5 GB
│   ├── Resources: 100m CPU, 256Mi RAM
│   └── Service: redis-health:6379
│
├── Redis (webauthn)
│   ├── StatefulSet (1 master pod)
│   ├── PVC: 5 GB
│   ├── Resources: 100m CPU, 256Mi RAM
│   └── Service: redis-auth:6379
│
├── MinIO
│   ├── StatefulSet (1 pod, standalone mode)
│   ├── PVC: 80 GB
│   ├── Resources: 200m CPU, 512Mi RAM
│   └── Service: minio:9000, minio-console:9001
│
└── RabbitMQ
    ├── StatefulSet (1 pod)
    ├── PVC: 15 GB
    ├── Resources: 300m CPU, 512Mi RAM
    └── Service: rabbitmq:5672, rabbitmq-management:15672
```

---

## Directory Structure

```
helm-charts/
└── health-platform/
    ├── Chart.yaml
    ├── values.yaml
    ├── values-production.yaml
    └── charts/
        └── infrastructure/
            ├── Chart.yaml
            ├── values.yaml
            ├── templates/
            │   ├── namespace.yaml
            │   ├── postgresql-health.yaml
            │   ├── postgresql-auth.yaml
            │   ├── redis-health.yaml
            │   ├── redis-auth.yaml
            │   ├── minio.yaml
            │   ├── rabbitmq.yaml
            │   └── secrets.yaml
            └── README.md
```

---

## Implementation Steps

### Step 1: Create Infrastructure Chart

**File: `helm-charts/health-platform/charts/infrastructure/Chart.yaml`**

```yaml
apiVersion: v2
name: infrastructure
description: Infrastructure layer for Health Data AI Platform
type: application
version: 1.0.0
appVersion: "1.0.0"

dependencies:
  - name: postgresql
    version: 13.2.24
    repository: https://charts.bitnami.com/bitnami
    alias: postgresql-health
    condition: postgresql-health.enabled

  - name: postgresql
    version: 13.2.24
    repository: https://charts.bitnami.com/bitnami
    alias: postgresql-auth
    condition: postgresql-auth.enabled

  - name: redis
    version: 18.4.0
    repository: https://charts.bitnami.com/bitnami
    alias: redis-health
    condition: redis-health.enabled

  - name: redis
    version: 18.4.0
    repository: https://charts.bitnami.com/bitnami
    alias: redis-auth
    condition: redis-auth.enabled

  - name: minio
    version: 12.11.3
    repository: https://charts.bitnami.com/bitnami
    condition: minio.enabled

  - name: rabbitmq
    version: 12.9.1
    repository: https://charts.bitnami.com/bitnami
    condition: rabbitmq.enabled
```

### Step 2: Configure Values for Always Free Tier

**File: `helm-charts/health-platform/charts/infrastructure/values.yaml`**

```yaml
# Namespace for data layer
namespace: health-data

# PostgreSQL - Health Data
postgresql-health:
  enabled: true
  global:
    postgresql:
      auth:
        existingSecret: postgresql-health-secret
        secretKeys:
          adminPasswordKey: postgres-password
          userPasswordKey: password

  primary:
    name: primary
    persistence:
      enabled: true
      storageClass: "oci-bv"  # OCI Block Volume
      size: 60Gi

    resources:
      requests:
        cpu: 300m
        memory: 1Gi
      limits:
        cpu: 500m
        memory: 2Gi

    podSecurityContext:
      enabled: true
      fsGroup: 1001

    containerSecurityContext:
      enabled: true
      runAsUser: 1001
      runAsNonRoot: true

  metrics:
    enabled: true
    serviceMonitor:
      enabled: true
      namespace: health-observability

# PostgreSQL - WebAuthn Auth
postgresql-auth:
  enabled: true
  global:
    postgresql:
      auth:
        existingSecret: postgresql-auth-secret
        secretKeys:
          adminPasswordKey: postgres-password
          userPasswordKey: password

  primary:
    persistence:
      enabled: true
      storageClass: "oci-bv"
      size: 20Gi

    resources:
      requests:
        cpu: 150m
        memory: 512Mi
      limits:
        cpu: 300m
        memory: 1Gi

  metrics:
    enabled: true
    serviceMonitor:
      enabled: true

# Redis - Health Data
redis-health:
  enabled: true
  architecture: standalone
  auth:
    enabled: true
    existingSecret: redis-health-secret
    existingSecretPasswordKey: password

  master:
    persistence:
      enabled: true
      storageClass: "oci-bv"
      size: 5Gi

    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 200m
        memory: 512Mi

  metrics:
    enabled: true
    serviceMonitor:
      enabled: true

# Redis - WebAuthn Sessions
redis-auth:
  enabled: true
  architecture: standalone
  auth:
    enabled: true
    existingSecret: redis-auth-secret
    existingSecretPasswordKey: password

  master:
    persistence:
      enabled: true
      storageClass: "oci-bv"
      size: 5Gi

    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 200m
        memory: 512Mi

# MinIO - S3-Compatible Data Lake
minio:
  enabled: true
  mode: standalone  # Single node for free tier

  auth:
    existingSecret: minio-secret

  persistence:
    enabled: true
    storageClass: "oci-bv"
    size: 80Gi

  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 400m
      memory: 1Gi

  service:
    type: ClusterIP
    ports:
      api: 9000
      console: 9001

  ingress:
    enabled: true
    ingressClassName: nginx
    hostname: minio.yourdomain.com
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-prod
    tls: true

  metrics:
    serviceMonitor:
      enabled: true

# RabbitMQ - Message Queue
rabbitmq:
  enabled: true
  replicaCount: 1  # Single instance for free tier

  auth:
    existingPasswordSecret: rabbitmq-secret
    existingErlangSecret: rabbitmq-erlang-secret

  persistence:
    enabled: true
    storageClass: "oci-bv"
    size: 15Gi

  resources:
    requests:
      cpu: 300m
      memory: 512Mi
    limits:
      cpu: 500m
      memory: 1Gi

  service:
    type: ClusterIP
    ports:
      amqp: 5672
      manager: 15672

  ingress:
    enabled: true
    ingressClassName: nginx
    hostname: rabbitmq.yourdomain.com
    tls: true

  metrics:
    enabled: true
    serviceMonitor:
      enabled: true
```

### Step 3: Create Secrets Template

**File: `helm-charts/health-platform/charts/infrastructure/templates/secrets.yaml`**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: {{ .Values.namespace }}
  labels:
    name: {{ .Values.namespace }}
---
# PostgreSQL Health Secret
apiVersion: v1
kind: Secret
metadata:
  name: postgresql-health-secret
  namespace: {{ .Values.namespace }}
type: Opaque
stringData:
  postgres-password: {{ .Values.secrets.postgresqlHealth.adminPassword | quote }}
  password: {{ .Values.secrets.postgresqlHealth.userPassword | quote }}
  username: {{ .Values.secrets.postgresqlHealth.username | quote }}
---
# PostgreSQL Auth Secret
apiVersion: v1
kind: Secret
metadata:
  name: postgresql-auth-secret
  namespace: {{ .Values.namespace }}
type: Opaque
stringData:
  postgres-password: {{ .Values.secrets.postgresqlAuth.adminPassword | quote }}
  password: {{ .Values.secrets.postgresqlAuth.userPassword | quote }}
  username: {{ .Values.secrets.postgresqlAuth.username | quote }}
---
# Redis Health Secret
apiVersion: v1
kind: Secret
metadata:
  name: redis-health-secret
  namespace: {{ .Values.namespace }}
type: Opaque
stringData:
  password: {{ .Values.secrets.redisHealth.password | quote }}
---
# Redis Auth Secret
apiVersion: v1
kind: Secret
metadata:
  name: redis-auth-secret
  namespace: {{ .Values.namespace }}
type: Opaque
stringData:
  password: {{ .Values.secrets.redisAuth.password | quote }}
---
# MinIO Secret
apiVersion: v1
kind: Secret
metadata:
  name: minio-secret
  namespace: {{ .Values.namespace }}
type: Opaque
stringData:
  root-user: {{ .Values.secrets.minio.rootUser | quote }}
  root-password: {{ .Values.secrets.minio.rootPassword | quote }}
---
# RabbitMQ Secret
apiVersion: v1
kind: Secret
metadata:
  name: rabbitmq-secret
  namespace: {{ .Values.namespace }}
type: Opaque
stringData:
  rabbitmq-password: {{ .Values.secrets.rabbitmq.password | quote }}
---
# RabbitMQ Erlang Cookie Secret
apiVersion: v1
kind: Secret
metadata:
  name: rabbitmq-erlang-secret
  namespace: {{ .Values.namespace }}
type: Opaque
stringData:
  rabbitmq-erlang-cookie: {{ .Values.secrets.rabbitmq.erlangCookie | quote }}
```

### Step 4: Production Values Override

**File: `helm-charts/health-platform/values-production.yaml`**

```yaml
infrastructure:
  enabled: true
  namespace: health-data

  # Secrets (MUST be replaced with Sealed Secrets in production)
  secrets:
    postgresqlHealth:
      adminPassword: "CHANGE_ME_ADMIN_PASSWORD"
      userPassword: "CHANGE_ME_USER_PASSWORD"
      username: "healthapi"

    postgresqlAuth:
      adminPassword: "CHANGE_ME_ADMIN_PASSWORD"
      userPassword: "CHANGE_ME_USER_PASSWORD"
      username: "webauthn"

    redisHealth:
      password: "CHANGE_ME_REDIS_PASSWORD"

    redisAuth:
      password: "CHANGE_ME_REDIS_PASSWORD"

    minio:
      rootUser: "admin"
      rootPassword: "CHANGE_ME_MINIO_PASSWORD"

    rabbitmq:
      password: "CHANGE_ME_RABBITMQ_PASSWORD"
      erlangCookie: "CHANGE_ME_ERLANG_COOKIE"

  # PostgreSQL Health - Production overrides
  postgresql-health:
    primary:
      persistence:
        size: 60Gi
      resources:
        requests:
          cpu: 300m
          memory: 1Gi

  # MinIO - Production configuration
  minio:
    ingress:
      hostname: minio.health-platform.example.com

  # RabbitMQ - Production configuration
  rabbitmq:
    ingress:
      hostname: rabbitmq.health-platform.example.com
```

---

## Deployment Commands

### Install Dependencies

```bash
# Add Bitnami repository
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Verify charts available
helm search repo bitnami/postgresql
helm search repo bitnami/redis
helm search repo bitnami/minio
helm search repo bitnami/rabbitmq
```

### Deploy Infrastructure

```bash
# 1. Create namespace
kubectl create namespace health-data

# 2. Deploy infrastructure chart
helm install infrastructure ./helm-charts/health-platform/charts/infrastructure \
  --namespace health-data \
  --values ./helm-charts/health-platform/values-production.yaml \
  --create-namespace

# 3. Watch deployment
kubectl get pods -n health-data -w

# Expected output after 2-5 minutes:
# NAME                                    READY   STATUS    RESTARTS   AGE
# postgresql-health-primary-0             1/1     Running   0          3m
# postgresql-auth-primary-0               1/1     Running   0          3m
# redis-health-master-0                   1/1     Running   0          3m
# redis-auth-master-0                     1/1     Running   0          3m
# minio-xxxxx                             1/1     Running   0          3m
# rabbitmq-0                              1/1     Running   0          3m
```

### Verify Deployments

```bash
# Check all pods are running
kubectl get pods -n health-data

# Check persistent volumes
kubectl get pvc -n health-data

# Expected PVCs:
# data-postgresql-health-primary-0     60Gi       Bound
# data-postgresql-auth-primary-0       20Gi       Bound
# redis-data-redis-health-master-0     5Gi        Bound
# redis-data-redis-auth-master-0       5Gi        Bound
# minio                                80Gi       Bound
# data-rabbitmq-0                      15Gi       Bound
# Total: 180 Gi (within 200 GB free tier) ✅

# Check services
kubectl get svc -n health-data

# Test PostgreSQL connection
kubectl run -it --rm psql-test \
  --image=postgres:15-alpine \
  --restart=Never \
  --namespace=health-data \
  -- psql -h postgresql-health -U healthapi -d postgres

# Test Redis connection
kubectl run -it --rm redis-test \
  --image=redis:7-alpine \
  --restart=Never \
  --namespace=health-data \
  -- redis-cli -h redis-health ping
# Expected: PONG
```

---

## Resource Verification

```bash
# Check resource usage
kubectl top pods -n health-data

# Expected output (approximate):
# NAME                            CPU    MEMORY
# postgresql-health-primary-0     150m   800Mi
# postgresql-auth-primary-0       80m    400Mi
# redis-health-master-0           50m    180Mi
# redis-auth-master-0             50m    180Mi
# minio-xxxxx                     120m   400Mi
# rabbitmq-0                      180m   450Mi
# -------------------------------------------
# Total:                          630m   2.4Gi ✅
```

---

## Connecting Services

### From Application Pods

```yaml
# PostgreSQL Health Connection
env:
  - name: DATABASE_URL
    value: "postgresql://healthapi:$(POSTGRES_PASSWORD)@postgresql-health.health-data.svc.cluster.local:5432/healthdb"
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: postgresql-health-secret
        key: password

# Redis Health Connection
env:
  - name: REDIS_URL
    value: "redis://:$(REDIS_PASSWORD)@redis-health.health-data.svc.cluster.local:6379"
  - name: REDIS_PASSWORD
    valueFrom:
      secretKeyRef:
        name: redis-health-secret
        key: password

# MinIO Connection
env:
  - name: S3_ENDPOINT_URL
    value: "http://minio.health-data.svc.cluster.local:9000"
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

# RabbitMQ Connection
env:
  - name: RABBITMQ_URL
    value: "amqp://user:$(RABBITMQ_PASSWORD)@rabbitmq.health-data.svc.cluster.local:5672/"
  - name: RABBITMQ_PASSWORD
    valueFrom:
      secretKeyRef:
        name: rabbitmq-secret
        key: rabbitmq-password
```

---

## Database Initialization

### PostgreSQL Health Database Setup

```bash
# Connect to PostgreSQL
kubectl exec -it postgresql-health-primary-0 -n health-data -- psql -U healthapi -d postgres

# Create database and tables
CREATE DATABASE healthdb;
\c healthdb

-- Create tables (based on your existing schema)
CREATE TABLE IF NOT EXISTS health_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    raw_data JSONB NOT NULL,
    processed_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_id ON health_records(user_id);
CREATE INDEX idx_data_type ON health_records(data_type);
CREATE INDEX idx_created_at ON health_records(created_at);

-- Verify
\dt
\q
```

### PostgreSQL Auth Database Setup

```bash
# Connect to auth PostgreSQL
kubectl exec -it postgresql-auth-primary-0 -n health-data -- psql -U webauthn -d postgres

# Create database
CREATE DATABASE webauthn;
\c webauthn

-- Create tables (based on webauthn-stack schema)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS credentials (
    id BYTEA PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    public_key BYTEA NOT NULL,
    sign_count BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

\q
```

### MinIO Bucket Setup

```bash
# Port-forward MinIO
kubectl port-forward svc/minio 9000:9000 9001:9001 -n health-data

# Install mc (MinIO client)
brew install minio/stable/mc

# Configure alias
mc alias set health-minio http://localhost:9000 admin CHANGE_ME_MINIO_PASSWORD

# Create buckets
mc mb health-minio/health-data
mc mb health-minio/processed-data
mc mb health-minio/backups

# Set lifecycle policy (auto-delete old data)
cat > lifecycle.json <<EOF
{
  "Rules": [{
    "ID": "Delete old raw data",
    "Status": "Enabled",
    "Filter": {
      "Prefix": "raw/"
    },
    "Expiration": {
      "Days": 90
    }
  }]
}
EOF

mc ilm import health-minio/health-data < lifecycle.json

# Verify
mc ls health-minio
```

---

## Upgrading

```bash
# Update values
vim helm-charts/health-platform/values-production.yaml

# Dry-run upgrade
helm upgrade infrastructure ./helm-charts/health-platform/charts/infrastructure \
  --namespace health-data \
  --values ./helm-charts/health-platform/values-production.yaml \
  --dry-run --debug

# Apply upgrade
helm upgrade infrastructure ./helm-charts/health-platform/charts/infrastructure \
  --namespace health-data \
  --values ./helm-charts/health-platform/values-production.yaml

# Watch rollout
kubectl rollout status statefulset/postgresql-health-primary -n health-data
```

---

## Troubleshooting

### Pods Not Starting

```bash
# Check pod events
kubectl describe pod postgresql-health-primary-0 -n health-data

# Common issue: PVC not bound
kubectl get pvc -n health-data
# Solution: Check StorageClass exists
kubectl get storageclass

# Common issue: Resource limits exceeded
kubectl top nodes
# Solution: Reduce resource requests in values.yaml
```

### PostgreSQL Connection Issues

```bash
# Check service DNS
kubectl run -it --rm debug \
  --image=busybox \
  --restart=Never \
  -n health-data \
  -- nslookup postgresql-health.health-data.svc.cluster.local

# Check logs
kubectl logs postgresql-health-primary-0 -n health-data

# Verify secret
kubectl get secret postgresql-health-secret -n health-data -o yaml
```

### Storage Full

```bash
# Check PVC usage
kubectl exec -it postgresql-health-primary-0 -n health-data -- df -h

# If > 80%:
# Option 1: Expand PVC (if supported)
kubectl edit pvc data-postgresql-health-primary-0 -n health-data
# Change size: 60Gi -> 80Gi

# Option 2: Clean up old data
kubectl exec -it postgresql-health-primary-0 -n health-data -- psql -U healthapi -d healthdb -c "DELETE FROM health_records WHERE created_at < NOW() - INTERVAL '90 days';"
```

---

## Success Criteria

- [ ] All 6 stateful services deployed and running
- [ ] All PVCs bound (total 180 GB / 200 GB free tier)
- [ ] PostgreSQL databases created and accessible
- [ ] Redis instances responding to PING
- [ ] MinIO buckets created
- [ ] RabbitMQ management UI accessible
- [ ] Total resource usage: < 1 vCPU, < 3 GB RAM
- [ ] Services accessible via Kubernetes DNS
- [ ] Metrics exporters working (ServiceMonitors created)

---

## Next Steps

1. ✅ **Module 2 Complete**: Infrastructure layer deployed
2. **Proceed to Module 3**: Deploy WebAuthn stack Helm chart
3. **Or Module 4**: Deploy Health API and ETL Engine

---

**Module 2 Complete**: Data layer infrastructure operational
