#!/bin/bash
# Database restore script
# Usage: ./restore-database.sh <database-type> <backup-file>
# Example: ./restore-database.sh health-data postgres-health-20250120-030000.sql.gz

set -e

DB_TYPE="${1}"
BACKUP_FILE="${2}"

if [ -z "${DB_TYPE}" ] || [ -z "${BACKUP_FILE}" ]; then
    echo "ERROR: Missing required arguments"
    echo "Usage: ./restore-database.sh <database-type> <backup-file>"
    echo ""
    echo "Database types:"
    echo "  health-data   - Health data PostgreSQL database"
    echo "  auth          - WebAuthn auth PostgreSQL database"
    echo "  minio         - MinIO data lake buckets"
    echo "  rabbitmq      - RabbitMQ definitions"
    echo ""
    exit 1
fi

echo "==========================================="
echo "Database Restore"
echo "Type: ${DB_TYPE}"
echo "Backup file: ${BACKUP_FILE}"
echo "Started at: $(date)"
echo "==========================================="

# Confirmation prompt
echo ""
echo "⚠️  WARNING: This will restore the database from backup"
echo "   Existing data may be overwritten"
echo ""
read -p "Continue with restore? (yes/no): " CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

case "${DB_TYPE}" in
    health-data)
        echo ""
        echo "Restoring Health Data PostgreSQL..."
        echo "-------------------------------------------"

        NAMESPACE="health-data"
        POD="postgresql-health-primary-0"
        DB_NAME="healthdb"
        DB_USER="healthapi"

        # Scale down applications
        echo "Step 1: Scaling down applications..."
        kubectl scale deployment health-api --replicas=0 -n health-api || true
        kubectl scale deployment etl-engine --replicas=0 -n health-etl || true

        # Copy backup file to pod
        echo "Step 2: Uploading backup file..."
        kubectl cp "${BACKUP_FILE}" "${NAMESPACE}/${POD}:/tmp/backup.dump"

        # Restore database
        echo "Step 3: Restoring database..."
        kubectl exec -n "${NAMESPACE}" "${POD}" -- bash -c "
            set -e
            echo 'Dropping existing database...'
            psql -U postgres -c 'DROP DATABASE IF EXISTS ${DB_NAME};'

            echo 'Creating new database...'
            psql -U postgres -c 'CREATE DATABASE ${DB_NAME};'

            echo 'Restoring from backup...'
            pg_restore -U postgres -d ${DB_NAME} --no-owner --no-acl --verbose /tmp/backup.dump

            echo 'Granting permissions...'
            psql -U postgres -d ${DB_NAME} -c 'GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};'
            psql -U postgres -d ${DB_NAME} -c 'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};'

            echo 'Cleaning up...'
            rm -f /tmp/backup.dump

            echo 'Verifying restore...'
            psql -U ${DB_USER} -d ${DB_NAME} -c 'SELECT COUNT(*) FROM information_schema.tables;'
        "

        # Scale up applications
        echo "Step 4: Scaling up applications..."
        kubectl scale deployment health-api --replicas=2 -n health-api
        kubectl scale deployment etl-engine --replicas=1 -n health-etl

        echo ""
        echo "✓ Health data database restored successfully"
        ;;

    auth)
        echo ""
        echo "Restoring WebAuthn Auth PostgreSQL..."
        echo "-------------------------------------------"

        NAMESPACE="health-auth"
        POD="postgresql-auth-primary-0"
        DB_NAME="webauthn"
        DB_USER="webauthn"

        # Scale down applications
        echo "Step 1: Scaling down applications..."
        kubectl scale deployment webauthn-server --replicas=0 -n health-auth || true
        kubectl scale deployment envoy-gateway --replicas=0 -n health-auth || true

        # Copy backup file to pod
        echo "Step 2: Uploading backup file..."
        kubectl cp "${BACKUP_FILE}" "${NAMESPACE}/${POD}:/tmp/backup.dump"

        # Restore database
        echo "Step 3: Restoring database..."
        kubectl exec -n "${NAMESPACE}" "${POD}" -- bash -c "
            set -e
            echo 'Dropping existing database...'
            psql -U postgres -c 'DROP DATABASE IF EXISTS ${DB_NAME};'

            echo 'Creating new database...'
            psql -U postgres -c 'CREATE DATABASE ${DB_NAME};'

            echo 'Restoring from backup...'
            pg_restore -U postgres -d ${DB_NAME} --no-owner --no-acl --verbose /tmp/backup.dump

            echo 'Granting permissions...'
            psql -U postgres -d ${DB_NAME} -c 'GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};'
            psql -U postgres -d ${DB_NAME} -c 'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};'

            echo 'Cleaning up...'
            rm -f /tmp/backup.dump

            echo 'Verifying restore...'
            psql -U ${DB_USER} -d ${DB_NAME} -c 'SELECT COUNT(*) FROM information_schema.tables;'
        "

        # Scale up applications
        echo "Step 4: Scaling up applications..."
        kubectl scale deployment webauthn-server --replicas=2 -n health-auth
        kubectl scale deployment envoy-gateway --replicas=2 -n health-auth

        echo ""
        echo "✓ Auth database restored successfully"
        ;;

    minio)
        echo ""
        echo "Restoring MinIO data lake..."
        echo "-------------------------------------------"
        echo "ERROR: MinIO restore not yet implemented"
        echo "Please use the MinIO mc tool to restore from OCI Object Storage"
        exit 1
        ;;

    rabbitmq)
        echo ""
        echo "Restoring RabbitMQ definitions..."
        echo "-------------------------------------------"

        NAMESPACE="health-data"
        POD=$(kubectl get pod -n "${NAMESPACE}" -l app.kubernetes.io/name=rabbitmq -o jsonpath='{.items[0].metadata.name}')

        if [ -z "${POD}" ]; then
            echo "ERROR: RabbitMQ pod not found"
            exit 1
        fi

        # Get RabbitMQ credentials
        RABBITMQ_USER=$(kubectl get secret rabbitmq-secret -n "${NAMESPACE}" -o jsonpath='{.data.rabbitmq-username}' | base64 -d)
        RABBITMQ_PASSWORD=$(kubectl get secret rabbitmq-secret -n "${NAMESPACE}" -o jsonpath='{.data.rabbitmq-password}' | base64 -d)

        # Extract definitions if compressed
        if [[ "${BACKUP_FILE}" == *.gz ]]; then
            gunzip -c "${BACKUP_FILE}" > /tmp/rabbitmq-definitions.json
            DEFINITIONS_FILE="/tmp/rabbitmq-definitions.json"
        else
            DEFINITIONS_FILE="${BACKUP_FILE}"
        fi

        # Import definitions
        echo "Importing RabbitMQ definitions..."
        kubectl cp "${DEFINITIONS_FILE}" "${NAMESPACE}/${POD}:/tmp/definitions.json"

        kubectl exec -n "${NAMESPACE}" "${POD}" -- \
            curl -u "${RABBITMQ_USER}:${RABBITMQ_PASSWORD}" \
            -H "content-type:application/json" \
            -X POST \
            --data-binary "@/tmp/definitions.json" \
            "http://localhost:15672/api/definitions"

        # Cleanup
        kubectl exec -n "${NAMESPACE}" "${POD}" -- rm -f /tmp/definitions.json
        [ -f /tmp/rabbitmq-definitions.json ] && rm -f /tmp/rabbitmq-definitions.json

        echo ""
        echo "✓ RabbitMQ definitions restored successfully"
        ;;

    *)
        echo "ERROR: Unknown database type: ${DB_TYPE}"
        exit 1
        ;;
esac

echo ""
echo "==========================================="
echo "Database restore completed"
echo "==========================================="
echo ""
echo "Next steps:"
echo "  1. Verify data integrity"
echo "  2. Test application functionality"
echo "  3. Monitor application logs"
echo ""
