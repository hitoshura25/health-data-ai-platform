# Module 8: Disaster Recovery
## Velero Backups & Recovery Procedures

**Estimated Time:** 3 days
**Dependencies:** Modules 1-4 (All services deployed)
**Deliverables:** Automated backups and tested recovery procedures

---

## Objectives

Implement comprehensive disaster recovery:
1. Velero - Kubernetes backup and restore
2. PostgreSQL backups - Database-specific backups
3. Backup schedules - Automated daily backups
4. Restore procedures - Documented recovery steps
5. DR testing - Regular recovery drills

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                     │
│  ┌──────────────┐                                      │
│  │   Velero     │                                      │
│  │  Controller  │                                      │
│  └──────┬───────┘                                      │
│         │                                               │
│         ├─► Backs up:                                  │
│         │   - All Kubernetes resources                 │
│         │   - PersistentVolumes (with restic)         │
│         │   - Namespace configurations                 │
│         │                                               │
│         ▼                                               │
│  ┌──────────────┐                                      │
│  │ OCI Object   │                                      │
│  │  Storage     │ (Always Free tier: 20 GB)           │
│  │  Bucket      │                                      │
│  └──────────────┘                                      │
│                                                         │
│  ┌──────────────┐       ┌──────────────┐              │
│  │ PostgreSQL   │──────►│   CronJob    │              │
│  │  Instances   │       │  (pg_dump)   │              │
│  └──────────────┘       └──────┬───────┘              │
│                                  │                      │
│                                  ▼                      │
│                          OCI Object Storage            │
└────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Install Velero

**Install Velero CLI:**

```bash
# macOS
brew install velero

# Linux
wget https://github.com/vmware-tanzu/velero/releases/download/v1.12.0/velero-v1.12.0-linux-amd64.tar.gz
tar -xvf velero-v1.12.0-linux-amd64.tar.gz
sudo mv velero-v1.12.0-linux-amd64/velero /usr/local/bin/

# Verify
velero version --client-only
```

**Configure OCI Object Storage for Velero:**

```bash
# Create credentials file for OCI
cat > velero-oci-credentials <<EOF
[default]
tenancy=<TENANCY_OCID>
user=<USER_OCID>
fingerprint=<API_KEY_FINGERPRINT>
key_file=/credentials/oci_api_key.pem
region=eu-amsterdam-1
EOF

# Create secret with credentials
kubectl create secret generic oci-credentials \
  --namespace velero \
  --from-file=credentials=velero-oci-credentials \
  --from-file=key_file=~/.oci/oci_api_key.pem
```

**Install Velero in Cluster:**

```bash
# Install Velero with OCI plugin
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.8.0 \
  --bucket health-platform-prod-velero-backups \
  --secret-file ./velero-oci-credentials \
  --use-volume-snapshots=true \
  --use-restic \
  --backup-location-config \
    region=eu-amsterdam-1,\
    s3ForcePathStyle="true",\
    s3Url=https://<namespace>.compat.objectstorage.eu-amsterdam-1.oraclecloud.com

# Wait for Velero to be ready
kubectl wait --for=condition=available --timeout=300s \
  deployment/velero -n velero

# Verify
velero version
```

### Step 2: Create Backup Schedules

**Daily Full Backup:**

```yaml
# velero-schedule-daily.yaml
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: daily-backup
  namespace: velero
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  template:
    includedNamespaces:
    - health-api
    - health-auth
    - health-etl
    - health-data
    - health-observability

    excludedResources:
    - events
    - events.events.k8s.io

    includeClusterResources: true

    storageLocation: default

    volumeSnapshotLocations:
    - default

    ttl: 720h  # 30 days retention

    snapshotVolumes: true
    defaultVolumesToRestic: true

    hooks: {}
```

```bash
kubectl apply -f velero-schedule-daily.yaml
```

**Namespace-Specific Backups:**

```bash
# Backup health-data namespace (critical)
velero schedule create health-data-backup \
  --schedule="0 */6 * * *" \
  --include-namespaces health-data \
  --ttl 720h

# Backup configuration only (lightweight)
velero schedule create config-backup \
  --schedule="0 */1 * * *" \
  --include-resources configmap,secret,serviceaccount \
  --include-namespaces health-api,health-auth,health-etl \
  --ttl 168h
```

### Step 3: PostgreSQL-Specific Backups

**Create Backup CronJob:**

