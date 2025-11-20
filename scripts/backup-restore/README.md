# Backup and Restore Scripts

Manual backup and restore scripts for the Health Data AI Platform Kubernetes deployment.

## Prerequisites

- `kubectl` configured and connected to cluster
- `velero` CLI installed (for Velero operations)
- Appropriate RBAC permissions
- Access to OCI Object Storage (for database backups)

## Scripts Overview

| Script | Purpose | Usage |
|--------|---------|-------|
| `backup-all.sh` | Create full backup of all components | `./backup-all.sh` |
| `restore-cluster.sh` | Restore entire cluster from backup | `./restore-cluster.sh <backup-name>` |
| `restore-database.sh` | Restore specific database | `./restore-database.sh <db-type> <backup-file>` |
| `list-backups.sh` | List all available backups | `./list-backups.sh` |

## Usage Examples

### Create Full Backup

```bash
# Create immediate backup of all components
./backup-all.sh

# This will:
# 1. Create Velero backup of all Kubernetes resources
# 2. Trigger database backup jobs
# 3. Wait for all backups to complete
# 4. Verify backup success
```

### List Backups

```bash
# View all available backups
./list-backups.sh

# Shows:
# - Velero backups
# - Recent database backup jobs
# - Backup verification status
```

### Restore Entire Cluster

```bash
# List available backups
velero backup get

# Restore from a specific backup
./restore-cluster.sh daily-full-backup-20250120020000

# This will:
# 1. Restore all Kubernetes resources
# 2. Restore PersistentVolumes
# 3. Wait for pods to be ready
# 4. Verify key services are running
```

### Restore Specific Database

```bash
# Restore health data database
./restore-database.sh health-data postgres-health-20250120-030000.sql.gz

# Restore auth database
./restore-database.sh auth postgres-auth-20250120-030000.sql.gz

# Restore RabbitMQ definitions
./restore-database.sh rabbitmq rabbitmq-definitions-20250120-050000.json.gz
```

## Database Types

### health-data
PostgreSQL database containing health records and analytics data.

- **Namespace**: `health-data`
- **Pod**: `postgresql-health-primary-0`
- **Database**: `healthdb`
- **User**: `healthapi`
- **Applications**: health-api, etl-engine

### auth
PostgreSQL database containing WebAuthn credentials and sessions.

- **Namespace**: `health-auth`
- **Pod**: `postgresql-auth-primary-0`
- **Database**: `webauthn`
- **User**: `webauthn`
- **Applications**: webauthn-server, envoy-gateway

### minio
MinIO S3-compatible data lake with health data buckets.

- **Namespace**: `health-data`
- **Buckets**: raw-health-data, processed-data, clinical-narratives, model-artifacts
- **Note**: Restore not yet automated, use mc tool

### rabbitmq
RabbitMQ message queue definitions (queues, exchanges, bindings).

- **Namespace**: `health-data`
- **Pod**: Auto-detected
- **API**: Management API on port 15672

## Disaster Recovery Scenarios

### Scenario 1: Accidental Resource Deletion

**Problem**: Deployment or ConfigMap accidentally deleted

**Solution**:
```bash
# List recent backups
velero backup get

# Restore specific resource type
velero restore create --from-backup daily-full-backup-latest \
    --include-resources deployment,configmap \
    --include-namespaces health-api
```

**RTO**: 15 minutes
**RPO**: 1 hour (hourly config backups)

### Scenario 2: Database Corruption

**Problem**: Database errors, corrupted data

**Solution**:
```bash
# Download latest backup from OCI Object Storage
# (Use OCI console or CLI)

# Restore database
./restore-database.sh health-data postgres-health-20250120-030000.sql.gz

# Verify data integrity
kubectl exec -n health-data postgresql-health-primary-0 -- \
    psql -U healthapi -d healthdb -c "SELECT COUNT(*) FROM health_records;"
```

**RTO**: 30 minutes
**RPO**: 24 hours (daily backups)

### Scenario 3: Complete Cluster Failure

**Problem**: Cluster unreachable, multiple node failures

