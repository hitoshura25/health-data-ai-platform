# Database Backup CronJobs

This directory contains Kubernetes CronJob definitions for automated database and service backups.

## Overview

The backup jobs complement Velero's Kubernetes resource backups by providing database-specific backups that are uploaded to OCI Object Storage.

## Backup Jobs

| CronJob | Schedule | Description | Namespace |
|---------|----------|-------------|-----------|
| `postgresql-health-backup` | Daily at 3 AM UTC | Health data PostgreSQL database | `health-data` |
| `postgresql-auth-backup` | Daily at 3 AM UTC | WebAuthn auth PostgreSQL database | `health-auth` |
| `minio-backup` | Daily at 4 AM UTC | MinIO data lake buckets | `health-data` |
| `rabbitmq-backup` | Daily at 5 AM UTC | RabbitMQ definitions | `health-data` |

## Deployment

### Prerequisites

1. **OCI Object Storage buckets created**:
   - `health-platform-db-backups`
   - `health-platform-minio-backups`

2. **Pre-authenticated requests (PARs) created**:
   ```bash
   # Create PAR for database backups (write access, 1 year expiry)
   oci os preauth-request create \
       --namespace <NAMESPACE> \
       --bucket-name health-platform-db-backups \
       --name db-backup-upload \
       --access-type ObjectWrite \
       --time-expires $(date -u -d "+1 year" +"%Y-%m-%dT%H:%M:%SZ")
   ```

3. **Secrets configured**:
   ```bash
   # Create backup-oci-config secret in health-data namespace
   kubectl create secret generic backup-oci-config \
       --from-literal=database-upload-url="https://objectstorage.eu-amsterdam-1.oraclecloud.com/p/YOUR_PAR_TOKEN/n/NAMESPACE/b/health-platform-db-backups/o" \
       --from-literal=oci-access-key="YOUR_ACCESS_KEY" \
       --from-literal=oci-secret-key="YOUR_SECRET_KEY" \
       -n health-data

   # Create backup-oci-config secret in health-auth namespace
   kubectl create secret generic backup-oci-config \
       --from-literal=database-upload-url="https://objectstorage.eu-amsterdam-1.oraclecloud.com/p/YOUR_PAR_TOKEN/n/NAMESPACE/b/health-platform-db-backups/o" \
       -n health-auth
   ```

### Deploy Backup Jobs

```bash
# Deploy PostgreSQL backup jobs
kubectl apply -f postgresql-health-backup.yaml
kubectl apply -f postgresql-auth-backup.yaml

# Deploy MinIO backup job
kubectl apply -f minio-backup.yaml

# Deploy RabbitMQ backup job
kubectl apply -f rabbitmq-backup.yaml

# Verify CronJobs created
kubectl get cronjobs -n health-data
kubectl get cronjobs -n health-auth
```

## Manual Backup Execution

Trigger backups manually for testing or ad-hoc needs:

```bash
# PostgreSQL health-data backup
kubectl create job --from=cronjob/postgresql-health-backup \
    manual-pg-health-$(date +%s) -n health-data

# PostgreSQL auth backup
kubectl create job --from=cronjob/postgresql-auth-backup \
    manual-pg-auth-$(date +%s) -n health-auth

# MinIO backup
kubectl create job --from=cronjob/minio-backup \
    manual-minio-$(date +%s) -n health-data

# RabbitMQ backup
kubectl create job --from=cronjob/rabbitmq-backup \
    manual-rabbitmq-$(date +%s) -n health-data

# Monitor job execution
kubectl get jobs -n health-data
kubectl logs -n health-data job/manual-pg-health-xxxxx
```

## Monitoring

### Check Backup Status

```bash
# List recent backup jobs
kubectl get jobs -n health-data -l app=postgresql-backup --sort-by=.status.startTime
kubectl get jobs -n health-data -l app=minio-backup --sort-by=.status.startTime
kubectl get jobs -n health-data -l app=rabbitmq-backup --sort-by=.status.startTime

# Check for failed jobs
kubectl get jobs -n health-data --field-selector status.successful!=1

# View logs for specific job
kubectl logs -n health-data job/<job-name>
```

### Prometheus Metrics

The backup jobs can be monitored via Prometheus:

```promql
# Failed backup jobs
kube_job_status_failed{job=~"postgresql-.*-backup|minio-backup|rabbitmq-backup"} > 0

# Job completion time
kube_job_status_completion_time{job=~"postgresql-.*-backup|minio-backup|rabbitmq-backup"}
```

## Backup Verification

