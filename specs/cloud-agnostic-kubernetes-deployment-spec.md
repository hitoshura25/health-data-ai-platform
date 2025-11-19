# Cloud-Agnostic Kubernetes Deployment Specification
## Health Data AI Platform Infrastructure

**Version:** 1.0
**Created:** 2025-11-18
**Status:** Draft

---

## Executive Summary

This specification defines a **cost-optimized, vendor-agnostic deployment strategy** for the Health Data AI Platform using Kubernetes, Helm, and Terraform. The solution prioritizes:

1. **Zero Vendor Lock-In**: Deploy to any cloud provider (AWS, GCP, Azure, DigitalOcean, Linode) or on-premises
2. **Cost Optimization**: Right-size resources, use spot/preemptible instances, implement auto-scaling
3. **Infrastructure as Code**: Full Terraform + Helm deployment for reproducibility
4. **Production-Ready**: High availability, security, observability, and disaster recovery

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Cost Optimization Strategy](#cost-optimization-strategy)
3. [Technology Stack](#technology-stack)
4. [Kubernetes Architecture](#kubernetes-architecture)
5. [Terraform Infrastructure](#terraform-infrastructure)
6. [Helm Charts](#helm-charts)
7. [Multi-Cloud Support](#multi-cloud-support)
8. [Security Architecture](#security-architecture)
9. [Disaster Recovery](#disaster-recovery)
10. [Migration Strategy](#migration-strategy)
11. [Implementation Phases](#implementation-phases)

---

## 1. Architecture Overview

### Current Docker Compose Stack

The platform currently consists of:

**WebAuthn Stack (Separate)**
- Envoy Gateway (port 8000) - Zero-trust entry point
- WebAuthn Server (FIDO2 + JWT authentication)
- PostgreSQL (port 5433) - Credentials only
- Redis (port 6380) - Sessions only
- Jaeger (port 16687) - Distributed tracing

**Health Services Stack**
- Health API Service (port 8001) - FastAPI upload service
- PostgreSQL (port 5432) - Health data
- Redis (port 6379) - Rate limiting
- MinIO (ports 9000/9001) - S3-compatible data lake
- RabbitMQ (ports 5672/15672) - Message queue
- ETL Narrative Engine (port 8002) - Data processing
- AI Query Interface (port 8003, planned) - MLflow + NLP

### Target Kubernetes Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Cloud Provider (AWS, GCP, Azure, DO, Linode, On-Prem)         │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Managed Kubernetes Service (EKS, GKE, AKS, DOKS, etc.)   │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Ingress Layer (NGINX/Traefik + Cert-Manager)        │ │ │
│  │  │  - TLS termination                                   │ │ │
│  │  │  - Load balancing                                    │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Application Layer (Kubernetes Deployments)          │ │ │
│  │  │  ┌────────────┐  ┌─────────────┐  ┌──────────────┐  │ │ │
│  │  │  │ WebAuthn   │  │  Health API │  │ ETL Narrative│  │ │ │
│  │  │  │ Stack      │  │  Service    │  │ Engine       │  │ │ │
│  │  │  └────────────┘  └─────────────┘  └──────────────┘  │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Data Layer (StatefulSets + PersistentVolumes)       │ │ │
│  │  │  ┌───────────┐  ┌────────┐  ┌─────────┐  ┌────────┐ │ │ │
│  │  │  │PostgreSQL │  │ Redis  │  │ MinIO   │  │RabbitMQ│ │ │ │
│  │  │  │(Primary + │  │(Cluster)│ │(S3 API) │  │(HA)    │ │ │ │
│  │  │  │ Replicas) │  │         │  │         │  │        │ │ │ │
│  │  │  └───────────┘  └────────┘  └─────────┘  └────────┘ │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Observability Layer                                  │ │ │
│  │  │  ┌─────────┐  ┌──────────┐  ┌─────────────────────┐ │ │ │
│  │  │  │ Jaeger  │  │Prometheus│  │ Grafana + Loki      │ │ │ │
│  │  │  │(Tracing)│  │(Metrics) │  │ (Logs + Dashboards) │ │ │ │
│  │  │  └─────────┘  └──────────┘  └─────────────────────┘ │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Cost Optimization Strategy

### 2.1 Cheapest Production-Ready Deployment Options

#### Option A: Managed Kubernetes - Budget Tier ($50-150/month)
**Providers:**
- **DigitalOcean Kubernetes (DOKS)**: $12/month per node (2 vCPU, 4GB RAM)
- **Linode Kubernetes Engine (LKE)**: $12/month per node (2 vCPU, 4GB RAM)
- **Civo Cloud**: $10/month per node (2 vCPU, 4GB RAM) - k3s-based
- **Vultr Kubernetes Engine**: $12/month per node (2 vCPU, 4GB RAM)

**Recommended Configuration for Small-Scale Production:**
```yaml
# 3-node cluster for HA
- 3x worker nodes: 2 vCPU, 4GB RAM each ($36/month)
- Control plane: Free (managed by provider)
- Load balancer: $12/month (DigitalOcean/Linode)
- Block storage: $10/month (100GB SSD)
- Backups: $5-10/month
---
Total: ~$60-75/month
```

#### Option B: Self-Managed K3s Cluster ($20-40/month)
**Providers:** DigitalOcean Droplets, Linode VMs, Hetzner Cloud

**Recommended Configuration:**
```yaml
# Single-node k3s for development/small production
- 1x server: 4 vCPU, 8GB RAM ($24/month Hetzner, $48/month DO)
- Block storage: $10/month (100GB SSD)
- Backups: $5/month
---
Total: ~$40-65/month
```

#### Option C: Hybrid Cloud-Agnostic (Production at Scale)
**For growth beyond initial deployment:**
- Use **Spot/Preemptible instances** for non-critical workloads (70% cost savings)
- Reserve instances for stateful services (PostgreSQL, RabbitMQ)
- Auto-scaling with cluster-autoscaler (scale to zero during off-hours)

### 2.2 Resource Right-Sizing

Based on current docker-compose resource allocation:

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit | Notes |
|---------|-------------|-----------|----------------|--------------|-------|
| Health API | 250m | 1000m | 256Mi | 512Mi | FastAPI + Uvicorn |
| WebAuthn Server | 500m | 1000m | 512Mi | 1Gi | Java application |
| PostgreSQL (Health) | 500m | 1000m | 512Mi | 1Gi | Primary database |
| PostgreSQL (WebAuthn) | 250m | 500m | 256Mi | 512Mi | Auth only |
| Redis (Health) | 100m | 250m | 128Mi | 256Mi | Rate limiting |
| Redis (WebAuthn) | 100m | 250m | 128Mi | 256Mi | Sessions |
| MinIO | 500m | 1000m | 512Mi | 1Gi | Object storage |
| RabbitMQ | 500m | 1000m | 512Mi | 1Gi | Message queue |
| Envoy Gateway | 100m | 500m | 128Mi | 256Mi | Reverse proxy |
| Jaeger | 250m | 500m | 256Mi | 512Mi | Tracing |
| ETL Engine | 500m | 2000m | 512Mi | 2Gi | Data processing |
| **TOTAL** | **3.55 vCPU** | **9.5 vCPU** | **3.7 GB** | **9.2 GB** |

**Minimum Cluster Requirements:**
- **Development**: 1 node with 4 vCPU, 8GB RAM
- **Production HA**: 3 nodes with 2 vCPU, 4GB RAM each (6 vCPU total, 12GB RAM)
- **Production Scale**: 3 nodes with 4 vCPU, 8GB RAM each (12 vCPU total, 24GB RAM)

### 2.3 Cost Optimization Techniques

#### Auto-Scaling Strategy
```yaml
# Horizontal Pod Autoscaler (HPA)
- Health API: Scale 1-5 pods based on CPU >70% or requests/sec
- ETL Engine: Scale 1-3 pods based on queue depth
- WebAuthn: Scale 1-3 pods based on CPU >60%

# Cluster Autoscaler
- Minimum nodes: 2 (production) / 1 (dev)
- Maximum nodes: 10
- Scale down after 10 minutes of <50% utilization
```

#### Spot Instance Strategy (for AWS/GCP/Azure)
```yaml
# Node pools
- Critical (on-demand): PostgreSQL, RabbitMQ, MinIO
- Burstable (spot): Health API, ETL Engine, WebAuthn (with pod disruption budgets)
- Savings: 60-70% on compute costs for burstable workloads
```

#### Storage Optimization
```yaml
# Use cheaper storage classes where appropriate
- PostgreSQL: SSD persistent disk (required for IOPS)
- MinIO: Standard persistent disk or object storage (cost-effective bulk storage)
- Redis: SSD for performance
- Logs: Cheap object storage with lifecycle policies (delete after 30 days)
```

---

## 3. Technology Stack

### 3.1 Kubernetes Distribution Options

| Distribution | Use Case | Cost Model | Vendor Lock-In |
|--------------|----------|------------|----------------|
| **k3s** | Self-managed, edge, IoT | Free (pay for VMs only) | None |
| **Amazon EKS** | AWS-native | $0.10/hr per cluster + nodes | Medium (AWS-specific features) |
| **Google GKE** | GCP-native | $0.10/hr per cluster + nodes | Medium (GCP-specific features) |
| **Azure AKS** | Azure-native | Free control plane + nodes | Medium (Azure-specific features) |
| **DigitalOcean DOKS** | Simplicity, cost | Free control plane + nodes | Low |
| **Linode LKE** | Cost, developer-friendly | Free control plane + nodes | Low |
| **Civo Cloud** | Fastest provisioning, k3s | Free control plane + nodes | Low |
| **Rancher RKE2** | Multi-cloud, enterprise | Free (pay for VMs) | None |
| **Vanilla Kubernetes** | Full control, any cloud | Free (pay for VMs) | None |

**Recommendation**: Start with **DigitalOcean DOKS** or **Linode LKE** for best cost/simplicity tradeoff, then migrate to multi-cloud Terraform modules for portability.

### 3.2 Infrastructure as Code

| Tool | Purpose | Why |
|------|---------|-----|
| **Terraform** | Provision Kubernetes clusters, networking, DNS | Cloud-agnostic, state management, mature ecosystem |
| **Helm** | Package and deploy applications | Templating, versioning, rollback support |
| **kubectl** | Kubernetes CLI operations | Standard Kubernetes tooling |
| **kustomize** | Environment-specific config overlays | Built into kubectl, GitOps-friendly |

### 3.3 Cloud-Agnostic Components

| Component | Technology | Alternatives | Vendor Lock-In Risk |
|-----------|------------|--------------|---------------------|
| **Ingress Controller** | NGINX Ingress | Traefik, HAProxy | None |
| **Certificate Management** | cert-manager | External ACME client | None |
| **Secret Management** | Sealed Secrets / External Secrets Operator | Vault, SOPS | None (with External Secrets) |
| **Monitoring** | Prometheus + Grafana | Victoria Metrics | None |
| **Logging** | Loki + Promtail | ELK, Fluentd | None |
| **Tracing** | Jaeger (already deployed) | Zipkin, Tempo | None |
| **Service Mesh** | (Optional) Linkerd | Istio, Cilium | None |
| **GitOps** | ArgoCD or FluxCD | Manual kubectl | None |
| **Container Registry** | Docker Hub (public), GitHub Container Registry | Harbor (self-hosted) | None |

---

## 4. Kubernetes Architecture

### 4.1 Namespace Strategy

```yaml
# Production environment
namespaces:
  - health-platform-system    # Ingress, cert-manager, secrets
  - health-platform-auth      # WebAuthn stack
  - health-platform-api       # Health API, ETL Engine
  - health-platform-data      # PostgreSQL, Redis, MinIO, RabbitMQ
  - health-platform-observability # Prometheus, Grafana, Loki, Jaeger
```

### 4.2 Network Policies

```yaml
# Default deny all ingress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
spec:
  podSelector: {}
  policyTypes:
  - Ingress

# Allow specific service-to-service communication
- Health API → PostgreSQL (health-data), Redis, RabbitMQ, MinIO
- WebAuthn Server → PostgreSQL (webauthn-auth), Redis (webauthn-sessions)
- ETL Engine → MinIO, RabbitMQ, PostgreSQL (health-data)
- All services → Jaeger (tracing)
- Ingress → Health API, WebAuthn Gateway
```

### 4.3 Storage Classes

```yaml
# Cloud-agnostic storage class definitions
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: fast-ssd
provisioner: # Cloud-specific (ebs.csi.aws.com, pd.csi.storage.gke.io, etc.)
parameters:
  type: gp3 # or pd-ssd (GCP), Premium_LRS (Azure), etc.
  iops: "3000"
volumeBindingMode: WaitForFirstConsumer

---
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: standard
provisioner: # Cloud-specific
parameters:
  type: gp2 # or pd-standard (GCP), Standard_LRS (Azure), etc.
volumeBindingMode: WaitForFirstConsumer
```

### 4.4 Deployment Strategy

| Service | Deployment Type | Replicas | Strategy | Notes |
|---------|----------------|----------|----------|-------|
| Health API | Deployment | 2-5 (HPA) | RollingUpdate | Stateless, auto-scale |
| WebAuthn Server | Deployment | 2-3 (HPA) | RollingUpdate | Stateless, session in Redis |
| Envoy Gateway | Deployment | 2-3 | RollingUpdate | HA proxy |
| PostgreSQL | StatefulSet | 1 primary + 2 replicas | RollingUpdate | Streaming replication |
| Redis | StatefulSet | 3 (sentinel) | RollingUpdate | Redis Cluster or Sentinel |
| MinIO | StatefulSet | 4 (distributed) | RollingUpdate | Distributed mode for HA |
| RabbitMQ | StatefulSet | 3 (cluster) | RollingUpdate | Quorum queues |
| Jaeger | Deployment | 1-2 | RollingUpdate | Stateless (use external storage) |

---

## 5. Terraform Infrastructure

### 5.1 Directory Structure

```
terraform/
├── modules/
│   ├── kubernetes-cluster/        # Kubernetes cluster provisioning
│   │   ├── aws-eks/              # AWS-specific implementation
│   │   ├── gcp-gke/              # GCP-specific implementation
│   │   ├── azure-aks/            # Azure-specific implementation
│   │   ├── digitalocean-doks/    # DigitalOcean-specific
│   │   ├── linode-lke/           # Linode-specific
│   │   └── k3s/                  # Self-managed k3s
│   ├── networking/               # VPC, subnets, firewall rules
│   ├── dns/                      # DNS zone management
│   ├── storage/                  # Object storage (S3, GCS, Azure Blob)
│   └── monitoring/               # Cloud-native monitoring integration
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars
│   ├── staging/
│   └── production/
└── backend.tf                    # Remote state configuration
```

### 5.2 Cloud-Agnostic Cluster Module Interface

```hcl
# terraform/modules/kubernetes-cluster/interface.tf
# Defines standard interface for all cloud providers

variable "cluster_name" {
  type = string
}

variable "region" {
  type = string
}

variable "node_pools" {
  type = list(object({
    name         = string
    size         = string
    min_nodes    = number
    max_nodes    = number
    auto_scale   = bool
    preemptible  = bool  # spot instances
  }))
}

variable "kubernetes_version" {
  type    = string
  default = "1.28"
}

output "cluster_endpoint" {
  value = # Cloud-specific
}

output "cluster_ca_certificate" {
  value     = # Cloud-specific
  sensitive = true
}

output "kubeconfig" {
  value     = # Cloud-specific
  sensitive = true
}
```

### 5.3 Multi-Cloud Provider Selection

```hcl
# terraform/environments/production/main.tf

# Provider selection via variable
variable "cloud_provider" {
  type    = string
  default = "digitalocean"
  validation {
    condition     = contains(["aws", "gcp", "azure", "digitalocean", "linode", "k3s"], var.cloud_provider)
    error_message = "Supported providers: aws, gcp, azure, digitalocean, linode, k3s"
  }
}

# Dynamic module source based on provider
module "kubernetes_cluster" {
  source = "../../modules/kubernetes-cluster/${var.cloud_provider}"

  cluster_name       = var.cluster_name
  region             = var.region
  node_pools         = var.node_pools
  kubernetes_version = var.kubernetes_version
}

# Cloud-agnostic outputs
output "kubeconfig" {
  value     = module.kubernetes_cluster.kubeconfig
  sensitive = true
}
```

### 5.4 Example: DigitalOcean Terraform Module

```hcl
# terraform/modules/kubernetes-cluster/digitalocean-doks/main.tf

terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.34"
    }
  }
}

resource "digitalocean_kubernetes_cluster" "main" {
  name    = var.cluster_name
  region  = var.region
  version = var.kubernetes_version

  # Default node pool (required by DOKS)
  node_pool {
    name       = var.node_pools[0].name
    size       = var.node_pools[0].size
    auto_scale = var.node_pools[0].auto_scale
    min_nodes  = var.node_pools[0].min_nodes
    max_nodes  = var.node_pools[0].max_nodes
  }

  # HA control plane (free on DO)
  ha = true

  # Automatic upgrades during maintenance window
  auto_upgrade = true
  maintenance_policy {
    day        = "sunday"
    start_time = "03:00"
  }
}

# Additional node pools
resource "digitalocean_kubernetes_node_pool" "additional" {
  count = length(var.node_pools) - 1

  cluster_id = digitalocean_kubernetes_cluster.main.id
  name       = var.node_pools[count.index + 1].name
  size       = var.node_pools[count.index + 1].size
  auto_scale = var.node_pools[count.index + 1].auto_scale
  min_nodes  = var.node_pools[count.index + 1].min_nodes
  max_nodes  = var.node_pools[count.index + 1].max_nodes
}

output "kubeconfig" {
  value     = digitalocean_kubernetes_cluster.main.kube_config[0].raw_config
  sensitive = true
}
```

### 5.5 Example Production Environment Configuration

```hcl
# terraform/environments/production/terraform.tfvars

cloud_provider     = "digitalocean"
cluster_name       = "health-platform-prod"
region             = "nyc3"
kubernetes_version = "1.28.2-do.0"

node_pools = [
  {
    name        = "system"
    size        = "s-2vcpu-4gb"  # $24/month per node
    min_nodes   = 2
    max_nodes   = 3
    auto_scale  = true
    preemptible = false
  },
  {
    name        = "workload"
    size        = "s-2vcpu-4gb"
    min_nodes   = 1
    max_nodes   = 5
    auto_scale  = true
    preemptible = false  # DigitalOcean doesn't support spot instances
  }
]
```

---

## 6. Helm Charts

### 6.1 Chart Structure

```
helm-charts/
├── health-platform/                    # Umbrella chart
│   ├── Chart.yaml
│   ├── values.yaml                     # Default values
│   ├── values-dev.yaml                 # Dev environment overrides
│   ├── values-production.yaml          # Production overrides
│   └── charts/
│       ├── webauthn-stack/             # WebAuthn services
│       ├── health-api/                 # Health API service
│       ├── etl-engine/                 # ETL Narrative Engine
│       ├── infrastructure/             # PostgreSQL, Redis, MinIO, RabbitMQ
│       └── observability/              # Jaeger, Prometheus, Grafana
└── README.md
```

### 6.2 Example: Health API Helm Chart

```yaml
# helm-charts/health-platform/charts/health-api/Chart.yaml
apiVersion: v2
name: health-api
description: Health Data AI Platform - API Service
type: application
version: 1.0.0
appVersion: "1.0.0"

dependencies:
  - name: postgresql
    version: 13.2.24
    repository: https://charts.bitnami.com/bitnami
    condition: postgresql.enabled
  - name: redis
    version: 18.4.0
    repository: https://charts.bitnami.com/bitnami
    condition: redis.enabled
```

```yaml
# helm-charts/health-platform/charts/health-api/values.yaml
replicaCount: 2

image:
  repository: ghcr.io/your-org/health-api
  tag: "1.0.0"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8001

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: api.health-platform.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: health-api-tls
      hosts:
        - api.health-platform.example.com

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

resources:
  requests:
    cpu: 250m
    memory: 256Mi
  limits:
    cpu: 1000m
    memory: 512Mi

env:
  - name: POSTGRES_HOST
    value: "{{ .Release.Name }}-postgresql"
  - name: REDIS_URL
    value: "redis://{{ .Release.Name }}-redis-master:6379"
  - name: S3_ENDPOINT_URL
    value: "http://{{ .Release.Name }}-minio:9000"

envFrom:
  - secretRef:
      name: health-api-secrets

postgresql:
  enabled: true
  auth:
    existingSecret: health-api-postgres-secret

redis:
  enabled: true
  auth:
    existingSecret: health-api-redis-secret
```

```yaml
# helm-charts/health-platform/charts/health-api/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "health-api.fullname" . }}
  labels:
    {{- include "health-api.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "health-api.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
      labels:
        {{- include "health-api.selectorLabels" . | nindent 8 }}
    spec:
      containers:
      - name: health-api
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        ports:
        - name: http
          containerPort: 8001
          protocol: TCP
        env:
          {{- toYaml .Values.env | nindent 10 }}
        envFrom:
          {{- toYaml .Values.envFrom | nindent 10 }}
        livenessProbe:
          httpGet:
            path: /health/live
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          {{- toYaml .Values.resources | nindent 12 }}
```

### 6.3 Umbrella Chart Values

```yaml
# helm-charts/health-platform/values-production.yaml
global:
  storageClass: fast-ssd
  domain: health-platform.example.com

webauthn-stack:
  enabled: true
  replicaCount: 3
  resources:
    requests:
      cpu: 500m
      memory: 512Mi

health-api:
  enabled: true
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10

infrastructure:
  postgresql:
    enabled: true
    architecture: replication
    primary:
      persistence:
        size: 50Gi
    readReplicas:
      replicaCount: 2

  minio:
    enabled: true
    mode: distributed
    replicas: 4
    persistence:
      size: 100Gi

  rabbitmq:
    enabled: true
    replicaCount: 3
    persistence:
      size: 20Gi

observability:
  jaeger:
    enabled: true
  prometheus:
    enabled: true
    retention: 30d
    storageSize: 50Gi
  grafana:
    enabled: true
```

---

## 7. Multi-Cloud Support

### 7.1 Abstraction Layers

To achieve true cloud-agnosticity, we use abstraction layers:

1. **Compute**: Kubernetes provides workload abstraction
2. **Storage**: CSI drivers for cloud-specific block storage
3. **Networking**: Cloud Controller Manager for load balancers
4. **DNS**: External-DNS with provider-agnostic configuration
5. **Secrets**: External Secrets Operator with pluggable backends

### 7.2 Cloud-Specific Services Mapping

| Generic Service | AWS | GCP | Azure | DigitalOcean | Linode |
|-----------------|-----|-----|-------|--------------|--------|
| **Kubernetes** | EKS | GKE | AKS | DOKS | LKE |
| **Block Storage** | EBS | Persistent Disk | Managed Disks | Volumes | Block Storage |
| **Object Storage** | S3 | GCS | Blob Storage | Spaces | Object Storage |
| **Load Balancer** | ALB/NLB | Cloud Load Balancing | Load Balancer | Load Balancer | NodeBalancer |
| **DNS** | Route 53 | Cloud DNS | Azure DNS | DNS | DNS Manager |
| **Database (Managed)** | RDS | Cloud SQL | Azure Database | Managed Databases | Managed Databases |

### 7.3 Migration Strategy Between Clouds

#### Data Migration Plan

1. **Application State**: Kubernetes manifests are cloud-agnostic (no changes needed)
2. **Database Migration**:
   - Use `pg_dump` for PostgreSQL → restore on new cloud
   - Or use streaming replication for zero-downtime migration
3. **Object Storage Migration**:
   - Use `rclone` or `s3cmd` to sync MinIO data between clouds
   - Update S3 endpoint URLs in application config
4. **DNS Cutover**: Update DNS records to new load balancer IP

#### Example Migration Workflow (DigitalOcean → AWS)

```bash
# 1. Provision new AWS infrastructure with Terraform
cd terraform/environments/production
terraform apply -var="cloud_provider=aws"

# 2. Deploy applications to new cluster
helm upgrade --install health-platform ./helm-charts/health-platform \
  --values values-production.yaml \
  --kube-context aws-prod

# 3. Migrate PostgreSQL data
pg_dump -h old-db.digitalocean.com -U postgres health_db | \
  psql -h new-db.aws.com -U postgres health_db

# 4. Sync MinIO data
rclone sync do-minio:health-data aws-s3:health-data --progress

# 5. Update DNS (gradual traffic shift)
# - Set low TTL (60s) on old DNS records
# - Create new records pointing to AWS load balancer
# - Monitor traffic shift
# - Decommission old infrastructure after 24 hours

# 6. Destroy old infrastructure
cd terraform/environments/production
terraform destroy -var="cloud_provider=digitalocean"
```

---

## 8. Security Architecture

### 8.1 Network Security

```yaml
# TLS Everywhere
- Ingress: TLS termination with cert-manager (Let's Encrypt)
- Service Mesh (optional): mTLS between services with Linkerd
- Database: TLS connections required
- Object Storage: HTTPS only

# Network Policies
- Default deny all ingress
- Explicit allow rules for service-to-service communication
- Egress restrictions to prevent data exfiltration
```

### 8.2 Secret Management

#### Option A: Sealed Secrets (Simplest)

```yaml
# Encrypt secrets at rest, commit to git
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: health-api-secrets
  namespace: health-platform-api
spec:
  encryptedData:
    POSTGRES_PASSWORD: AgBQ8... (encrypted)
    S3_SECRET_KEY: AgC7P... (encrypted)
```

#### Option B: External Secrets Operator (Cloud-Agnostic)

```yaml
# Fetch secrets from any backend (AWS Secrets Manager, GCP Secret Manager, Vault, etc.)
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: health-platform-system
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "health-platform"

---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: health-api-secrets
  namespace: health-platform-api
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: health-api-secrets
  data:
    - secretKey: POSTGRES_PASSWORD
      remoteRef:
        key: health-platform/postgres
        property: password
```

### 8.3 RBAC Configuration

```yaml
# Service accounts with minimal permissions
apiVersion: v1
kind: ServiceAccount
metadata:
  name: health-api
  namespace: health-platform-api

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: health-api
  namespace: health-platform-api
rules:
  - apiGroups: [""]
    resources: ["secrets", "configmaps"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: health-api
  namespace: health-platform-api
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: health-api
subjects:
  - kind: ServiceAccount
    name: health-api
    namespace: health-platform-api
```

### 8.4 Pod Security Standards

```yaml
# Enforce security policies with Pod Security Admission
apiVersion: v1
kind: Namespace
metadata:
  name: health-platform-api
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

---

## 9. Disaster Recovery

### 9.1 Backup Strategy

#### Database Backups (PostgreSQL)

```yaml
# Use Velero for Kubernetes-native backups
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: postgres-backup
  namespace: velero
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM UTC
  template:
    includedNamespaces:
      - health-platform-data
    includedResources:
      - persistentvolumeclaims
      - persistentvolumes
    labelSelector:
      matchLabels:
        app: postgresql
    ttl: 720h  # 30 days retention
```

#### Object Storage Backups (MinIO)

```yaml
# Use MinIO bucket replication to external S3-compatible storage
mc mirror --watch --remove \
  minio/health-data \
  s3-backup/health-data-backup
```

### 9.2 Disaster Recovery Plan

| Scenario | RTO (Recovery Time Objective) | RPO (Recovery Point Objective) | Recovery Steps |
|----------|-------------------------------|--------------------------------|----------------|
| Pod failure | < 1 minute | 0 (no data loss) | Kubernetes auto-restart |
| Node failure | < 5 minutes | 0 (no data loss) | Kubernetes reschedules pods |
| Database corruption | < 30 minutes | Last backup (1 day) | Restore from Velero backup |
| Cluster failure | < 2 hours | Last backup (1 day) | Provision new cluster, restore data |
| Region outage | < 4 hours | Last replication (1 hour) | Failover to standby cluster |

### 9.3 Multi-Region High Availability (Optional)

```yaml
# For mission-critical deployments
Primary Cluster (Region A):
  - Active traffic serving
  - Continuous PostgreSQL streaming replication to Region B
  - MinIO bucket replication to Region B

Standby Cluster (Region B):
  - Read-only PostgreSQL replica (can be promoted to primary)
  - MinIO mirror bucket
  - Can be activated in < 15 minutes with DNS failover
```

---

## 10. Migration Strategy

### 10.1 Phase 1: Local Development (Week 1-2)

**Goal**: Prove Kubernetes deployments work locally

```bash
# Use kind (Kubernetes in Docker) or minikube
kind create cluster --name health-platform-dev

# Deploy with Helm
helm install health-platform ./helm-charts/health-platform \
  --values values-dev.yaml

# Verify all services
kubectl get pods -A
kubectl port-forward svc/health-api 8001:8001
```

### 10.2 Phase 2: Cloud Provisioning (Week 3)

**Goal**: Provision production-like cluster with Terraform

```bash
# Choose cheapest provider for initial deployment
cd terraform/environments/production
terraform init
terraform plan -var="cloud_provider=digitalocean"
terraform apply
```

### 10.3 Phase 3: Application Migration (Week 4-5)

**Goal**: Migrate services from docker-compose to Kubernetes

**Migration Order** (dependency-based):
1. PostgreSQL, Redis, MinIO, RabbitMQ (infrastructure layer)
2. WebAuthn Stack (authentication)
3. Jaeger (observability)
4. Health API Service
5. ETL Narrative Engine

**Migration Checklist per Service**:
- [ ] Create Helm chart
- [ ] Configure environment variables via ConfigMaps/Secrets
- [ ] Set resource requests/limits
- [ ] Configure health checks
- [ ] Test connectivity to dependencies
- [ ] Set up ingress/service
- [ ] Verify monitoring/tracing
- [ ] Load test

### 10.4 Phase 4: Production Hardening (Week 6)

**Goal**: Production-ready deployment

- [ ] Enable autoscaling
- [ ] Configure backups (Velero)
- [ ] Set up monitoring alerts (Prometheus Alertmanager)
- [ ] Implement network policies
- [ ] Enable TLS everywhere
- [ ] Conduct disaster recovery drill
- [ ] Load testing and capacity planning
- [ ] Security audit (pod security standards, RBAC)

### 10.5 Phase 5: GitOps and CI/CD (Week 7-8)

**Goal**: Automated deployments

```yaml
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Define application
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: health-platform
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/health-platform
    targetRevision: main
    path: helm-charts/health-platform
    helm:
      valueFiles:
        - values-production.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: health-platform-api
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

---

## 11. Implementation Phases

### Phase 1: Infrastructure Setup (2 weeks)

**Deliverables**:
- Terraform modules for multi-cloud Kubernetes provisioning
- Provision DigitalOcean/Linode cluster for development
- Set up kubectl, Helm, Terraform tooling
- Configure DNS and wildcard TLS certificates

**Success Criteria**:
- `kubectl get nodes` shows healthy cluster
- Ingress controller routes traffic with TLS

### Phase 2: Helm Chart Development (3 weeks)

**Deliverables**:
- Helm charts for all services (WebAuthn, Health API, Infrastructure, Observability)
- Values files for dev/staging/production
- Secret management strategy (Sealed Secrets or External Secrets)

**Success Criteria**:
- `helm install` successfully deploys entire platform
- All pods are running and healthy
- Services can communicate via Kubernetes DNS

### Phase 3: Migration and Testing (2 weeks)

**Deliverables**:
- Migrate data from local docker-compose to Kubernetes
- Load testing with realistic traffic patterns
- Disaster recovery testing (backup/restore)

**Success Criteria**:
- All integration tests pass in Kubernetes environment
- API endpoints respond correctly
- WebAuthn authentication works
- File uploads succeed and trigger ETL pipeline

### Phase 4: Observability and Hardening (1 week)

**Deliverables**:
- Prometheus/Grafana dashboards for all services
- Jaeger distributed tracing integrated
- Logging aggregation with Loki
- Security policies (network policies, RBAC, pod security)

**Success Criteria**:
- Grafana shows real-time metrics for all services
- Jaeger traces show end-to-end request flow
- Security scan passes with no critical vulnerabilities

### Phase 5: Production Deployment (1 week)

**Deliverables**:
- Production cluster provisioned
- Production data migrated
- DNS cutover
- Monitoring alerts configured

**Success Criteria**:
- Production API accessible at `https://api.health-platform.example.com`
- Zero downtime during migration
- All health checks green
- Backups running automatically

### Phase 6: CI/CD and GitOps (1 week)

**Deliverables**:
- GitHub Actions workflows for Docker image builds
- ArgoCD application definitions
- Automated deployment pipeline

**Success Criteria**:
- Code push → automatic deployment to staging
- Manual approval gates for production
- Rollback capability tested

---

## 12. Cost Estimates

### 12.1 Minimal Production Deployment (DigitalOcean)

| Component | Specification | Monthly Cost |
|-----------|--------------|--------------|
| **DOKS Cluster** | 2x 2vCPU/4GB nodes + HA control plane | $48 |
| **Load Balancer** | 1x managed LB | $12 |
| **Block Storage** | 150GB SSD (PostgreSQL, Redis, RabbitMQ) | $15 |
| **Spaces (Object Storage)** | 250GB + 1TB transfer | $5 |
| **Backups** | Volume snapshots | $3 |
| **DNS** | Included | $0 |
| **Total** | | **$83/month** |

### 12.2 Scalable Production Deployment (DigitalOcean)

| Component | Specification | Monthly Cost |
|-----------|--------------|--------------|
| **DOKS Cluster** | 3x 4vCPU/8GB nodes (auto-scale 3-6) | $192 (base) + $192 (peak) |
| **Load Balancer** | 1x managed LB | $12 |
| **Block Storage** | 500GB SSD | $50 |
| **Spaces (Object Storage)** | 1TB + 5TB transfer | $15 |
| **Backups** | Volume snapshots | $10 |
| **Managed PostgreSQL** | 2x 4GB RAM (HA) | $120 |
| **Total (Base)** | | **$399/month** |
| **Total (Peak)** | | **$591/month** |

### 12.3 Enterprise Multi-Cloud Deployment (AWS)

| Component | Specification | Monthly Cost |
|-----------|--------------|--------------|
| **EKS Cluster** | Control plane | $73 |
| **EC2 Nodes** | 3x t3.large (2vCPU/8GB) reserved | $135 |
| **Spot Instances** | 3x t3.large (burstable workloads) | $27 (70% savings) |
| **Application Load Balancer** | 1x ALB | $23 |
| **EBS Volumes** | 500GB gp3 | $50 |
| **S3 Storage** | 1TB + requests | $25 |
| **RDS PostgreSQL** | db.t4g.large Multi-AZ | $180 |
| **ElastiCache Redis** | cache.t4g.small | $36 |
| **Total** | | **$549/month** |

---

## 13. Recommendations

### For Small-Scale Production (< 1000 users)

**Recommended Stack**:
- **Cloud Provider**: DigitalOcean DOKS or Linode LKE
- **Cluster Size**: 2-3 nodes (2 vCPU, 4GB RAM each)
- **Storage**: Kubernetes-native (no managed databases)
- **Estimated Cost**: $60-100/month

**Rationale**: Minimal overhead, simple management, easy scaling path

### For Medium-Scale Production (1000-10,000 users)

**Recommended Stack**:
- **Cloud Provider**: AWS, GCP, or Azure (depending on region requirements)
- **Cluster Size**: 3 nodes (4 vCPU, 8GB RAM) + spot instances for burstable workloads
- **Storage**: Managed databases (RDS PostgreSQL, ElastiCache Redis)
- **Estimated Cost**: $400-600/month

**Rationale**: Better reliability, managed services reduce operational burden, spot instances for cost savings

### For Enterprise/Multi-Region (> 10,000 users)

**Recommended Stack**:
- **Cloud Provider**: Multi-cloud with Terraform abstraction
- **Cluster Size**: Multiple regions with active-active or active-standby
- **Storage**: Managed databases with cross-region replication
- **Estimated Cost**: $2,000-5,000/month

**Rationale**: High availability, disaster recovery, compliance (data residency)

---

## 14. Next Steps

1. **Review and Approve Specification**: Stakeholder sign-off on architecture and cost estimates
2. **Choose Initial Cloud Provider**: Based on budget and technical requirements
3. **Set Up Terraform Modules**: Provision first Kubernetes cluster
4. **Develop Helm Charts**: Containerize and Helmify all services
5. **Test Migration**: Validate docker-compose → Kubernetes migration in dev environment
6. **Production Deployment**: Execute phased rollout plan
7. **Continuous Optimization**: Monitor costs, right-size resources, implement GitOps

---

## 15. Appendix

### A. Glossary

- **HPA**: Horizontal Pod Autoscaler (scales pods based on metrics)
- **PVC**: PersistentVolumeClaim (storage request)
- **CSI**: Container Storage Interface (plugin for storage providers)
- **Ingress**: Kubernetes resource for HTTP/HTTPS routing
- **StatefulSet**: Kubernetes workload for stateful applications (databases)

### B. References

- [Kubernetes Official Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [Terraform Kubernetes Provider](https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs)
- [DigitalOcean Kubernetes](https://www.digitalocean.com/products/kubernetes)
- [Linode Kubernetes Engine](https://www.linode.com/products/kubernetes/)
- [ArgoCD GitOps](https://argo-cd.readthedocs.io/)

### C. Example Commands Reference

```bash
# Terraform
terraform init
terraform plan -var-file=production.tfvars
terraform apply -auto-approve

# Helm
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install health-platform ./helm-charts/health-platform -f values-production.yaml
helm upgrade --install health-platform ./helm-charts/health-platform
helm rollback health-platform 1

# kubectl
kubectl get pods -n health-platform-api
kubectl logs -f deployment/health-api -n health-platform-api
kubectl port-forward svc/health-api 8001:8001 -n health-platform-api
kubectl apply -f manifests/

# Cluster Management
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
kubectl cordon <node>
kubectl uncordon <node>

# Debugging
kubectl describe pod <pod-name>
kubectl exec -it <pod-name> -- /bin/bash
kubectl top nodes
kubectl top pods -A
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-18 | Claude (AI Assistant) | Initial specification |

---

**End of Specification**