```yaml
# postgresql-backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgresql-backup
  namespace: health-data
spec:
  schedule: "0 3 * * *"  # 3 AM daily
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1

  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure

          containers:
          - name: pg-backup
            image: postgres:15-alpine
            command:
            - /bin/sh
            - -c
            - |
              set -e

              # Backup filename with timestamp
              BACKUP_FILE="postgres-health-$(date +%Y%m%d-%H%M%S).sql.gz"

              echo "Starting backup: $BACKUP_FILE"

              # Dump database
              PGPASSWORD=$POSTGRES_PASSWORD pg_dump \
                -h postgresql-health \
                -U healthapi \
                -d healthdb \
                --format=custom \
                | gzip > /tmp/$BACKUP_FILE

              # Upload to OCI Object Storage (using pre-authenticated request)
              curl -X PUT \
                --upload-file /tmp/$BACKUP_FILE \
                "$BACKUP_UPLOAD_URL/$BACKUP_FILE"

              echo "Backup completed: $BACKUP_FILE"

              # Cleanup old backups (keep last 7 days)
              # This would require oci CLI or custom script

            env:
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgresql-health-secret
                  key: password
            - name: BACKUP_UPLOAD_URL
              valueFrom:
                secretKeyRef:
                  name: backup-config
                  key: oci-upload-url
```

```bash
kubectl apply -f postgresql-backup-cronjob.yaml

# Trigger manual backup
kubectl create job --from=cronjob/postgresql-backup manual-backup-$(date +%s) -n health-data

# Check backup logs
kubectl logs job/manual-backup-xxx -n health-data
```

### Step 4: Create Restore Procedures

**Full Cluster Restore:**

```bash
# 1. List available backups
velero backup get

# Example output:
# NAME                          STATUS      CREATED                          EXPIRES
# daily-backup-20250119020000   Completed   2025-01-19 02:00:00 +0000 UTC   29d

# 2. Restore from backup
velero restore create --from-backup daily-backup-20250119020000

# 3. Monitor restore
velero restore describe <restore-name>
velero restore logs <restore-name>

# 4. Verify pods are running
kubectl get pods -A

# 5. Verify data integrity
kubectl exec -it postgresql-health-primary-0 -n health-data -- \
  psql -U healthapi -d healthdb -c "SELECT COUNT(*) FROM health_records;"
```

**Namespace-Specific Restore:**

```bash
# Restore only health-api namespace
velero restore create health-api-restore \
  --from-backup daily-backup-20250119020000 \
  --include-namespaces health-api

# Or restore specific resources
velero restore create --from-backup daily-backup-20250119020000 \
  --include-resources deployment,service,configmap \
  --namespace-mappings health-api:health-api-restored
```

**PostgreSQL Database Restore:**

```bash
# 1. Scale down applications using database
kubectl scale deployment health-api --replicas=0 -n health-api
kubectl scale deployment etl-engine --replicas=0 -n health-etl

# 2. Download backup from OCI Object Storage
# (Use OCI CLI or console)

# 3. Restore database
kubectl exec -it postgresql-health-primary-0 -n health-data -- bash

# Inside pod:
dropdb -U postgres healthdb
createdb -U postgres healthdb
gunzip < /tmp/postgres-health-20250119-030000.sql.gz | \
  pg_restore -U postgres -d healthdb

# 4. Verify restore
psql -U healthapi -d healthdb -c "SELECT COUNT(*) FROM health_records;"

# 5. Scale applications back up
kubectl scale deployment health-api --replicas=2 -n health-api
kubectl scale deployment etl-engine --replicas=1 -n health-etl
```

### Step 5: Disaster Recovery Runbook

**File: `docs/runbooks/disaster-recovery.md`**