**Solution**:
```bash
# 1. Provision new cluster with Terraform
cd terraform/environments/production
terraform apply -auto-approve

# 2. Install Velero (configure OCI credentials first)
cd ../../../kubernetes
helm install velero ../helm-charts/health-platform/charts/velero \
    --namespace velero \
    --create-namespace \
    -f velero-production-values.yaml

# 3. Wait for Velero to sync backups from OCI
kubectl wait --for=condition=available --timeout=300s deployment/velero -n velero

# 4. Restore cluster
cd ../scripts/backup-restore
./restore-cluster.sh daily-full-backup-latest

# 5. Update DNS to new cluster
# (Manual step - update DNS records)
```

**RTO**: 2-4 hours
**RPO**: 24 hours

### Scenario 4: Namespace-Specific Restore

**Problem**: Need to restore only specific namespace

**Solution**:
```bash
# Restore only health-api namespace
velero restore create health-api-restore \
    --from-backup daily-full-backup-20250120020000 \
    --include-namespaces health-api

# Monitor restore
velero restore describe health-api-restore
velero restore logs health-api-restore
```

## Backup Verification

### Manual Verification

```bash
# Check latest backup status
velero backup describe $(velero backup get -o json | jq -r '.items[0].metadata.name')

# Verify database backups
kubectl get jobs -n health-data -l app=postgresql-backup --sort-by=.status.startTime

# Check backup sizes in OCI Object Storage
# (Use OCI console)
```

### Automated Verification

```bash
# Trigger backup verification job
kubectl create job --from=cronjob/backup-verification \
    verify-manual-$(date +%s) -n velero

# Check verification logs
kubectl logs -n velero job/verify-manual-xxxxx
```

## Troubleshooting

### Velero Backup Failing

```bash
# Check Velero logs
kubectl logs -n velero deployment/velero

# Check backup status
velero backup describe <backup-name> --details

# View backup logs
velero backup logs <backup-name>

# Verify OCI credentials
kubectl get secret velero-oci-credentials -n velero -o yaml
```

### Database Backup Job Failing

```bash
# Check CronJob configuration
kubectl get cronjob postgresql-health-backup -n health-data -o yaml

# View recent job logs
kubectl logs -n health-data $(kubectl get pods -n health-data -l app=postgresql-backup --sort-by=.status.startTime -o jsonpath='{.items[-1].metadata.name}')

# Check secrets
kubectl get secret postgresql-health-secret -n health-data
kubectl get secret backup-oci-config -n health-data
```

### Restore Failing

```bash
# Check restore status
velero restore describe <restore-name> --details

# View restore logs
velero restore logs <restore-name>

# Check for resource conflicts
kubectl get all -n <namespace>

# Delete conflicting resources if needed
kubectl delete deployment <name> -n <namespace>
```

## Best Practices

1. **Test Restores Regularly**
   - Monthly DR drills to test restore procedures
   - Verify data integrity after restore
   - Document any issues or improvements

2. **Monitor Backup Status**
   - Check automated verification job results
   - Set up alerts for backup failures
   - Review backup sizes and retention

3. **Keep Scripts Updated**
   - Update credentials when rotated
   - Adjust resource names if changed
   - Document any customizations

4. **Secure Backup Access**
   - Limit access to backup scripts
   - Rotate OCI credentials regularly
   - Use RBAC to restrict backup operations

5. **Document Changes**
   - Update DISASTER-RECOVERY.md after infrastructure changes
   - Keep runbooks current
   - Train team on procedures

## Additional Resources

- [Velero Documentation](https://velero.io/docs/)
- [OCI Object Storage](https://docs.oracle.com/en-us/iaas/Content/Object/home.htm)
- [Disaster Recovery Runbook](../../DISASTER-RECOVERY.md)
- [Kubernetes Backup Best Practices](https://kubernetes.io/docs/tasks/administer-cluster/backup/)

## Support

For issues or questions:
1. Check the disaster recovery runbook
2. Review Velero logs
3. Open an issue in the project repository
