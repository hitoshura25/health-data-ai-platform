# Disaster Recovery Runbook

## Health Data AI Platform - Kubernetes Deployment

**Version**: 1.0.0
**Last Updated**: 2025-01-20
**Target Infrastructure**: Oracle Cloud Always Free Tier

---

## Table of Contents

1. [Overview](#overview)
2. [Backup Strategy](#backup-strategy)
3. [Recovery Time & Point Objectives](#recovery-time--point-objectives)
4. [Disaster Scenarios](#disaster-scenarios)
5. [Step-by-Step Recovery Procedures](#step-by-step-recovery-procedures)
6. [Database Recovery](#database-recovery)
7. [Backup Verification](#backup-verification)
8. [Testing & Drills](#testing--drills)
9. [Monitoring & Alerts](#monitoring--alerts)
10. [Contact Information](#contact-information)

---

## Overview

This document provides comprehensive disaster recovery procedures for the Health Data AI Platform deployed on Oracle Kubernetes Engine (OKE). The platform uses Velero for Kubernetes resource backups and custom CronJobs for database backups, all stored in OCI Object Storage.

### Architecture Components

- **Kubernetes Cluster**: OKE on Oracle Cloud (Always Free tier)
- **Backup Solution**: Velero + OCI Object Storage (S3-compatible)
- **Databases**: PostgreSQL (health-data, webauthn-auth)
- **Data Lake**: MinIO (S3-compatible object storage)
- **Message Queue**: RabbitMQ
- **Observability**: Jaeger, Prometheus, Grafana

### Backup Storage Locations

- **Velero Backups**: `oci://health-platform-velero-backups/velero/`
- **Database Backups**: `oci://health-platform-db-backups/`
- **MinIO Backups**: `oci://health-platform-minio-backups/`

---

## Backup Strategy

### Automated Backup Schedules

| Backup Type | Frequency | Retention | Description |
|-------------|-----------|-----------|-------------|
| **Full Cluster** | Daily at 2 AM UTC | 30 days | All Kubernetes resources + PVs |
| **Health Data Namespace** | Every 6 hours | 7 days | Critical health-data namespace |
| **Config Backup** | Every hour | 7 days | ConfigMaps, Secrets, ServiceAccounts |
| **PostgreSQL (health-data)** | Daily at 3 AM UTC | 7 days | pg_dump with compression |
| **PostgreSQL (webauthn-auth)** | Daily at 3 AM UTC | 7 days | pg_dump with compression |
| **MinIO Buckets** | Daily at 4 AM UTC | 7 days | Incremental sync to OCI |
| **RabbitMQ Definitions** | Daily at 5 AM UTC | 7 days | Queue/exchange configurations |

### Backup Components

#### Velero (Kubernetes Resources)
- All namespaces: `health-api`, `health-auth`, `health-etl`, `health-data`, `health-observability`
- Cluster-scoped resources: StorageClasses, PersistentVolumes, etc.
- PersistentVolume snapshots using restic
- Excludes: Events, temporary pods

#### Database Backups
- **Format**: PostgreSQL custom format with gzip compression
- **Method**: `pg_dump --format=custom | gzip`
- **Upload**: OCI Object Storage via pre-authenticated requests
- **Encryption**: OCI bucket-level encryption

#### MinIO Backups
- **Method**: `mc mirror` for incremental sync
- **Buckets**: raw-health-data, processed-data, clinical-narratives, model-artifacts
- **Destination**: OCI Object Storage (separate bucket)

#### RabbitMQ Backups
- **Method**: Management API export (`/api/definitions`)
- **Contents**: Queues, exchanges, bindings, users, vhosts, policies
- **Format**: JSON with gzip compression

---

## Recovery Time & Point Objectives

### RTO (Recovery Time Objective)

| Scenario | RTO Target | Actual Tested |
|----------|------------|---------------|
| Single resource deletion | 15 minutes | ✓ |
| Namespace restore | 30 minutes | ✓ |
| Database corruption | 30 minutes | ✓ |
| Complete cluster failure | 2-4 hours | Pending |
| Region outage | 4-6 hours | Pending |

### RPO (Recovery Point Objective)

| Component | RPO Target | Backup Frequency |
|-----------|------------|------------------|
| Kubernetes resources | 1 hour | Hourly config backups |
| Application data | 6 hours | 6-hourly health-data backups |
| Databases | 24 hours | Daily backups |
| MinIO data lake | 24 hours | Daily sync |
| RabbitMQ config | 24 hours | Daily exports |

---

## Disaster Scenarios

### Scenario 1: Accidental Resource Deletion

**Symptoms:**
- Deployment, Service, or ConfigMap missing
- Pods not starting due to missing resources
- Application errors referencing missing configs

**Impact:**
- Service downtime
- Application unavailable
- Data access issues

**Recovery Procedure:** [See Section 5.1](#51-restore-deleted-kubernetes-resources)

**RTO:** 15 minutes
**RPO:** 1 hour (hourly config backups)

---

### Scenario 2: Database Corruption

**Symptoms:**
- PostgreSQL crashes or fails to start
- Data integrity errors
- Transaction log corruption
- Application database connection errors

**Impact:**
- Complete service outage
- Data inconsistency
- Potential data loss

**Recovery Procedure:** [See Section 6.1](#61-postgresql-restore)

**RTO:** 30 minutes
**RPO:** 24 hours (daily backups)

---

### Scenario 3: Complete Cluster Failure

**Symptoms:**
- Cluster API server unreachable
- All nodes down
- OKE control plane failure
- Cannot connect with kubectl

**Impact:**
- Complete platform outage
- All services unavailable
- No data access

**Recovery Procedure:** [See Section 5.3](#53-complete-cluster-rebuild)

**RTO:** 2-4 hours
**RPO:** 24 hours

---

### Scenario 4: Namespace Compromise

**Symptoms:**
- Security breach in specific namespace
- Unauthorized changes detected
- Malicious pods running
- Data exfiltration suspected

**Impact:**
- Security incident
- Potential data breach
- Compliance issues

**Recovery Procedure:** [See Section 5.2](#52-namespace-specific-restore)

**RTO:** 1 hour
**RPO:** 6 hours

---

### Scenario 5: Data Lake Corruption

**Symptoms:**
- MinIO service errors
- Bucket data corruption
- Object integrity failures
- S3 API errors

**Impact:**
- Historical data unavailable
- ETL pipeline failures
- ML model training blocked

**Recovery Procedure:** [See Section 6.3](#63-minio-data-lake-restore)

**RTO:** 2 hours
**RPO:** 24 hours

---

### Scenario 6: Region Outage (Oracle Cloud)

**Symptoms:**
- Entire eu-amsterdam-1 region unavailable
- Cannot access OCI services
- Cluster unreachable
- OCI console errors

**Impact:**
- Complete platform outage
- No access to backups in same region
- Multi-hour downtime

**Recovery Procedure:** [See Section 5.4](#54-region-failover)

**RTO:** 4-6 hours
**RPO:** 24 hours (last cross-region sync)

---

## Step-by-Step Recovery Procedures

### 5.1 Restore Deleted Kubernetes Resources

**Use Case:** Deployment, Service, ConfigMap, or other K8s resource accidentally deleted

#### Prerequisites
- Velero CLI installed and configured
- kubectl access to cluster
- Recent backup available

#### Steps

```bash
# 1. List available backups
velero backup get

# Example output:
# NAME                              STATUS      CREATED
# config-backup-20250120010000      Completed   2025-01-20 01:00:00 +0000 UTC
# daily-full-backup-20250120020000  Completed   2025-01-20 02:00:00 +0000 UTC

# 2. Identify the backup containing the resource
# Use the most recent config-backup for quick recovery

# 3. Restore specific resource type
velero restore create restore-$(date +%Y%m%d-%H%M%S) \
    --from-backup config-backup-20250120010000 \
    --include-resources deployment,service,configmap \
    --include-namespaces health-api

# 4. Monitor restore progress
velero restore describe restore-20250120-120000

# 5. Check restore logs
velero restore logs restore-20250120-120000

# 6. Verify resource restored
kubectl get all -n health-api

# 7. Check pod status
kubectl get pods -n health-api

# 8. Verify application is running
curl https://health-api.yourdomain.com/health
```

#### Troubleshooting

**Problem:** Resource still missing after restore

```bash
# Check if resource was in backup
velero backup describe config-backup-20250120010000 --details | grep deployment

# Check for errors
velero restore describe restore-20250120-120000 --details

# Try restoring from daily full backup instead
velero restore create --from-backup daily-full-backup-20250120020000 \
    --include-namespaces health-api
```

**Problem:** Restore conflicts with existing resources

```bash
# Delete conflicting resources first
kubectl delete deployment health-api -n health-api

# Retry restore
velero restore create --from-backup config-backup-20250120010000 \
    --include-namespaces health-api
```

---

### 5.2 Namespace-Specific Restore

**Use Case:** Entire namespace needs restoration (security breach, corruption)

#### Prerequisites
- Velero CLI installed
- kubectl access
- Namespace backup available

#### Steps

```bash
# 1. List available backups
velero backup get

# 2. Identify most recent backup with the namespace
# health-data-backup runs every 6 hours
# daily-full-backup runs daily at 2 AM

# 3. (Optional) Delete compromised namespace
kubectl delete namespace health-api --wait=true

# Note: Only delete if namespace is compromised or corrupted
# Otherwise, restore will merge with existing resources

# 4. Restore namespace
velero restore create restore-health-api-$(date +%Y%m%d-%H%M%S) \
    --from-backup daily-full-backup-20250120020000 \
    --include-namespaces health-api \
    --wait

# 5. Wait for pods to be ready
kubectl wait --for=condition=ready pod --all -n health-api --timeout=600s

# 6. Verify all resources
kubectl get all -n health-api

# 7. Check PersistentVolumeClaims
kubectl get pvc -n health-api

# 8. Verify ConfigMaps and Secrets
kubectl get configmap,secret -n health-api

# 9. Test application functionality
curl https://health-api.yourdomain.com/health
curl https://health-api.yourdomain.com/api/v1/status
```

#### Post-Restore Verification

```bash
# Check application logs
kubectl logs -n health-api deployment/health-api --tail=100

# Verify database connectivity
kubectl exec -n health-data postgresql-health-primary-0 -- \
    psql -U healthapi -d healthdb -c "SELECT COUNT(*) FROM health_records;"

# Check service endpoints
kubectl get endpoints -n health-api

# Verify ingress
kubectl get ingress -n health-api
```

---

### 5.3 Complete Cluster Rebuild

**Use Case:** Total cluster failure, need to rebuild from scratch

#### Prerequisites
- Terraform installed
- OCI CLI configured
- Access to Terraform state (OCI Object Storage)
- Velero CLI installed
- OCI credentials for Object Storage
- DNS management access

#### Steps

**Phase 1: Provision New Cluster**

```bash
# 1. Navigate to Terraform configuration
cd terraform/environments/production

# 2. Review current state
terraform plan

# 3. Provision new OKE cluster
terraform apply -auto-approve

# Expected time: 20-30 minutes

# 4. Configure kubectl
export KUBECONFIG=~/.kube/config
oci ce cluster create-kubeconfig \
    --cluster-id <cluster-ocid> \
    --file ~/.kube/config \
    --region eu-amsterdam-1

# 5. Verify cluster access
kubectl cluster-info
kubectl get nodes
```

**Phase 2: Install Velero**

```bash
# 1. Create Velero namespace
kubectl create namespace velero

# 2. Create OCI credentials secret
cat > velero-oci-credentials <<EOF
[default]
aws_access_key_id=<OCI_ACCESS_KEY>
aws_secret_access_key=<OCI_SECRET_KEY>
EOF

kubectl create secret generic velero-oci-credentials \
    --namespace velero \
    --from-file=cloud=velero-oci-credentials

# 3. Add Velero Helm repo
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm repo update

# 4. Install Velero chart
cd ../../../helm-charts/health-platform/charts/velero

helm install velero . \
    --namespace velero \
    --set velero.enabled=true \
    --set oci.namespace=<YOUR_OCI_NAMESPACE> \
    --set velero.configuration.backupStorageLocation.config.s3Url=https://<NAMESPACE>.compat.objectstorage.eu-amsterdam-1.oraclecloud.com

# 5. Wait for Velero to be ready
kubectl wait --for=condition=available --timeout=300s \
    deployment/velero -n velero

# 6. Verify Velero can see backups
velero backup get
```

**Phase 3: Restore Cluster**

```bash
# 1. Identify most recent full backup
LATEST_BACKUP=$(velero backup get -o json | \
    jq -r '.items | sort_by(.status.startTimestamp) | .[-1].metadata.name')

echo "Restoring from: ${LATEST_BACKUP}"

# 2. Create restore
velero restore create cluster-restore-$(date +%Y%m%d-%H%M%S) \
    --from-backup "${LATEST_BACKUP}" \
    --wait

# Expected time: 15-30 minutes

# 3. Monitor restore progress
velero restore describe cluster-restore-20250120-140000

# 4. Check restore logs for errors
velero restore logs cluster-restore-20250120-140000
```

**Phase 4: Verify Services**

```bash
# 1. Check all namespaces restored
kubectl get namespaces | grep health

# Expected output:
# health-api            Active   5m
# health-auth           Active   5m
# health-data           Active   5m
# health-etl            Active   5m
# health-observability  Active   5m

# 2. Wait for all pods to be ready
for NS in health-api health-auth health-etl health-data health-observability; do
    echo "Checking namespace: ${NS}"
    kubectl wait --for=condition=ready pod --all -n "${NS}" --timeout=600s
done

# 3. Verify PostgreSQL databases
echo "Checking PostgreSQL health-data..."
kubectl exec -n health-data postgresql-health-primary-0 -- \
    psql -U healthapi -d healthdb -c "SELECT version();"

echo "Checking PostgreSQL auth..."
kubectl exec -n health-auth postgresql-auth-primary-0 -- \
    psql -U webauthn -d webauthn -c "SELECT version();"

# 4. Verify MinIO
kubectl exec -n health-data deploy/minio -- \
    mc alias set local http://localhost:9000 minioadmin minioadmin

kubectl exec -n health-data deploy/minio -- \
    mc ls local/

# 5. Verify RabbitMQ
kubectl exec -n health-data deploy/rabbitmq -- \
    rabbitmqctl status

# 6. Check Jaeger (observability)
kubectl port-forward -n health-observability svc/jaeger-query 16686:16686 &
curl http://localhost:16686/api/services
```

**Phase 5: Update DNS**

```bash
# 1. Get new LoadBalancer IP
kubectl get svc -n health-api health-api -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

# 2. Update DNS records (method depends on DNS provider)
# Example for OCI DNS:
oci dns record rrset update \
    --zone-name-or-id yourdomain.com \
    --domain health-api.yourdomain.com \
    --rtype A \
    --items '[{"domain":"health-api.yourdomain.com","rdata":"<NEW_IP>","rtype":"A","ttl":300}]'

# 3. Wait for DNS propagation
watch -n 5 dig health-api.yourdomain.com

# 4. Test endpoint
curl https://health-api.yourdomain.com/health
```

**Phase 6: Restore Databases (if needed)**

```bash
# If database backups are more recent than Velero PV snapshots,
# restore databases separately (see Section 6)

cd scripts/backup-restore

# Download latest database backups from OCI
# (Use OCI console or CLI)

# Restore health-data database
./restore-database.sh health-data postgres-health-20250120-030000.sql.gz

# Restore auth database
./restore-database.sh auth postgres-auth-20250120-030000.sql.gz
```

**Phase 7: Post-Restore Monitoring**

```bash
# 1. Monitor application logs
kubectl logs -n health-api deployment/health-api --tail=100 -f

# 2. Check Prometheus alerts
kubectl port-forward -n health-observability svc/prometheus 9090:9090 &
open http://localhost:9090/alerts

# 3. Check Grafana dashboards
kubectl port-forward -n health-observability svc/grafana 3000:3000 &
open http://localhost:3000

# 4. Run integration tests
# (If available)
./scripts/integration-tests.sh

# 5. Monitor for 24 hours
# Watch for errors, performance issues, data inconsistencies
```

---

### 5.4 Region Failover

**Use Case:** Entire Oracle Cloud region unavailable

#### Prerequisites
- Terraform configuration for secondary region
- OCI Object Storage cross-region replication enabled
- DNS with low TTL (< 5 minutes)
- Velero backups replicated to secondary region

#### Steps

**Note:** This procedure requires advance setup of cross-region replication and secondary infrastructure.

```bash
# 1. Verify backups available in secondary region
# Login to OCI console for secondary region
# Check bucket: health-platform-velero-backups (replicated)

# 2. Provision cluster in secondary region
cd terraform/environments/production-secondary
terraform apply -auto-approve

# 3. Follow cluster rebuild procedure (Section 5.3)
# with secondary region configuration

# 4. Update DNS to secondary region
# Point health-api.yourdomain.com to new LoadBalancer IP

# 5. Monitor traffic shift
# Watch access logs for requests hitting new region

# 6. When primary region recovers
# Reverse DNS changes
# Sync data back to primary region if needed
```

---

## Database Recovery

### 6.1 PostgreSQL Restore

#### Health Data Database

**Use Case:** Restore health-data PostgreSQL database from backup

```bash
# 1. Download latest backup from OCI Object Storage
# Option A: Use OCI Console
# Navigate to Object Storage > health-platform-db-backups
# Download postgres-health-YYYYMMDD-HHMMSS.sql.gz

# Option B: Use OCI CLI
oci os object get \
    --namespace <NAMESPACE> \
    --bucket-name health-platform-db-backups \
    --name postgres-health-20250120-030000.sql.gz \
    --file postgres-health-20250120-030000.sql.gz

# 2. Run restore script
cd scripts/backup-restore
./restore-database.sh health-data postgres-health-20250120-030000.sql.gz

# Script will:
# - Scale down health-api and etl-engine
# - Copy backup to PostgreSQL pod
# - Drop and recreate database
# - Restore from pg_dump
# - Grant permissions
# - Scale applications back up

# 3. Verify restore
kubectl exec -n health-data postgresql-health-primary-0 -- \
    psql -U healthapi -d healthdb -c "
    SELECT
        schemaname,
        tablename,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
    LIMIT 10;
    "

# 4. Test application
curl https://health-api.yourdomain.com/api/v1/health-records?limit=10

# 5. Check application logs
kubectl logs -n health-api deployment/health-api --tail=100
```

#### WebAuthn Auth Database

```bash
# 1. Download backup
oci os object get \
    --namespace <NAMESPACE> \
    --bucket-name health-platform-db-backups \
    --name postgres-auth-20250120-030000.sql.gz \
    --file postgres-auth-20250120-030000.sql.gz

# 2. Run restore script
cd scripts/backup-restore
./restore-database.sh auth postgres-auth-20250120-030000.sql.gz

# 3. Verify restore
kubectl exec -n health-auth postgresql-auth-primary-0 -- \
    psql -U webauthn -d webauthn -c "SELECT COUNT(*) FROM users;"

# 4. Test authentication
curl https://auth.yourdomain.com/health
```

#### Manual PostgreSQL Restore (Alternative)

```bash
# If automated script fails, use manual procedure

# 1. Scale down applications
kubectl scale deployment health-api --replicas=0 -n health-api
kubectl scale deployment etl-engine --replicas=0 -n health-etl

# 2. Copy backup to pod
kubectl cp postgres-health-20250120-030000.sql.gz \
    health-data/postgresql-health-primary-0:/tmp/backup.sql.gz

# 3. Connect to PostgreSQL pod
kubectl exec -it -n health-data postgresql-health-primary-0 -- bash

# 4. Inside pod, restore database
# Drop existing database
psql -U postgres -c "DROP DATABASE IF EXISTS healthdb;"

# Create new database
psql -U postgres -c "CREATE DATABASE healthdb;"

# Restore from backup
gunzip < /tmp/backup.sql.gz | \
    pg_restore -U postgres -d healthdb --no-owner --no-acl --verbose

# Grant permissions
psql -U postgres -d healthdb <<EOF
GRANT ALL PRIVILEGES ON DATABASE healthdb TO healthapi;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO healthapi;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO healthapi;
EOF

# Verify
psql -U healthapi -d healthdb -c "SELECT COUNT(*) FROM information_schema.tables;"

# Cleanup
rm -f /tmp/backup.sql.gz
exit

# 5. Scale up applications
kubectl scale deployment health-api --replicas=2 -n health-api
kubectl scale deployment etl-engine --replicas=1 -n health-etl
```

---

### 6.2 PostgreSQL Point-in-Time Recovery (PITR)

**Note:** Full PITR requires WAL archiving, which is not currently configured. This section describes how to implement it.

#### Setup WAL Archiving (Future Implementation)

```yaml
# Add to PostgreSQL Helm values
postgresql-health:
  primary:
    extraVolumes:
      - name: wal-archive
        persistentVolumeClaim:
          claimName: postgresql-wal-archive

    extraVolumeMounts:
      - name: wal-archive
        mountPath: /archive

    configuration: |
      wal_level = replica
      archive_mode = on
      archive_command = 'test ! -f /archive/%f && cp %p /archive/%f'
      archive_timeout = 300
```

#### Restore to Point in Time (When WAL Archiving Enabled)

```bash
# 1. Stop PostgreSQL
kubectl scale statefulset postgresql-health-primary --replicas=0 -n health-data

# 2. Restore base backup
# (Follow Section 6.1)

# 3. Create recovery.conf
kubectl exec -n health-data postgresql-health-primary-0 -- bash -c "
cat > /bitnami/postgresql/data/recovery.conf <<EOF
restore_command = 'cp /archive/%f %p'
recovery_target_time = '2025-01-20 14:30:00'
recovery_target_action = 'promote'
EOF
"

# 4. Start PostgreSQL
kubectl scale statefulset postgresql-health-primary --replicas=1 -n health-data

# 5. Monitor recovery
kubectl logs -n health-data postgresql-health-primary-0 -f
```

---

### 6.3 MinIO Data Lake Restore

**Use Case:** Restore MinIO buckets from OCI Object Storage backup

#### Prerequisites
- MinIO mc CLI installed (or use MinIO pod)
- OCI credentials for backup bucket
- MinIO credentials for target cluster

#### Steps

```bash
# 1. List available backups in OCI
oci os object list \
    --namespace <NAMESPACE> \
    --bucket-name health-platform-minio-backups \
    --prefix minio-backups/ \
    | jq -r '.data[].name'

# Example output:
# minio-backups/raw-health-data/20250120-040000/
# minio-backups/processed-data/20250120-040000/
# minio-backups/clinical-narratives/20250120-040000/
# minio-backups/model-artifacts/20250120-040000/

# 2. Port-forward to MinIO
kubectl port-forward -n health-data svc/minio 9000:9000 &

# 3. Configure mc aliases
mc alias set target http://localhost:9000 <MINIO_ACCESS_KEY> <MINIO_SECRET_KEY>

mc alias set oci \
    https://<NAMESPACE>.compat.objectstorage.eu-amsterdam-1.oraclecloud.com \
    <OCI_ACCESS_KEY> \
    <OCI_SECRET_KEY>

# 4. Restore specific bucket
BACKUP_DATE="20250120-040000"
BUCKET="raw-health-data"

mc mirror --overwrite \
    oci/health-platform-minio-backups/minio-backups/${BUCKET}/${BACKUP_DATE}/ \
    target/${BUCKET}/

# 5. Verify restore
mc ls target/${BUCKET}/
mc du target/${BUCKET}/

# 6. Repeat for other buckets
for BUCKET in processed-data clinical-narratives model-artifacts; do
    echo "Restoring bucket: ${BUCKET}"
    mc mirror --overwrite \
        oci/health-platform-minio-backups/minio-backups/${BUCKET}/${BACKUP_DATE}/ \
        target/${BUCKET}/
done

# 7. Verify data integrity
kubectl exec -n health-data deploy/minio -- \
    mc admin heal -r target/
```

#### Alternative: Restore Using MinIO Pod

```bash
# 1. Copy OCI credentials to MinIO pod
kubectl create secret generic oci-credentials \
    --from-literal=access-key=<OCI_ACCESS_KEY> \
    --from-literal=secret-key=<OCI_SECRET_KEY> \
    -n health-data

# 2. Exec into MinIO pod
kubectl exec -it -n health-data deploy/minio -- bash

# 3. Configure aliases inside pod
mc alias set oci \
    https://<NAMESPACE>.compat.objectstorage.eu-amsterdam-1.oraclecloud.com \
    $OCI_ACCESS_KEY \
    $OCI_SECRET_KEY

mc alias set local http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD

# 4. Restore buckets
for BUCKET in raw-health-data processed-data clinical-narratives model-artifacts; do
    mc mirror --overwrite \
        oci/health-platform-minio-backups/minio-backups/${BUCKET}/20250120-040000/ \
        local/${BUCKET}/
done

# 5. Exit pod
exit
```

---

### 6.4 RabbitMQ Definitions Restore

**Use Case:** Restore RabbitMQ queues, exchanges, and configurations

```bash
# 1. Download backup from OCI
oci os object get \
    --namespace <NAMESPACE> \
    --bucket-name health-platform-db-backups \
    --name rabbitmq-definitions-20250120-050000.json.gz \
    --file rabbitmq-definitions-20250120-050000.json.gz

# 2. Run restore script
cd scripts/backup-restore
./restore-database.sh rabbitmq rabbitmq-definitions-20250120-050000.json.gz

# Script will:
# - Extract definitions JSON
# - Copy to RabbitMQ pod
# - Import via Management API
# - Cleanup temporary files

# 3. Verify restore
kubectl exec -n health-data deploy/rabbitmq -- \
    rabbitmqctl list_queues name messages

# 4. Check Management UI
kubectl port-forward -n health-data svc/rabbitmq 15672:15672 &
open http://localhost:15672

# Login with credentials from secret:
kubectl get secret rabbitmq-secret -n health-data -o jsonpath='{.data.rabbitmq-username}' | base64 -d
kubectl get secret rabbitmq-secret -n health-data -o jsonpath='{.data.rabbitmq-password}' | base64 -d
```

#### Manual RabbitMQ Restore (Alternative)

```bash
# 1. Extract definitions
gunzip rabbitmq-definitions-20250120-050000.json.gz

# 2. Get RabbitMQ credentials
RABBITMQ_USER=$(kubectl get secret rabbitmq-secret -n health-data -o jsonpath='{.data.rabbitmq-username}' | base64 -d)
RABBITMQ_PASSWORD=$(kubectl get secret rabbitmq-secret -n health-data -o jsonpath='{.data.rabbitmq-password}' | base64 -d)

# 3. Port-forward to RabbitMQ Management API
kubectl port-forward -n health-data svc/rabbitmq 15672:15672 &

# 4. Import definitions
curl -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
    -H "content-type:application/json" \
    -X POST \
    --data-binary @rabbitmq-definitions-20250120-050000.json \
    http://localhost:15672/api/definitions

# 5. Verify
curl -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
    http://localhost:15672/api/queues | jq '.[] | {name, messages}'
```

---

## Backup Verification

### Automated Verification

A CronJob runs daily at 6 AM UTC to verify all backups.

#### Check Verification Status

```bash
# 1. Get recent verification jobs
kubectl get jobs -n velero -l app=backup-verification --sort-by=.status.startTime

# 2. Check latest verification logs
LATEST_JOB=$(kubectl get jobs -n velero -l app=backup-verification --sort-by=.status.startTime -o jsonpath='{.items[-1].metadata.name}')

kubectl logs -n velero job/${LATEST_JOB}

# 3. Check for failures
kubectl get jobs -n velero -l app=backup-verification --field-selector status.successful!=1
```

#### Manual Verification

```bash
# 1. Trigger manual verification
kubectl create job --from=cronjob/backup-verification \
    verify-manual-$(date +%s) -n velero

# 2. Monitor logs
kubectl logs -n velero job/verify-manual-xxxxx -f

# 3. Check exit code
kubectl get job verify-manual-xxxxx -n velero -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}'
```

### Manual Backup Inspection

```bash
# 1. List all backups
./scripts/backup-restore/list-backups.sh

# 2. Inspect specific Velero backup
velero backup describe daily-full-backup-20250120020000 --details

# 3. Check backup contents
velero backup describe daily-full-backup-20250120020000 --details | grep "Resource List"

# 4. Download backup logs
velero backup logs daily-full-backup-20250120020000 > backup-logs.txt

# 5. Check database backup sizes in OCI
oci os object list \
    --namespace <NAMESPACE> \
    --bucket-name health-platform-db-backups \
    | jq '.data[] | {name: .name, size: .size, time: .timeCreated}'
```

---

## Testing & Drills

### Monthly DR Drill

**Objective:** Verify backup and restore procedures work correctly

**Schedule:** First Monday of each month at 10 AM

#### Procedure

```bash
# 1. Create test namespace
kubectl create namespace dr-test

# 2. Restore to test namespace
velero restore create dr-drill-$(date +%Y%m%d) \
    --from-backup daily-full-backup-latest \
    --namespace-mappings health-api:dr-test \
    --wait

# 3. Verify pods running
kubectl wait --for=condition=ready pod --all -n dr-test --timeout=600s

# 4. Check all resources
kubectl get all -n dr-test

# 5. Test functionality (if possible)
kubectl port-forward -n dr-test svc/health-api 8080:80 &
curl http://localhost:8080/health

# 6. Document results
cat > dr-drill-$(date +%Y%m%d).md <<EOF
# DR Drill Report - $(date +%Y-%m-%d)

## Summary
- **Backup Used**: daily-full-backup-latest
- **Restore Time**: X minutes
- **Status**: Success/Failure
- **Issues Found**: List any issues

## Verification
- Pods Running: Yes/No
- Data Accessible: Yes/No
- Services Responding: Yes/No

## Actions Required
- List any follow-up actions

## Conducted By
- Name, Date
EOF

# 7. Cleanup
kubectl delete namespace dr-test
```

### Quarterly Full Rebuild Test

**Objective:** Verify complete cluster rebuild procedures

**Schedule:** Every quarter (Jan, Apr, Jul, Oct)

#### Procedure

```bash
# WARNING: This test requires a separate test environment
# DO NOT run in production

# 1. Document current state
kubectl get all -A > cluster-state-before.txt
velero backup get > backups-before.txt

# 2. Provision test cluster
cd terraform/environments/dr-test
terraform apply -auto-approve

# 3. Install Velero on test cluster
# (Follow Section 5.3, Phase 2)

# 4. Restore from production backup
velero restore create test-restore-$(date +%Y%m%d) \
    --from-backup daily-full-backup-latest \
    --wait

# 5. Verify all services
# (Follow Section 5.3, Phase 4)

# 6. Compare states
kubectl get all -A > cluster-state-after.txt
diff cluster-state-before.txt cluster-state-after.txt

# 7. Document results and lessons learned

# 8. Destroy test cluster
terraform destroy -auto-approve
```

---

## Monitoring & Alerts

### Prometheus Alerts

#### Backup Failure Alerts

```yaml
# Alert: VeleroBackupFailure
# Severity: Critical
# Condition: Velero backup has failed

- alert: VeleroBackupFailure
  expr: velero_backup_failure_total > 0
  for: 5m
  annotations:
    summary: "Velero backup has failed"
    description: "Backup {{ $labels.backup }} has failed"

# Alert: VeleroBackupTooOld
# Severity: Warning
# Condition: No successful backup in 24 hours

- alert: VeleroBackupTooOld
  expr: time() - velero_backup_last_successful_timestamp > 86400
  for: 1h
  annotations:
    summary: "No successful backup in 24 hours"
    description: "Latest backup is {{ $value }} seconds old"

# Alert: DatabaseBackupFailed
# Severity: Warning
# Condition: Database backup CronJob failed

- alert: DatabaseBackupFailed
  expr: kube_job_status_failed{job=~"postgresql-.*-backup|minio-backup|rabbitmq-backup"} > 0
  for: 5m
  annotations:
    summary: "Database backup job failed"
    description: "Job {{ $labels.job_name }} has failed"
```

### Checking Alert Status

```bash
# 1. Port-forward to Prometheus
kubectl port-forward -n health-observability svc/prometheus 9090:9090 &

# 2. Open Prometheus UI
open http://localhost:9090/alerts

# 3. Check firing alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'

# 4. Query backup metrics
curl -s 'http://localhost:9090/api/v1/query?query=velero_backup_last_successful_timestamp' | jq .

# 5. Check database backup job status
kubectl get jobs -n health-data -l app=postgresql-backup
kubectl get jobs -n health-auth -l app=postgresql-backup
```

### Grafana Dashboards

#### Disaster Recovery Dashboard

```bash
# 1. Port-forward to Grafana
kubectl port-forward -n health-observability svc/grafana 3000:3000 &

# 2. Open Grafana
open http://localhost:3000

# 3. Login (get credentials from secret)
kubectl get secret grafana-admin -n health-observability -o jsonpath='{.data.password}' | base64 -d

# 4. Navigate to "Disaster Recovery" dashboard

# Dashboard includes:
# - Backup success rate (last 7 days)
# - Time since last successful backup
# - Backup size trends
# - Database backup job status
# - Restore test results
# - Alert status
```

---

## Contact Information

### On-Call Rotation

| Role | Primary | Secondary |
|------|---------|-----------|
| **Platform Engineer** | Name, Email, Phone | Name, Email, Phone |
| **Database Administrator** | Name, Email, Phone | Name, Email, Phone |
| **Security Engineer** | Name, Email, Phone | Name, Email, Phone |
| **Engineering Manager** | Name, Email, Phone | - |

### Escalation Path

1. **Level 1**: On-call Platform Engineer
2. **Level 2**: Senior Platform Engineer + Database Administrator
3. **Level 3**: Engineering Manager + CTO

### Communication Channels

- **Slack**: `#incidents` channel
- **Email**: `ops-team@yourdomain.com`
- **Phone**: Emergency hotline (to be configured)
- **Ticketing**: JIRA project `INCIDENT`

### External Contacts

- **Oracle Cloud Support**: `+XX-XXX-XXX-XXXX`
- **DNS Provider Support**: Contact info
- **Security Team**: Contact info

---

## Appendix

### A. Backup Storage Estimates

| Component | Daily Size | Monthly Size (30 days) | Annual Size |
|-----------|------------|------------------------|-------------|
| Velero full backup | 2-5 GB | 60-150 GB | 730 GB - 1.8 TB |
| PostgreSQL health-data | 500 MB - 2 GB | 15-60 GB | 180-730 GB |
| PostgreSQL auth | 100-500 MB | 3-15 GB | 36-180 GB |
| MinIO snapshots | 10-20 GB | 70-140 GB | 730 GB - 1.4 TB |
| RabbitMQ definitions | 1-10 MB | 30-300 MB | 365 MB - 3.6 GB |
| **Total** | ~15-30 GB/day | ~150-365 GB/month | ~1.7-4 TB/year |

**Note:** With retention policies, actual storage is much lower:
- Velero: 30 days retention = ~60-150 GB
- Databases: 7 days retention = ~10-45 GB
- **Total with retention**: ~70-195 GB

### B. Useful Commands Reference

```bash
# List all backups
velero backup get

# Create manual backup
velero backup create manual-$(date +%Y%m%d-%H%M%S) \
    --include-namespaces health-api,health-auth,health-etl,health-data

# Restore from backup
velero restore create --from-backup <backup-name>

# Monitor restore
velero restore describe <restore-name>
velero restore logs <restore-name>

# List database backup jobs
kubectl get jobs -n health-data -l app=postgresql-backup

# Trigger manual database backup
kubectl create job --from=cronjob/postgresql-health-backup \
    manual-db-backup-$(date +%s) -n health-data

# Check backup verification status
kubectl logs -n velero $(kubectl get pods -n velero -l app=backup-verification -o name | head -1)

# Port-forward to services
kubectl port-forward -n health-observability svc/prometheus 9090:9090
kubectl port-forward -n health-observability svc/grafana 3000:3000
kubectl port-forward -n health-data svc/minio 9000:9000

# Scale applications
kubectl scale deployment health-api --replicas=0 -n health-api
kubectl scale deployment health-api --replicas=2 -n health-api
```

### C. Velero Configuration Reference

```yaml
# Current Velero configuration
schedules:
  - name: daily-full-backup
    schedule: "0 2 * * *"
    retention: 30 days
    namespaces: all health-* namespaces

  - name: health-data-backup
    schedule: "0 */6 * * *"
    retention: 7 days
    namespaces: health-data

  - name: config-backup
    schedule: "0 */1 * * *"
    retention: 7 days
    resources: configmap,secret,serviceaccount

storage:
  provider: aws (OCI S3-compatible)
  bucket: health-platform-velero-backups
  region: eu-amsterdam-1
  endpoint: https://<namespace>.compat.objectstorage.eu-amsterdam-1.oraclecloud.com
```

### D. Terraform Recovery Configuration

```hcl
# Key Terraform resources for cluster rebuild

resource "oci_containerengine_cluster" "health_platform" {
  compartment_id     = var.compartment_id
  kubernetes_version = "v1.28.2"
  name               = "health-platform-prod"
  vcn_id             = oci_core_vcn.health_vcn.id

  options {
    service_lb_subnet_ids = [oci_core_subnet.lb_subnet.id]
  }
}

resource "oci_containerengine_node_pool" "health_nodes" {
  cluster_id         = oci_containerengine_cluster.health_platform.id
  compartment_id     = var.compartment_id
  kubernetes_version = "v1.28.2"
  name               = "health-nodes"
  node_shape         = "VM.Standard.E2.1.Micro"

  node_config_details {
    size = 3
  }
}
```

### E. Backup Encryption

All backups are encrypted at rest in OCI Object Storage.

**Encryption Configuration:**
- **Method**: Server-side encryption with OCI-managed keys
- **Algorithm**: AES-256
- **Key Rotation**: Automatic (OCI managed)

**Enable encryption for new buckets:**

```bash
oci os bucket create \
    --namespace <NAMESPACE> \
    --compartment-id <COMPARTMENT_ID> \
    --name health-platform-velero-backups \
    --storage-tier Standard \
    --public-access-type NoPublicAccess

# Encryption is enabled by default for OCI Object Storage
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01-20 | Platform Team | Initial disaster recovery runbook |

---

**Last Reviewed**: 2025-01-20
**Next Review Due**: 2025-04-20
**Document Owner**: Platform Engineering Team
