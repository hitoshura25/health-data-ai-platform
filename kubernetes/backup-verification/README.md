# Backup Verification

Automated backup verification for the Health Data AI Platform disaster recovery system.

## Overview

The backup verification CronJob runs daily to ensure all backups are:
- Created successfully
- Recent (within expected time windows)
- Complete and not corrupted
- Accessible for restore operations

## Verification Schedule

**CronJob**: `backup-verification`
**Schedule**: Daily at 6:00 AM UTC
**Namespace**: `velero`

The verification runs after all backup jobs complete:
- Velero full backup: 2 AM UTC
- PostgreSQL backups: 3 AM UTC
- MinIO backup: 4 AM UTC
- RabbitMQ backup: 5 AM UTC
- Verification: 6 AM UTC ✓

## What Gets Verified

### Velero Backups

✓ Daily full backup exists and completed successfully
✓ Health data namespace backup (6-hour interval) is recent
✓ Config backup (hourly) is recent
✓ No errors or warnings in backup status
✓ Backup contains expected number of resources

### Database Backups

✓ PostgreSQL health-data backup job ran successfully
✓ PostgreSQL auth backup job ran successfully
✓ MinIO backup job completed
✓ RabbitMQ backup job completed
✓ All backups completed within expected timeframes

## Deployment

### Prerequisites

- Velero installed and configured
- Backup CronJobs deployed
- RBAC permissions configured

### Deploy Verification Job

```bash
# Apply verification CronJob
kubectl apply -f verify-backups.yaml

# Verify deployment
kubectl get cronjob backup-verification -n velero
kubectl get serviceaccount backup-verification -n velero
kubectl get clusterrole backup-verification
kubectl get clusterrolebinding backup-verification
```

## Manual Verification

Trigger verification manually:

```bash
# Create manual verification job
kubectl create job --from=cronjob/backup-verification \
    verify-manual-$(date +%s) -n velero

# Monitor verification
kubectl get jobs -n velero -l app=backup-verification

# View verification results
kubectl logs -n velero job/verify-manual-xxxxx

# Example output:
# ===========================================
# Backup Verification
# Started at: Mon Jan 20 06:00:00 UTC 2025
# ===========================================
#
# Checking backup: daily-full-backup-20250120020000
# Backup age: 4 hours
# Backup status: Completed
# Items backed up: 1247
# ✓ Backup verification passed
#
# ...
#
# ===========================================
# Verification Summary
# ===========================================
# ✓ All backup verifications passed
# Finished at: Mon Jan 20 06:05:23 UTC 2025
```

## Verification Criteria

### Velero Backup Checks

| Check | Threshold | Description |
|-------|-----------|-------------|
| Daily full backup age | < 25 hours | Should run daily at 2 AM |
| Health data backup age | < 7 hours | Should run every 6 hours |
| Config backup age | < 2 hours | Should run hourly |
| Backup status | "Completed" | No failures or partial failures |
| Backup errors | 0 | No errors during backup |
| Backup size | > 0 items | Backup contains resources |

### Database Backup Checks

| Check | Threshold | Description |
|-------|-----------|-------------|
| PostgreSQL health backup | < 2 days | CronJob last success time |
| PostgreSQL auth backup | < 2 days | CronJob last success time |
| MinIO backup | < 2 days | CronJob last success time |
| RabbitMQ backup | < 2 days | CronJob last success time |

## Monitoring & Alerts

### Prometheus Metrics

The verification job can be monitored via Prometheus:

```promql
# Verification job failures
kube_job_status_failed{job="backup-verification"} > 0

# Time since last successful verification
time() - kube_job_status_completion_time{job="backup-verification"} > 86400
```

### Grafana Dashboard

View backup verification status in Grafana:

```bash
# Port-forward to Grafana
kubectl port-forward -n health-observability svc/grafana 3000:3000

# Navigate to "Disaster Recovery" dashboard
# Check "Backup Verification" panel
```

### Alerts

Configure alerts for backup verification failures:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: backup-verification-alerts
  namespace: velero
spec:
  groups:
  - name: backup-verification
    rules:
    - alert: BackupVerificationFailed
      expr: kube_job_status_failed{job="backup-verification"} > 0
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "Backup verification failed"
        description: "The automated backup verification job has failed"

    - alert: BackupVerificationNotRun
      expr: time() - kube_job_status_completion_time{job="backup-verification"} > 86400
      for: 1h
      labels:
        severity: warning
      annotations:
        summary: "Backup verification has not run in 24 hours"
        description: "Verification job may be stuck or disabled"
```

## Alert Webhooks

Configure webhook notifications for verification failures:

```bash
# Create secret with webhook URL (Slack, Teams, Discord, etc.)
kubectl create secret generic backup-verification-webhook \
    --from-literal=webhook-url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
    -n velero

# Update verification CronJob to call webhook on failure
# (See alert-webhook.sh in ConfigMap)
```

## Verification Results

### Check Recent Verifications

```bash
# List verification jobs (last 7 days)
kubectl get jobs -n velero -l app=backup-verification --sort-by=.status.startTime

