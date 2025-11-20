#!/bin/bash
# Cluster restore script
# Usage: ./restore-cluster.sh <backup-name>

set -e

BACKUP_NAME="${1}"

if [ -z "${BACKUP_NAME}" ]; then
    echo "ERROR: Backup name required"
    echo "Usage: ./restore-cluster.sh <backup-name>"
    echo ""
    echo "Available backups:"
    velero backup get
    exit 1
fi

echo "==========================================="
echo "Health Data AI Platform - Cluster Restore"
echo "Backup: ${BACKUP_NAME}"
echo "Started at: $(date)"
echo "==========================================="

# Verify backup exists
if ! velero backup get "${BACKUP_NAME}" &> /dev/null; then
    echo "ERROR: Backup '${BACKUP_NAME}' not found"
    echo ""
    echo "Available backups:"
    velero backup get
    exit 1
fi

# Show backup details
echo ""
echo "Backup details:"
echo "-------------------------------------------"
velero backup describe "${BACKUP_NAME}"

# Confirmation prompt
echo ""
echo "⚠️  WARNING: This will restore the entire cluster from backup"
echo "   This may overwrite existing resources"
echo ""
read -p "Continue with restore? (yes/no): " CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

RESTORE_NAME="restore-${BACKUP_NAME}-$(date +%Y%m%d-%H%M%S)"

echo ""
echo "Step 1: Creating Velero restore..."
echo "-------------------------------------------"

velero restore create "${RESTORE_NAME}" \
    --from-backup "${BACKUP_NAME}" \
    --wait

echo ""
echo "Step 2: Monitoring restore progress..."
echo "-------------------------------------------"

# Check restore status
RESTORE_STATUS=$(velero restore get "${RESTORE_NAME}" -o json | jq -r '.status.phase')

echo "Restore status: ${RESTORE_STATUS}"

if [ "${RESTORE_STATUS}" != "Completed" ]; then
    echo "WARNING: Restore status is ${RESTORE_STATUS}"
    echo ""
    echo "Restore logs:"
    velero restore logs "${RESTORE_NAME}"
fi

echo ""
echo "Step 3: Verifying pods are running..."
echo "-------------------------------------------"

# Wait for pods to be ready
NAMESPACES="health-api health-auth health-etl health-data health-observability"

for NS in ${NAMESPACES}; do
    echo "Checking namespace: ${NS}"
    kubectl wait --for=condition=ready pod --all -n "${NS}" --timeout=300s || {
        echo "WARNING: Some pods in ${NS} are not ready"
        kubectl get pods -n "${NS}"
    }
done

echo ""
echo "Step 4: Verifying services..."
echo "-------------------------------------------"

# Check key services
echo "PostgreSQL health-data:"
kubectl exec -n health-data postgresql-health-primary-0 -- \
    psql -U healthapi -d healthdb -c "SELECT version();" || echo "WARNING: Health DB not accessible"

echo ""
echo "PostgreSQL auth:"
kubectl exec -n health-auth postgresql-auth-primary-0 -- \
    psql -U webauthn -d webauthn -c "SELECT version();" || echo "WARNING: Auth DB not accessible"

echo ""
echo "MinIO:"
kubectl exec -n health-data deploy/minio -- \
    mc alias set local http://localhost:9000 "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" || echo "WARNING: MinIO not accessible"

echo ""
echo "RabbitMQ:"
kubectl exec -n health-data deploy/rabbitmq -- rabbitmqctl status || echo "WARNING: RabbitMQ not accessible"

echo ""
echo "==========================================="
echo "✓ Cluster restore completed"
echo "==========================================="
echo ""
echo "Restore details:"
echo "  Name: ${RESTORE_NAME}"
echo "  Status: ${RESTORE_STATUS}"
echo "  From backup: ${BACKUP_NAME}"
echo ""
echo "To view restore details:"
echo "  velero restore describe ${RESTORE_NAME}"
echo ""
echo "To download restore logs:"
echo "  velero restore logs ${RESTORE_NAME}"
echo ""
echo "Next steps:"
echo "  1. Verify application functionality"
echo "  2. Check data integrity"
echo "  3. Monitor logs for errors"
echo "  4. Update DNS if needed"
echo ""
