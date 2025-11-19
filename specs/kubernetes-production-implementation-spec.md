# Kubernetes Production Deployment - Implementation Specification
## Health Data AI Platform on Oracle Cloud Infrastructure

**Version:** 1.0
**Created:** 2025-01-19
**Status:** Ready for Implementation
**Target Platform:** Oracle Cloud Infrastructure (OKE) - Always Free Tier
**Cloud Strategy:** Oracle-first, cloud-agnostic design for future portability

---

## Executive Summary

This specification defines the **production-ready Kubernetes deployment** of the Health Data AI Platform using Oracle Cloud Infrastructure's Always Free tier, providing a **$0/month production environment** with professional-grade architecture.

### Key Decisions

1. **Primary Platform**: Oracle Kubernetes Engine (OKE) on Always Free tier
2. **Cloud Strategy**: Cloud-agnostic design (Terraform modules, Helm charts) with Oracle as initial target
3. **Cost**: $0/month for infrastructure (within Always Free limits)
4. **Sustainability**: 100% renewable energy (EU regions)
5. **Scalability**: Design supports migration to paid tiers or other clouds when needed

### Resources Available (Oracle Always Free)

```yaml
Compute:
  - 4 ARM vCPUs (Ampere A1)
  - 24 GB RAM
  - Configurable across 1-4 instances

Storage:
  - 200 GB block storage (boot volumes)
  - 20 GB object storage (OCI Object Storage)

Networking:
  - 1 Flexible Load Balancer (10 Mbps)
  - 10 TB outbound data transfer/month

Kubernetes:
  - OKE Basic Cluster (FREE control plane)
  - Managed Kubernetes service
```

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Implementation Modules](#2-implementation-modules)
3. [Parallel Development Strategy](#3-parallel-development-strategy)
4. [Resource Allocation](#4-resource-allocation)
5. [Technology Stack](#5-technology-stack)
6. [Security Architecture](#6-security-architecture)
7. [Observability Strategy](#7-observability-strategy)
8. [Disaster Recovery](#8-disaster-recovery)
9. [Migration & Scaling Strategy](#9-migration--scaling-strategy)
10. [Success Criteria](#10-success-criteria)

---

## 1. Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Oracle Cloud Infrastructure (OCI)                              │
│  Region: eu-amsterdam-1 (100% renewable energy)                 │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  OKE Basic Cluster (FREE Control Plane)                   │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Ingress Layer                                        │ │ │
│  │  │  - NGINX Ingress Controller                          │ │ │
│  │  │  - cert-manager (Let's Encrypt SSL)                  │ │ │
│  │  │  - Flexible Load Balancer (FREE)                     │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Application Layer (Deployments)                      │ │ │
│  │  │                                                        │ │ │
│  │  │  ┌────────────────┐  ┌─────────────────────────────┐ │ │ │
│  │  │  │ WebAuthn Stack │  │  Health Services            │ │ │ │
│  │  │  │ - Envoy GW     │  │  - Health API               │ │ │ │
│  │  │  │ - WebAuthn Svr │  │  - ETL Narrative Engine     │ │ │ │
│  │  │  └────────────────┘  └─────────────────────────────┘ │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Data Layer (StatefulSets)                            │ │ │
│  │  │                                                        │ │ │
│  │  │  ┌───────────┐  ┌────────┐  ┌─────────┐  ┌────────┐ │ │ │
│  │  │  │PostgreSQL │  │ Redis  │  │ MinIO   │  │RabbitMQ│ │ │ │
│  │  │  │(2 instances)│ │(2 inst)│  │(Data Lk)│  │(MQ)    │ │ │ │
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
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Storage (Always Free Tier)                               │ │
│  │  - 200 GB Block Volumes (PersistentVolumes)               │ │
│  │  - 20 GB Object Storage (Backups)                         │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Node Architecture

```yaml
Node Pool Configuration (4 vCPU, 24 GB RAM total):

Node 1 - System & Observability (VM.Standard.A1.Flex):
  Allocation: 2 OCPU, 12 GB RAM
  Purpose: System services, monitoring, ingress
  Workloads:
    - NGINX Ingress Controller
    - cert-manager
    - Prometheus
    - Grafana
    - Jaeger
    - Loki
    - System pods (CoreDNS, etc.)

Node 2 - Application Primary (VM.Standard.A1.Flex):
  Allocation: 1 OCPU, 6 GB RAM
  Purpose: Application services (primary)
  Workloads:
    - Health API (1 replica)
    - WebAuthn Server (1 replica)
    - Envoy Gateway (1 replica)
    - PostgreSQL (health-data, primary)
    - Redis (health-data)

Node 3 - Application Secondary (VM.Standard.A1.Flex):
  Allocation: 1 OCPU, 6 GB RAM
  Purpose: Application services (secondary), data services
  Workloads:
    - Health API (1 replica)
    - WebAuthn Server (1 replica)
    - PostgreSQL (webauthn-auth)
    - Redis (webauthn-sessions)
    - MinIO (data lake)
    - RabbitMQ (message queue)
    - ETL Narrative Engine
```

### 1.3 Namespace Strategy

```yaml
Namespaces (Isolation by Function):
  - health-system           # Ingress, cert-manager, sealed-secrets
  - health-auth             # WebAuthn stack
  - health-api              # Health API service
  - health-etl              # ETL Narrative Engine
  - health-data             # PostgreSQL, Redis, MinIO, RabbitMQ
  - health-observability    # Prometheus, Grafana, Jaeger, Loki
```

---

## 2. Implementation Modules

The implementation is divided into **8 parallel modules** that can be developed concurrently:

| Module | Description | Dependencies | Estimated Time | Implementation File |
|--------|-------------|--------------|----------------|---------------------|
| **Module 1** | Terraform Infrastructure | None | 1 week | `terraform-infrastructure-module.md` |
| **Module 2** | Helm Charts - Infrastructure | None | 1 week | `helm-infrastructure-module.md` |
| **Module 3** | Helm Charts - WebAuthn | None | 1 week | `helm-webauthn-module.md` |
| **Module 4** | Helm Charts - Health Services | None | 1 week | `helm-health-services-module.md` |
| **Module 5** | Observability Stack | None | 1 week | `observability-module.md` |
| **Module 6** | Security & RBAC | Module 1 | 3 days | `security-module.md` |
| **Module 7** | GitOps & CI/CD | Modules 1-4 | 1 week | `gitops-cicd-module.md` |
| **Module 8** | Disaster Recovery | Modules 1-4 | 3 days | `disaster-recovery-module.md` |

**Total Timeline**: 4-6 weeks (with parallelization)

---

## 3. Parallel Development Strategy

### 3.1 Week 1-2: Foundation (Parallel Tracks)

```yaml
Track A: Infrastructure (Developer A)
  Module 1: Terraform Infrastructure
    - Oracle Cloud provider configuration
    - OKE cluster provisioning
    - VCN and networking setup
    - Block storage configuration
    - Object storage bucket creation
    - Load balancer provisioning

Track B: Helm Charts - Data Layer (Developer B)
  Module 2: Infrastructure Helm Charts
    - PostgreSQL StatefulSet (Bitnami chart wrapper)
    - Redis StatefulSet (Bitnami chart wrapper)
    - MinIO StatefulSet
    - RabbitMQ StatefulSet
    - PersistentVolumeClaim templates

Track C: Helm Charts - Auth (Developer C)
  Module 3: WebAuthn Stack Helm Charts
    - WebAuthn Server deployment
    - Envoy Gateway deployment
    - ConfigMaps and Secrets
    - Service definitions

Track D: Helm Charts - Health Services (Developer D)
  Module 4: Health Services Helm Charts
    - Health API deployment
    - ETL Narrative Engine deployment
    - Ingress configurations
    - HorizontalPodAutoscaler definitions

Track E: Observability (Developer E)
  Module 5: Observability Stack
    - Prometheus + Operator
    - Grafana deployment
    - Jaeger deployment
    - Loki + Promtail
    - Dashboard configurations
```

### 3.2 Week 3-4: Integration & Security

```yaml
Track A+B+C+D: Integration Testing
  - Combine all Helm charts into umbrella chart
  - Test service-to-service communication
  - Validate resource consumption within free tier
  - Load testing

Track E: Security Hardening (Module 6)
  - NetworkPolicies for service isolation
  - RBAC configuration
  - Pod Security Standards
  - Sealed Secrets setup
  - Security scanning
```

### 3.3 Week 5-6: Production Readiness

```yaml
Track A: GitOps & CI/CD (Module 7)
  - ArgoCD installation and configuration
  - GitHub Actions workflows
  - Automated testing pipeline
  - Deployment automation

Track B: Disaster Recovery (Module 8)
  - Velero backup configuration
  - Database backup strategies
  - Restore testing
  - Runbook documentation

Track C: Final Testing & Documentation
  - End-to-end testing
  - Performance optimization
  - Cost monitoring setup
  - Operations documentation
```

---

## 4. Resource Allocation

### 4.1 CPU Allocation (4 vCPUs total)

```yaml
Node 1 (2 vCPU - System & Observability):
  NGINX Ingress:        200m CPU (request), 500m (limit)
  cert-manager:         100m CPU (request), 200m (limit)
  Prometheus:           500m CPU (request), 1000m (limit)
  Grafana:              200m CPU (request), 500m (limit)
  Jaeger:               300m CPU (request), 500m (limit)
  Loki:                 200m CPU (request), 400m (limit)
  System Pods:          500m CPU (request), 900m (limit)
  ---
  Total Request:        2000m (2 vCPU) ✅
  Total Limit:          4000m (allows bursting)

Node 2 (1 vCPU - App Primary):
  Health API:           250m CPU (request), 500m (limit)
  WebAuthn Server:      250m CPU (request), 500m (limit)
  Envoy Gateway:        100m CPU (request), 200m (limit)
  PostgreSQL (health):  300m CPU (request), 500m (limit)
  Redis (health):       100m CPU (request), 200m (limit)
  ---
  Total Request:        1000m (1 vCPU) ✅
  Total Limit:          1900m (allows bursting)

Node 3 (1 vCPU - App Secondary + Data):
  Health API:           250m CPU (request), 500m (limit)
  WebAuthn Server:      200m CPU (request), 400m (limit)
  PostgreSQL (auth):    150m CPU (request), 300m (limit)
  Redis (auth):         100m CPU (request), 200m (limit)
  MinIO:                200m CPU (request), 400m (limit)
  RabbitMQ:             300m CPU (request), 500m (limit)
  ETL Engine:           200m CPU (request), 700m (limit)
  ---
  Total Request:        1000m (1 vCPU) ✅
  Total Limit:          3000m (allows bursting)
```

### 4.2 Memory Allocation (24 GB total)

```yaml
Node 1 (12 GB - System & Observability):
  NGINX Ingress:        256 Mi (request), 512 Mi (limit)
  cert-manager:         128 Mi (request), 256 Mi (limit)
  Prometheus:           2 Gi (request), 4 Gi (limit)
  Grafana:              512 Mi (request), 1 Gi (limit)
  Jaeger:               512 Mi (request), 1 Gi (limit)
  Loki:                 512 Mi (request), 1 Gi (limit)
  System Pods:          1 Gi (request), 2 Gi (limit)
  ---
  Total Request:        ~5 Gi ✅
  Total Limit:          ~10 Gi

Node 2 (6 GB - App Primary):
  Health API:           256 Mi (request), 512 Mi (limit)
  WebAuthn Server:      512 Mi (request), 1 Gi (limit)
  Envoy Gateway:        128 Mi (request), 256 Mi (limit)
  PostgreSQL (health):  1 Gi (request), 2 Gi (limit)
  Redis (health):       256 Mi (request), 512 Mi (limit)
  ---
  Total Request:        ~2.1 Gi ✅
  Total Limit:          ~4.2 Gi

Node 3 (6 GB - App Secondary + Data):
  Health API:           256 Mi (request), 512 Mi (limit)
  WebAuthn Server:      512 Mi (request), 1 Gi (limit)
  PostgreSQL (auth):    512 Mi (request), 1 Gi (limit)
  Redis (auth):         256 Mi (request), 512 Mi (limit)
  MinIO:                512 Mi (request), 1 Gi (limit)
  RabbitMQ:             512 Mi (request), 1 Gi (limit)
  ETL Engine:           512 Mi (request), 2 Gi (limit)
  ---
  Total Request:        ~3 Gi ✅
  Total Limit:          ~7 Gi
```

### 4.3 Storage Allocation (200 GB block, 20 GB object)

```yaml
Block Volumes (200 GB total):
  PostgreSQL (health-data):     60 GB (primary data)
  PostgreSQL (webauthn-auth):   20 GB (credentials)
  MinIO (data lake):            80 GB (raw health data)
  RabbitMQ (message persistence): 15 GB
  Prometheus (metrics):         20 GB (30-day retention)
  Loki (logs):                  5 GB (7-day retention)
  ---
  Total:                        200 GB ✅

Object Storage (20 GB, OCI Object Storage):
  Database Backups:             12 GB
  Configuration Backups:        3 GB
  Static Assets:                5 GB
  ---
  Total:                        20 GB ✅

Future Expansion (When exceeding free tier):
  - Add paid block volumes: $0.0255/GB/month
  - Expand object storage: $0.0255/GB/month
  - Example: +100GB block = $2.55/month
```

---

## 5. Technology Stack

### 5.1 Infrastructure as Code

```yaml
Terraform (v1.6+):
  Purpose: Provision OKE cluster and OCI resources
  Modules:
    - oracle-oke (cluster provisioning)
    - networking (VCN, subnets, security lists)
    - storage (block volumes, object storage buckets)
    - dns (optional, for custom domain)

  State Management:
    Backend: OCI Object Storage (free tier)
    Locking: Not required for single developer
    Location: oci://health-platform-terraform-state
```

### 5.2 Kubernetes Package Management

```yaml
Helm (v3.13+):
  Purpose: Application deployment and configuration management

  Chart Structure:
    health-platform/              # Umbrella chart
    ├── charts/
    │   ├── infrastructure/       # PostgreSQL, Redis, MinIO, RabbitMQ
    │   ├── webauthn-stack/       # WebAuthn services
    │   ├── health-api/           # Health API service
    │   ├── etl-engine/           # ETL Narrative Engine
    │   └── observability/        # Monitoring stack
    ├── values.yaml               # Default values
    ├── values-dev.yaml           # Development overrides
    └── values-production.yaml    # Production overrides

  Dependencies (Bitnami Charts):
    - postgresql: v13.2.24
    - redis: v18.4.0
    - minio: v12.11.3
    - rabbitmq: v12.9.1
```

### 5.3 GitOps & CI/CD

```yaml
ArgoCD (v2.9+):
  Purpose: Continuous deployment from Git
  Deployment: In-cluster (health-system namespace)
  Sync Policy: Automated with pruning

GitHub Actions:
  Purpose: CI/CD pipeline
  Workflows:
    - Docker image builds
    - Helm chart linting
    - Integration testing
    - Deployment to staging/production
```

### 5.4 Observability

```yaml
Prometheus (v2.48+):
  Purpose: Metrics collection and alerting
  Deployment: kube-prometheus-stack (Helm)
  Retention: 30 days
  Storage: 20 GB PVC

Grafana (v10.2+):
  Purpose: Metrics visualization
  Dashboards: Pre-configured for K8s, applications

Jaeger (v1.52+):
  Purpose: Distributed tracing
  Already in use: Shared with docker-compose stack

Loki (v2.9+):
  Purpose: Log aggregation
  Retention: 7 days
  Storage: 5 GB PVC
```

### 5.5 Security

```yaml
cert-manager (v1.13+):
  Purpose: Automated SSL/TLS certificate management
  Issuer: Let's Encrypt (production)

Sealed Secrets (v0.24+):
  Purpose: Encrypt secrets in Git
  Controller: In-cluster decryption

OCI IAM:
  Purpose: Cloud-level access control
  Policies: Principle of least privilege

Kubernetes RBAC:
  Purpose: In-cluster access control
  ServiceAccounts: Per-service with minimal permissions
```

---

## 6. Security Architecture

### 6.1 Network Security

```yaml
Network Policies (Calico/OCI CNI):
  Default: Deny all ingress, allow all egress

  Explicit Allow Rules:
    Ingress Controller → Health API, WebAuthn Gateway
    Health API → PostgreSQL (health), Redis (health), MinIO, RabbitMQ
    WebAuthn → PostgreSQL (auth), Redis (auth)
    ETL Engine → PostgreSQL (health), MinIO, RabbitMQ
    All Services → Jaeger (tracing)
    Prometheus → All Services (metrics scraping)

Security Lists (OCI VCN):
  Ingress:
    - Port 443 (HTTPS) from Internet
    - Port 6443 (K8s API) from trusted IPs only
  Egress:
    - Allow all (required for package downloads, etc.)
```

### 6.2 Secret Management

```yaml
Sealed Secrets Strategy:
  1. Developer encrypts secrets locally with kubeseal
  2. Encrypted SealedSecret committed to Git
  3. Controller in cluster decrypts and creates Secret
  4. Pods consume Secret as environment variables or volumes

  Secrets to Manage:
    - Database passwords (PostgreSQL, Redis)
    - S3 credentials (MinIO access/secret keys)
    - RabbitMQ credentials
    - JWT signing keys (WebAuthn)
    - TLS certificates (cert-manager automates this)
    - OCI API keys (for Terraform)

Alternative (Future):
  - OCI Vault (managed secrets service)
  - External Secrets Operator with OCI Vault backend
```

### 6.3 Pod Security

```yaml
Pod Security Standards:
  Enforcement Level: restricted (most secure)

  Applied to Namespaces:
    - health-api
    - health-auth
    - health-etl

  Requirements:
    - Run as non-root user
    - Read-only root filesystem (where possible)
    - Drop all capabilities
    - No privilege escalation
    - Seccomp profile: RuntimeDefault
```

### 6.4 RBAC Configuration

```yaml
ServiceAccounts (Per Service):
  health-api-sa:
    Permissions:
      - Get/List Secrets in health-api namespace
      - Get/List ConfigMaps in health-api namespace

  webauthn-sa:
    Permissions:
      - Get/List Secrets in health-auth namespace
      - Get/List ConfigMaps in health-auth namespace

  prometheus-sa:
    Permissions:
      - Get/List Pods, Services (all namespaces)
      - Get metrics endpoints

ClusterRoles (Global):
  view: Read-only access (for developers)
  admin: Full access (for operators)
```

---

## 7. Observability Strategy

### 7.1 Metrics (Prometheus)

```yaml
Prometheus Configuration:
  Scrape Interval: 15s
  Evaluation Interval: 15s
  Retention: 30 days

  ServiceMonitors (Auto-discovery):
    - health-api metrics endpoint (/metrics)
    - webauthn-server metrics
    - postgresql-exporter
    - redis-exporter
    - minio metrics
    - rabbitmq metrics
    - etl-engine metrics

  Alerting Rules:
    - High CPU usage (>80% for 5m)
    - High memory usage (>85% for 5m)
    - Pod restart loops
    - Persistent volume near capacity (>80%)
    - Service downtime (>1m)
    - Database connection failures
```

### 7.2 Dashboards (Grafana)

```yaml
Pre-configured Dashboards:
  1. Kubernetes Cluster Overview
     - Node CPU/Memory/Disk usage
     - Pod status and distribution
     - Network I/O

  2. Application Performance
     - Request rate, latency, errors (RED metrics)
     - Database query performance
     - Cache hit rates

  3. Infrastructure Health
     - PostgreSQL performance
     - Redis performance
     - MinIO metrics
     - RabbitMQ queue depth

  4. Cost Monitoring
     - CPU/Memory utilization %
     - Storage consumption
     - Network bandwidth usage

  5. Security Dashboard
     - Failed authentication attempts
     - Network policy denials
     - Certificate expiry warnings
```

### 7.3 Tracing (Jaeger)

```yaml
Jaeger Configuration:
  Already Deployed: Yes (from webauthn-stack)
  Integration: OpenTelemetry SDK in all services

  Traces to Capture:
    - HTTP request end-to-end (Ingress → API → Database)
    - WebAuthn authentication flow
    - ETL pipeline execution
    - Message queue processing

  Sampling Strategy:
    - Development: 100% (all traces)
    - Production: 10% (adaptive sampling)
```

### 7.4 Logging (Loki)

```yaml
Loki + Promtail Configuration:
  Log Aggregation: Centralized in Loki
  Log Shipping: Promtail DaemonSet on all nodes
  Retention: 7 days

  Structured Logging:
    - JSON format
    - Fields: timestamp, level, service, trace_id, message

  Log Sources:
    - Application logs (stdout/stderr)
    - Kubernetes events
    - Ingress access logs
    - Database slow query logs
```

---

## 8. Disaster Recovery

### 8.1 Backup Strategy

```yaml
Velero (Kubernetes Backup):
  Purpose: Backup Kubernetes resources and persistent volumes
  Schedule: Daily at 2 AM UTC
  Retention: 30 days
  Storage: OCI Object Storage (free tier)

  Backup Scope:
    - All namespaces (except kube-system)
    - Persistent volumes (PostgreSQL, MinIO, etc.)
    - Cluster resources (RBAC, NetworkPolicies)

Database Backups (PostgreSQL):
  Method: pg_dump via CronJob
  Schedule: Daily at 3 AM UTC
  Retention: 7 daily, 4 weekly
  Storage: OCI Object Storage
  Encryption: At rest (OCI native)

  Backup Script:
    - Dump database to compressed file
    - Upload to object storage
    - Verify backup integrity
    - Rotate old backups
```

### 8.2 Disaster Recovery Plan

```yaml
Recovery Time Objective (RTO): 2 hours
Recovery Point Objective (RPO): 24 hours

Disaster Scenarios:

1. Pod Failure
   RTO: < 1 minute
   Action: Kubernetes auto-restart

2. Node Failure
   RTO: < 5 minutes
   Action: Kubernetes reschedules pods to healthy nodes

3. Database Corruption
   RTO: 30 minutes
   Action: Restore from latest pg_dump backup
   Steps:
     - Scale down application pods
     - Drop corrupted database
     - Restore from backup
     - Verify data integrity
     - Scale up application pods

4. Cluster Failure
   RTO: 2 hours
   Action: Provision new cluster, restore from Velero
   Steps:
     - Provision new OKE cluster with Terraform
     - Install Velero
     - Restore from latest backup
     - Verify all services
     - Update DNS records

5. Region Outage (Advanced)
   RTO: 4 hours
   Action: Failover to different region (future enhancement)
```

### 8.3 Testing Schedule

```yaml
Monthly DR Drills:
  Week 1: Test database restore
  Week 2: Test Velero cluster restore
  Week 3: Test full cluster rebuild from Terraform
  Week 4: Test failover procedures (when multi-region)

Documentation:
  - Runbook for each disaster scenario
  - Contact information for on-call
  - Escalation procedures
```

---

## 9. Migration & Scaling Strategy

### 9.1 Migration from Docker Compose

```yaml
Phase 1: Preparation (Week 1)
  ✅ Provision OKE cluster with Terraform
  ✅ Deploy Helm charts (empty, no data)
  ✅ Verify all services start successfully
  ✅ Test service-to-service communication

Phase 2: Data Migration (Week 2)
  ✅ Export data from local PostgreSQL (pg_dump)
  ✅ Export data from local MinIO (mc mirror)
  ✅ Import to Kubernetes PostgreSQL
  ✅ Import to Kubernetes MinIO
  ✅ Verify data integrity

Phase 3: Traffic Cutover (Week 3)
  ✅ Run parallel (docker-compose + K8s) for 1 week
  ✅ Test all functionality on K8s
  ✅ Update DNS to point to K8s ingress
  ✅ Monitor for issues
  ✅ Decommission docker-compose stack

Phase 4: Optimization (Week 4)
  ✅ Fine-tune resource requests/limits
  ✅ Optimize database queries
  ✅ Configure autoscaling
  ✅ Document operations
```

### 9.2 Scaling Strategy

```yaml
When to Scale Beyond Always Free:

Trigger 1: CPU Utilization > 70% sustained
  Action: Add 1 paid ARM node (2 vCPU, 8GB = ~$15/month)

Trigger 2: Memory Utilization > 80% sustained
  Action: Add 1 paid ARM node with more memory

Trigger 3: Storage > 180 GB
  Action: Add paid block volumes ($0.0255/GB/month)

Trigger 4: Bandwidth > 8 TB/month
  Action: Upgrade load balancer or add CDN

Trigger 5: Need for HA / Multi-region
  Action: Deploy secondary cluster in different region
  Cost: ~$50-100/month (paid Oracle resources)

Scaling Options:

Option A: Stay on Oracle (Scale Up)
  Cost: $15-50/month for additional ARM nodes
  Benefit: Cheapest, familiar platform

Option B: Add GCP (Multi-Cloud)
  Oracle: Free tier for dev/staging
  GCP: Paid production cluster (europe-north1, Finland)
  Cost: ~$100/month for GCP production
  Benefit: Best carbon footprint, geographic diversity

Option C: Hybrid (Oracle + Hetzner)
  Oracle: Free tier for dev/staging
  Hetzner: Dedicated k3s cluster for production
  Cost: €20-40/month (~$24-48)
  Benefit: Great performance/cost ratio
```

---

## 10. Success Criteria

### 10.1 Technical Criteria

```yaml
Infrastructure:
  ✅ OKE cluster provisioned and accessible
  ✅ All nodes healthy and within resource limits
  ✅ Ingress controller routing traffic with SSL
  ✅ DNS configured and resolving correctly

Application:
  ✅ All pods running and healthy (0 restarts)
  ✅ Health API responds to requests < 200ms
  ✅ WebAuthn authentication functional
  ✅ ETL pipeline processes sample data
  ✅ All integration tests pass in K8s environment

Observability:
  ✅ Prometheus scraping all targets
  ✅ Grafana dashboards displaying metrics
  ✅ Jaeger showing distributed traces
  ✅ Loki aggregating logs from all services
  ✅ Alerts configured and tested

Security:
  ✅ Network policies enforced
  ✅ Pod security standards applied
  ✅ RBAC configured correctly
  ✅ Secrets encrypted with Sealed Secrets
  ✅ SSL certificates auto-renewing

Reliability:
  ✅ Database backups running daily
  ✅ Velero backups successful
  ✅ DR restore tested successfully
  ✅ No single point of failure (except free tier limits)
```

### 10.2 Operational Criteria

```yaml
Cost:
  ✅ Monthly cost: $0 (within Always Free tier)
  ✅ Cost monitoring dashboard active
  ✅ Alerts for approaching free tier limits

Performance:
  ✅ CPU utilization: 50-70% average (good efficiency)
  ✅ Memory utilization: 60-75% average
  ✅ Storage utilization: < 80%
  ✅ API latency: p95 < 500ms, p99 < 1s

Sustainability:
  ✅ Deployed to 100% renewable energy region (EU)
  ✅ Resource utilization optimized (no waste)
  ✅ Carbon footprint tracked and documented

Documentation:
  ✅ Architecture diagrams updated
  ✅ Runbooks for common operations
  ✅ Disaster recovery procedures documented
  ✅ Onboarding guide for new developers
```

### 10.3 Career Development Criteria

```yaml
Portfolio Value:
  ✅ Production Kubernetes deployment demonstrated
  ✅ Multi-service orchestration with Helm
  ✅ Infrastructure as Code with Terraform
  ✅ GitOps workflow implemented
  ✅ Observability stack configured
  ✅ Security best practices applied
  ✅ Cost optimization demonstrated ($0/month production)
  ✅ Blog post written: "Migrating to Production Kubernetes on Oracle's Free Tier"

Skills Acquired:
  ✅ Kubernetes administration
  ✅ Helm chart development
  ✅ Terraform infrastructure provisioning
  ✅ ArgoCD GitOps workflows
  ✅ Prometheus/Grafana monitoring
  ✅ Security hardening (RBAC, NetworkPolicies)
  ✅ Disaster recovery planning
```

---

## 11. Next Steps

### 11.1 Immediate Actions (This Week)

1. **Review and approve this specification**
2. **Set up Oracle Cloud account** (if not already done)
3. **Assign implementation modules** to team members (or solo schedule)
4. **Read detailed implementation guides** (separate module files)
5. **Set up development environment** (Terraform, Helm, kubectl)

### 11.2 Implementation Guides

Detailed implementation guides for each module:

- `terraform-infrastructure-module.md` - Complete Terraform setup for OKE
- `helm-infrastructure-module.md` - PostgreSQL, Redis, MinIO, RabbitMQ charts
- `helm-webauthn-module.md` - WebAuthn stack Helm chart
- `helm-health-services-module.md` - Health API and ETL Engine charts
- `observability-module.md` - Prometheus, Grafana, Jaeger, Loki setup
- `security-module.md` - RBAC, NetworkPolicies, Sealed Secrets
- `gitops-cicd-module.md` - ArgoCD and GitHub Actions setup
- `disaster-recovery-module.md` - Velero and backup procedures

### 11.3 Communication

- **Status Updates**: Weekly (or as milestones completed)
- **Issue Tracking**: GitHub Issues for each module
- **Documentation**: All changes documented in respective module files
- **Code Reviews**: Required for all Terraform and Helm changes

---

## 12. Appendix

### A. Glossary

- **OKE**: Oracle Kubernetes Engine (managed Kubernetes service)
- **OCPU**: Oracle Compute Unit (1 OCPU = 2 vCPUs for Intel/AMD, 1 vCPU for ARM)
- **VCN**: Virtual Cloud Network (Oracle's VPC equivalent)
- **PVC**: PersistentVolumeClaim (Kubernetes storage request)
- **HPA**: HorizontalPodAutoscaler (automatic pod scaling)
- **StatefulSet**: Kubernetes workload for stateful applications
- **SealedSecret**: Encrypted secret that can be stored in Git

### B. References

- [Oracle Cloud Always Free Services](https://www.oracle.com/cloud/free/)
- [Oracle Kubernetes Engine (OKE) Documentation](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
- [Terraform OCI Provider](https://registry.terraform.io/providers/oracle/oci/latest/docs)
- [Helm Documentation](https://helm.sh/docs/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)

### C. Oracle Cloud Regions (100% Renewable)

```yaml
European Regions (100% Renewable Energy):
  - eu-amsterdam-1 (Netherlands) - RECOMMENDED
  - eu-frankfurt-1 (Germany)
  - uk-london-1 (United Kingdom)

Selection Criteria:
  - eu-amsterdam-1: Good latency to US/EU, 100% renewable
  - Avoid: Non-EU regions if sustainability is priority
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-19 | Claude (AI Assistant) | Initial production implementation specification |

---

**END OF MAIN SPECIFICATION**

**Next**: Review detailed implementation modules for parallel development.
