# Velero Disaster Recovery Chart

Kubernetes backup and disaster recovery solution for the Health Data AI Platform using Velero and OCI Object Storage.

## Overview

This Helm chart deploys Velero configured to back up:
- All Kubernetes resources (deployments, services, configs, etc.)
- Persistent volumes using restic
- Database dumps (PostgreSQL)
- MinIO data lake buckets
- RabbitMQ configurations

## Prerequisites

- Kubernetes 1.23+
- Helm 3.0+
- Oracle Cloud Infrastructure (OCI) account with Object Storage
- OCI Object Storage bucket created
- OCI API credentials (access key and secret key)

## Installation

### 1. Create OCI Object Storage Bucket

```bash
# Using OCI CLI
oci os bucket create \
  --namespace <your-namespace> \
  --name health-platform-velero-backups \
  --compartment-id <compartment-ocid>

oci os bucket create \
  --namespace <your-namespace> \
  --name health-platform-db-backups \
  --compartment-id <compartment-ocid>
```

### 2. Create OCI API Credentials

```bash
# Generate customer secret keys in OCI Console:
# Identity > Users > Your User > Customer Secret Keys > Generate Secret Key

# Save the access key and secret key
```

### 3. Configure Values

Create a `velero-values.yaml` file:

```yaml
oci:
  namespace: "your-oci-namespace"
  accessKeyId: "your-access-key"
  secretAccessKey: "your-secret-key"

velero:
  configuration:
    backupStorageLocation:
      config:
        s3Url: "https://your-oci-namespace.compat.objectstorage.eu-amsterdam-1.oraclecloud.com"
```

### 4. Install the Chart

```bash
# Add dependency repo
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm repo update

# Install Velero chart
helm install velero ./helm-charts/health-platform/charts/velero \
  --namespace velero \
  --create-namespace \
  --values velero-values.yaml
```

## Configuration

### Backup Schedules

| Schedule | Frequency | Retention | Description |
|----------|-----------|-----------|-------------|
| daily-full-backup | Daily at 2 AM | 30 days | Full cluster backup |
| health-data-backup | Every 6 hours | 7 days | Health data namespace |
| config-backup | Every hour | 7 days | ConfigMaps/Secrets only |

### Database Backups

PostgreSQL backups run separately as CronJobs:
- **Health Data DB**: Daily at 3 AM UTC
- **WebAuthn DB**: Daily at 3 AM UTC
- **Retention**: 7 days

### Storage Requirements

On OCI Always Free tier (50GB Object Storage):

| Component | Estimated Size | Frequency |
|-----------|----------------|-----------|
| Velero cluster backup | 2-5 GB | Daily |
| PostgreSQL health-data | 500 MB - 2 GB | Daily |
| PostgreSQL webauthn | 100 MB - 500 MB | Daily |
| MinIO buckets | 10-20 GB | Daily |
| **Total** | ~15-30 GB | - |

## Usage

### Manual Backup

```bash
# Create immediate backup
velero backup create manual-backup-$(date +%Y%m%d) \
  --include-namespaces health-api,health-auth,health-etl,health-data

# Check backup status
velero backup describe manual-backup-20250120

# View backup logs
velero backup logs manual-backup-20250120
```

### Restore Operations

```bash
# List available backups
velero backup get

# Restore entire cluster
velero restore create --from-backup daily-full-backup-20250120

# Restore specific namespace
velero restore create health-api-restore \
  --from-backup daily-full-backup-20250120 \
  --include-namespaces health-api

# Monitor restore
velero restore describe health-api-restore
velero restore logs health-api-restore
```

### Database Restore

```bash
# Scale down applications
kubectl scale deployment health-api --replicas=0 -n health-api

# Download backup from OCI
# (Use OCI console or CLI)

# Restore PostgreSQL
kubectl exec -it postgresql-health-primary-0 -n health-data -- bash
gunzip < /tmp/postgres-health-backup.sql.gz | pg_restore -U postgres -d healthdb

# Scale up applications
kubectl scale deployment health-api --replicas=2 -n health-api
```

## Monitoring

### Prometheus Metrics

Velero exposes Prometheus metrics for monitoring:

```promql
# Backup failures
velero_backup_failure_total

# Last successful backup timestamp
velero_backup_last_successful_timestamp

# Partial failures
velero_backup_partial_failure_total
```

### Alerts

Pre-configured Prometheus alerts:
- `VeleroBackupFailure`: Triggered when backup fails
- `VeleroBackupTooOld`: No successful backup in 24 hours
- `VeleroBackupPartialFailure`: Backup partially failed

## Disaster Recovery Procedures

### RTO/RPO Targets

| Scenario | RTO | RPO |
|----------|-----|-----|
| Resource deletion | 15 min | 1 hour |
| Database corruption | 30 min | 24 hours |
| Cluster failure | 2-4 hours | 24 hours |
| Region outage | 4-6 hours | 24 hours |

### DR Testing

Monthly DR drill:

```bash
# Create test namespace
kubectl create namespace dr-test

# Restore to test namespace
velero restore create dr-drill-$(date +%Y%m%d) \
  --from-backup daily-full-backup-latest \
  --namespace-mappings health-api:dr-test

# Verify
kubectl get all -n dr-test

# Cleanup
kubectl delete namespace dr-test
```

## Troubleshooting

### Velero Pod Not Starting

```bash
# Check logs
kubectl logs -n velero deployment/velero

# Verify credentials
kubectl get secret velero-oci-credentials -n velero -o yaml

# Test OCI connectivity
kubectl run -it --rm debug --image=amazon/aws-cli --restart=Never -- \
  s3 ls --endpoint-url=https://YOUR_NAMESPACE.compat.objectstorage.eu-amsterdam-1.oraclecloud.com
```

### Backup Failing

```bash
# Check backup details
velero backup describe <backup-name> --details

# View logs
velero backup logs <backup-name>

# Check storage location
kubectl get backupstoragelocation -n velero
```

### Restore Issues

```bash
# Check restore status
velero restore describe <restore-name> --details

# View logs
velero restore logs <restore-name>

# Check for conflicts
kubectl get all -n <namespace>
```

## Security

### Credentials Management

- Store OCI credentials in Kubernetes secrets
- Use RBAC to limit access to Velero namespace
- Rotate OCI access keys regularly
- Enable OCI bucket encryption

### Backup Encryption

Enable bucket-level encryption in OCI:

```bash
oci os bucket update \
  --namespace <namespace> \
  --name health-platform-velero-backups \
  --kms-key-id <kms-key-ocid>
```

## Cost Optimization

On OCI Always Free tier:
- 20 GB Object Storage (free)
- 10 GB Archive Storage (free)
- Optimize retention periods
- Compress database dumps
- Use incremental backups where possible

## Additional Resources

- [Velero Documentation](https://velero.io/docs/)
- [OCI Object Storage](https://docs.oracle.com/en-us/iaas/Content/Object/home.htm)
- [Disaster Recovery Runbook](../../../DISASTER-RECOVERY.md)

## Values

See [values.yaml](./values.yaml) for full configuration options.

## Support

For issues or questions, refer to the disaster recovery runbook or open an issue in the project repository.