# Check success rate
kubectl get jobs -n velero -l app=backup-verification -o json | \
    jq '.items | group_by(.status.succeeded == 1) |
        {successful: (.[0] | length), failed: (.[1] // [] | length)}'

# View logs from last 5 verifications
for JOB in $(kubectl get jobs -n velero -l app=backup-verification --sort-by=.status.startTime -o name | tail -5); do
    echo "=== ${JOB} ==="
    kubectl logs -n velero ${JOB}
    echo ""
done
```

### Verification History Report

```bash
# Generate verification history report
kubectl get jobs -n velero -l app=backup-verification -o json | \
    jq -r '.items[] |
    {
        name: .metadata.name,
        start: .status.startTime,
        completion: .status.completionTime,
        succeeded: .status.succeeded,
        failed: .status.failed
    } |
    [.name, .start, .completion, .succeeded, .failed] |
    @tsv' | column -t
```

## Testing

### Test Verification Logic

```bash
# Create a test backup
velero backup create test-backup-$(date +%Y%m%d) \
    --include-namespaces health-api \
    --wait

# Run verification
kubectl create job --from=cronjob/backup-verification \
    verify-test-$(date +%s) -n velero

# Check results
kubectl logs -n velero job/verify-test-xxxxx

# Cleanup test backup
velero backup delete test-backup-$(date +%Y%m%d) --confirm
```

### Simulate Backup Failure

```bash
# Temporarily disable a backup schedule
velero schedule pause daily-full-backup

# Wait 25 hours (or adjust verification script thresholds)

# Run verification - should detect old backup
kubectl create job --from=cronjob/backup-verification \
    verify-failure-test-$(date +%s) -n velero

# Check logs - should show error
kubectl logs -n velero job/verify-failure-test-xxxxx | grep "✗"

# Re-enable backup schedule
velero schedule unpause daily-full-backup
```

## Troubleshooting

### Verification Job Not Running

```bash
# Check CronJob exists and is enabled
kubectl get cronjob backup-verification -n velero

# Check CronJob schedule
kubectl get cronjob backup-verification -n velero -o jsonpath='{.spec.schedule}'

# Check for suspended CronJob
kubectl get cronjob backup-verification -n velero -o jsonpath='{.spec.suspend}'

# Manual trigger
kubectl create job --from=cronjob/backup-verification test-$(date +%s) -n velero
```

### Verification Failing

```bash
# Check which backups are failing
kubectl logs -n velero $(kubectl get pods -n velero -l app=backup-verification -o name | tail -1) | grep "✗"

# List all Velero backups
velero backup get

# Check backup details
velero backup describe <backup-name> --details

# Check database backup jobs
kubectl get jobs -n health-data -l app=postgresql-backup
kubectl get jobs -n health-auth -l app=postgresql-backup
```

### RBAC Issues

```bash
# Check ServiceAccount exists
kubectl get serviceaccount backup-verification -n velero

# Check ClusterRole
kubectl get clusterrole backup-verification -o yaml

# Check ClusterRoleBinding
kubectl get clusterrolebinding backup-verification -o yaml

# Test permissions manually
kubectl auth can-i get backups.velero.io --as=system:serviceaccount:velero:backup-verification -n velero
kubectl auth can-i list cronjobs.batch --as=system:serviceaccount:velero:backup-verification -n health-data
```

## Customization

### Adjust Verification Thresholds

Edit the verification script in the ConfigMap:

```bash
# Edit verification script
kubectl edit configmap backup-verification-script -n velero

# Adjust these values:
# - Daily backup age threshold (currently 25 hours)
# - Health data backup age threshold (currently 7 hours)
# - Config backup age threshold (currently 2 hours)
# - Database backup age threshold (currently 2 days)

# Restart verification to use new thresholds
kubectl rollout restart deployment/backup-verification -n velero
```

### Add Custom Checks

Extend the verification script with custom checks:

```bash
# Example: Verify backup size is within expected range
check_backup_size() {
    local backup_name=$1
    local min_size_mb=$2
    local max_size_mb=$3

    BACKUP_SIZE=$(velero backup describe ${backup_name} -o json | \
        jq -r '.status.progress.totalItems')

    if [ ${BACKUP_SIZE} -lt ${min_size_mb} ] || [ ${BACKUP_SIZE} -gt ${max_size_mb} ]; then
        echo "ERROR: Backup size ${BACKUP_SIZE} outside expected range"
        return 1
    fi

    return 0
}

# Example: Verify backup in OCI Object Storage
check_backup_in_oci() {
    local backup_name=$1

    # Use OCI CLI to verify backup exists
    oci os object head \
        --namespace <NAMESPACE> \
        --bucket-name health-platform-velero-backups \
        --name velero/${backup_name}

    return $?
}
```

## Best Practices

1. **Monitor Verification Results**
   - Set up alerts for verification failures
   - Review verification logs regularly
   - Track verification success rate

2. **Test Regularly**
   - Run manual verifications after changes
   - Test failure scenarios
   - Document verification issues

3. **Keep Scripts Updated**
   - Update thresholds as backup schedules change
   - Add checks for new backup types
   - Improve error messages

4. **Integrate with Monitoring**
   - Export metrics to Prometheus
   - Create Grafana dashboards
   - Set up alert channels (Slack, email, PagerDuty)

## Additional Resources

- [Disaster Recovery Runbook](../../DISASTER-RECOVERY.md)
- [Backup Jobs](../backup-jobs/)
- [Backup/Restore Scripts](../../scripts/backup-restore/)
- [Velero Documentation](https://velero.io/docs/)

## Support

For issues with backup verification:
1. Check verification logs
2. Verify RBAC permissions
3. Test backup commands manually
4. Review disaster recovery runbook
5. Open an issue in the project repository