Backups are automatically verified by the backup-verification CronJob in the `velero` namespace.

Manual verification:

```bash
# List backups in OCI Object Storage
oci os object list \
    --namespace <NAMESPACE> \
    --bucket-name health-platform-db-backups \
    | jq '.data[].name'

# Download and inspect a backup
oci os object get \
    --namespace <NAMESPACE> \
    --bucket-name health-platform-db-backups \
    --name postgres-health-20250120-030000.sql.gz \
    --file /tmp/backup.sql.gz

# Verify backup is not corrupted
gunzip -t /tmp/backup.sql.gz
```

## Restore Procedures

See [../../DISASTER-RECOVERY.md](../../DISASTER-RECOVERY.md) for complete restore procedures.

Quick restore:

```bash
# Use the restore script
cd ../../scripts/backup-restore

# Restore health-data database
./restore-database.sh health-data postgres-health-20250120-030000.sql.gz

# Restore auth database
./restore-database.sh auth postgres-auth-20250120-030000.sql.gz

# Restore RabbitMQ
./restore-database.sh rabbitmq rabbitmq-definitions-20250120-050000.json.gz
```

## Retention Policy

| Backup Type | Retention Period | Cleanup Method |
|-------------|------------------|----------------|
| PostgreSQL | 7 days | OCI Lifecycle Policy |
| MinIO | 7 days | OCI Lifecycle Policy |
| RabbitMQ | 7 days | OCI Lifecycle Policy |

Configure OCI Object Storage lifecycle policy:

```bash
oci os object-lifecycle-policy put \
    --namespace <NAMESPACE> \
    --bucket-name health-platform-db-backups \
    --items '[{
        "name": "delete-old-backups",
        "action": "DELETE",
        "objectNameFilter": {
            "inclusionPrefixes": ["postgres-", "minio-", "rabbitmq-"]
        },
        "timeAmount": 7,
        "timeUnit": "DAYS",
        "isEnabled": true
    }]'
```

## Troubleshooting

### Backup Job Failing

```bash
# Check CronJob configuration
kubectl get cronjob postgresql-health-backup -n health-data -o yaml

# View recent job logs
kubectl logs -n health-data \
    $(kubectl get pods -n health-data -l app=postgresql-backup --sort-by=.status.startTime -o name | tail -1)

# Check secrets exist
kubectl get secret postgresql-health-secret -n health-data
kubectl get secret backup-oci-config -n health-data

# Test database connectivity
kubectl exec -n health-data postgresql-health-primary-0 -- \
    psql -U healthapi -d healthdb -c "SELECT version();"
```

### Upload to OCI Failing

```bash
# Test PAR URL
curl -I "https://objectstorage.eu-amsterdam-1.oraclecloud.com/p/YOUR_PAR_TOKEN/..."

# Check OCI credentials
kubectl get secret backup-oci-config -n health-data -o yaml

# Verify network connectivity from pod
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
    curl -I "https://objectstorage.eu-amsterdam-1.oraclecloud.com"
```

### MinIO Backup Issues

```bash
# Test MinIO connectivity
kubectl exec -n health-data deploy/minio -- \
    mc alias set local http://localhost:9000 minioadmin minioadmin

# List buckets
kubectl exec -n health-data deploy/minio -- \
    mc ls local/

# Check MinIO credentials
kubectl get secret minio-secret -n health-data -o jsonpath='{.data.root-user}' | base64 -d
```

## Security Considerations

1. **Secrets Management**:
   - Use Kubernetes Secrets for credentials
   - Consider using sealed-secrets or external secret management (Vault, OCI Secrets)
   - Rotate OCI access keys regularly

2. **Network Security**:
   - Backups upload over HTTPS
   - Use NetworkPolicies to restrict egress
   - OCI Object Storage endpoints are regional

3. **Backup Encryption**:
   - OCI Object Storage provides encryption at rest
   - PostgreSQL backups are compressed but not encrypted (consider pgcrypto for sensitive data)
   - Use OCI KMS for additional encryption layer

4. **Access Control**:
   - Limit RBAC permissions for backup jobs
   - Use OCI IAM policies to restrict bucket access
   - PAR URLs should have short expiry times

## Additional Resources

- [Disaster Recovery Runbook](../../DISASTER-RECOVERY.md)
- [Backup/Restore Scripts](../../scripts/backup-restore/)
- [Backup Verification](../backup-verification/)
- [OCI Object Storage Documentation](https://docs.oracle.com/en-us/iaas/Content/Object/home.htm)