```markdown
# Disaster Recovery Runbook

## Scenario 1: Accidental Resource Deletion

**Symptoms**: Pod/Deployment accidentally deleted

**Recovery**:
1. List recent backups: `velero backup get`
2. Restore: `velero restore create --from-backup <latest-backup>`
3. Monitor: `velero restore describe <restore-name>`
4. Verify: `kubectl get pods -A`

**RTO**: 15 minutes
**RPO**: Last hourly backup (max 1 hour data loss)

---

## Scenario 2: Database Corruption

**Symptoms**: Database errors, corrupted data

**Recovery**:
1. Scale down apps: `kubectl scale deployment health-api --replicas=0`
2. List PostgreSQL backups in OCI Object Storage
3. Download latest backup
4. Restore using pg_restore
5. Verify data: Run sample queries
6. Scale up apps

**RTO**: 30 minutes
**RPO**: Last daily PostgreSQL backup (max 24 hours data loss)

---

## Scenario 3: Complete Cluster Failure

**Symptoms**: Cluster unreachable, nodes down

**Recovery**:
1. Provision new OKE cluster with Terraform
2. Install Velero: `velero install ...`
3. Restore from backup: `velero restore create --from-backup <latest-backup>`
4. Verify all namespaces and resources
5. Update DNS to new cluster
6. Monitor for 24 hours

**RTO**: 2-4 hours
**RPO**: Last daily backup (max 24 hours data loss)

---

## Scenario 4: Region Outage (Oracle)

**Symptoms**: Entire region unavailable

**Recovery**:
1. Provision cluster in different region
2. Restore from OCI Object Storage backup (cross-region)
3. Update DNS to new region
4. Monitor traffic shift

**RTO**: 4-6 hours
**RPO**: Last backup sync (max 24 hours)
```

### Step 6: Test DR Procedures

**Monthly DR Drill:**

```bash
# Create test namespace for DR drill
kubectl create namespace dr-test

# Restore to test namespace
velero restore create dr-drill-$(date +%Y%m%d) \
  --from-backup daily-backup-latest \
  --namespace-mappings health-api:dr-test

# Verify restore
kubectl get all -n dr-test

# Test functionality
curl https://dr-test-api.yourdomain.com/health

# Cleanup
kubectl delete namespace dr-test
```

**Quarterly Full Cluster Rebuild:**

```bash
# Test complete cluster rebuild
# 1. Document current state
kubectl get all -A > cluster-state-before.txt

# 2. Destroy and rebuild cluster with Terraform
cd terraform/environments/production
terraform destroy -auto-approve
terraform apply -auto-approve

# 3. Install Velero
velero install ...

# 4. Restore everything
velero restore create full-restore --from-backup daily-backup-latest

# 5. Verify match
kubectl get all -A > cluster-state-after.txt
diff cluster-state-before.txt cluster-state-after.txt

# 6. Test all services
./scripts/integration-tests.sh
```

---

## Backup Verification

**Check Backup Status:**

```bash
# List all backups
velero backup get

# Check backup details
velero backup describe daily-backup-20250119020000

# Download backup logs
velero backup logs daily-backup-20250119020000

# Verify backup size
kubectl exec -it velero-xxx -n velero -- \
  ls -lh /backups/
```

**Automated Backup Verification:**

```yaml
# backup-verification-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup-verification
  namespace: velero
spec:
  schedule: "0 4 * * *"  # Daily at 4 AM
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: verify
            image: bitnami/kubectl:latest
            command:
            - /bin/sh
            - -c
            - |
              # Get latest backup
              LATEST_BACKUP=$(velero backup get --output json | \
                jq -r '.items[0].metadata.name')

              # Check backup status
              STATUS=$(velero backup describe $LATEST_BACKUP --output json | \
                jq -r '.status.phase')

              if [ "$STATUS" != "Completed" ]; then
                echo "ERROR: Latest backup failed: $LATEST_BACKUP"
                exit 1
              fi

              echo "SUCCESS: Latest backup verified: $LATEST_BACKUP"
```

---

## Success Criteria

- [ ] Velero installed and configured
- [ ] Daily automated backups running
- [ ] PostgreSQL backups to OCI Object Storage
- [ ] Backups stored in multiple locations (cluster + object storage)
- [ ] Restore procedures documented
- [ ] DR runbook created
- [ ] Quarterly DR drills scheduled
- [ ] Backup verification automated
- [ ] RTO < 2 hours tested
- [ ] RPO < 24 hours achieved
- [ ] Team trained on recovery procedures

---

## Monitoring & Alerts

**Prometheus Alerts for Backups:**

```yaml
# backup-alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: backup-alerts
  namespace: velero
spec:
  groups:
  - name: velero
    interval: 30s
    rules:
    - alert: VeleroBackupFailed
      expr: velero_backup_failure_total > 0
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "Velero backup failed"

    - alert: VeleroBackupTooOld
      expr: time() - velero_backup_last_successful_timestamp > 86400
      for: 1h
      labels:
        severity: warning
      annotations:
        summary: "No successful backup in 24 hours"
```

---

**Module 8 Complete**: Disaster recovery fully implemented
