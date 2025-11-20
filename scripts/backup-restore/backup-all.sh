#!/bin/bash
# Manual backup script for all components
# Usage: ./backup-all.sh

set -e

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_NAME="manual-backup-${TIMESTAMP}"

echo "==========================================="
echo "Health Data AI Platform - Full Backup"
echo "Backup name: ${BACKUP_NAME}"
echo "Started at: $(date)"
echo "==========================================="

# Check if velero is installed
if ! command -v velero &> /dev/null; then
    echo "ERROR: velero CLI not found. Please install velero."
    echo "https://velero.io/docs/main/basic-install/"
    exit 1
fi

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo "ERROR: kubectl not configured or cluster not accessible"
    exit 1
fi

echo ""
echo "Step 1: Creating Velero backup..."
echo "-------------------------------------------"

velero backup create "${BACKUP_NAME}" \
    --include-namespaces health-api,health-auth,health-etl,health-data,health-observability \
    --include-cluster-resources=true \
    --snapshot-volumes=true \
    --default-volumes-to-restic=true \
    --wait

echo ""
echo "Step 2: Triggering database backups..."
echo "-------------------------------------------"

# Trigger PostgreSQL health-data backup
echo "Triggering PostgreSQL health-data backup..."
kubectl create job "postgresql-health-manual-${TIMESTAMP}" \
    --from=cronjob/postgresql-health-backup \
    -n health-data

# Trigger PostgreSQL auth backup
echo "Triggering PostgreSQL auth backup..."
kubectl create job "postgresql-auth-manual-${TIMESTAMP}" \
    --from=cronjob/postgresql-auth-backup \
    -n health-auth

# Trigger MinIO backup
echo "Triggering MinIO backup..."
kubectl create job "minio-manual-${TIMESTAMP}" \
    --from=cronjob/minio-backup \
    -n health-data

# Trigger RabbitMQ backup
echo "Triggering RabbitMQ backup..."
kubectl create job "rabbitmq-manual-${TIMESTAMP}" \
    --from=cronjob/rabbitmq-backup \
    -n health-data

echo ""
echo "Step 3: Waiting for backup jobs to complete..."
echo "-------------------------------------------"

# Wait for jobs to complete (timeout: 10 minutes)
for JOB in "postgresql-health-manual-${TIMESTAMP}" "postgresql-auth-manual-${TIMESTAMP}" "minio-manual-${TIMESTAMP}" "rabbitmq-manual-${TIMESTAMP}"; do
    NAMESPACE="health-data"
    if [[ "${JOB}" == *"auth"* ]]; then
        NAMESPACE="health-auth"
    fi

    echo "Waiting for ${JOB} in namespace ${NAMESPACE}..."
    kubectl wait --for=condition=complete --timeout=600s "job/${JOB}" -n "${NAMESPACE}" || {
        echo "WARNING: Job ${JOB} did not complete in time"
        kubectl logs "job/${JOB}" -n "${NAMESPACE}" --tail=50
    }
done

echo ""
echo "Step 4: Verifying backups..."
echo "-------------------------------------------"

# Verify Velero backup
velero backup describe "${BACKUP_NAME}"

# Check backup status
BACKUP_STATUS=$(velero backup get "${BACKUP_NAME}" -o json | jq -r '.status.phase')

if [ "${BACKUP_STATUS}" != "Completed" ]; then
    echo "ERROR: Backup status is ${BACKUP_STATUS}"
    velero backup logs "${BACKUP_NAME}"
    exit 1
fi

echo ""
echo "==========================================="
echo "✓ Full backup completed successfully"
echo "==========================================="
echo ""
echo "Backup details:"
echo "  Name: ${BACKUP_NAME}"
echo "  Status: ${BACKUP_STATUS}"
echo "  Timestamp: ${TIMESTAMP}"
echo ""
echo "To restore this backup:"
echo "  velero restore create --from-backup ${BACKUP_NAME}"
echo ""
echo "To view backup details:"
echo "  velero backup describe ${BACKUP_NAME}"
echo ""
echo "To download backup logs:"
echo "  velero backup logs ${BACKUP_NAME}"
echo ""
