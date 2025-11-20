#!/bin/bash
# Script to create and seal secrets for Health Data AI Platform
#
# Prerequisites:
#   - kubeseal CLI installed (brew install kubeseal or download from releases)
#   - kubectl configured to access the cluster
#   - Sealed Secrets controller deployed
#
# Usage:
#   ./create-sealed-secret.sh <service-name> <namespace>
#
# Example:
#   ./create-sealed-secret.sh health-api health-api

set -e

SERVICE_NAME=${1:-health-api}
NAMESPACE=${2:-health-api}

echo "Creating sealed secret for ${SERVICE_NAME} in namespace ${NAMESPACE}"
echo "============================================================"

# Check if kubeseal is installed
if ! command -v kubeseal &> /dev/null; then
    echo "ERROR: kubeseal CLI not found. Please install it first:"
    echo "  brew install kubeseal"
    echo "  OR download from: https://github.com/bitnami-labs/sealed-secrets/releases"
    exit 1
fi

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo "ERROR: kubectl is not configured or cluster is not accessible"
    exit 1
fi

# Create temporary directory for secrets
TMP_DIR=$(mktemp -d)
trap "rm -rf ${TMP_DIR}" EXIT

# Function to prompt for secret value
prompt_secret() {
    local key=$1
    local default=$2
    local value

    if [ -n "$default" ]; then
        read -sp "Enter value for ${key} [${default}]: " value
    else
        read -sp "Enter value for ${key}: " value
    fi
    echo

    # Use default if no value entered
    if [ -z "$value" ]; then
        value=$default
    fi

    echo -n "$value"
}

# Prompt for secret values based on service
case $SERVICE_NAME in
    health-api)
        echo "Creating secrets for Health API service"
        echo ""

        DB_PASSWORD=$(prompt_secret "database-password")
        REDIS_PASSWORD=$(prompt_secret "redis-password")
        MINIO_ACCESS_KEY=$(prompt_secret "minio-access-key" "minioadmin")
        MINIO_SECRET_KEY=$(prompt_secret "minio-secret-key")
        RABBITMQ_PASSWORD=$(prompt_secret "rabbitmq-password")
        SECRET_KEY=$(prompt_secret "secret-key" "$(openssl rand -base64 32)")

        # Create regular secret
        kubectl create secret generic ${SERVICE_NAME}-secrets \
            --from-literal=database-password="${DB_PASSWORD}" \
            --from-literal=redis-password="${REDIS_PASSWORD}" \
            --from-literal=minio-access-key="${MINIO_ACCESS_KEY}" \
            --from-literal=minio-secret-key="${MINIO_SECRET_KEY}" \
            --from-literal=rabbitmq-password="${RABBITMQ_PASSWORD}" \
            --from-literal=secret-key="${SECRET_KEY}" \
            --namespace=${NAMESPACE} \
            --dry-run=client -o yaml > ${TMP_DIR}/secret.yaml
        ;;

    etl-engine)
        echo "Creating secrets for ETL Narrative Engine"
        echo ""

        DB_PASSWORD=$(prompt_secret "database-password")
        MINIO_ACCESS_KEY=$(prompt_secret "minio-access-key" "minioadmin")
        MINIO_SECRET_KEY=$(prompt_secret "minio-secret-key")
        RABBITMQ_USER=$(prompt_secret "rabbitmq-user" "user")
        RABBITMQ_PASSWORD=$(prompt_secret "rabbitmq-password")

        kubectl create secret generic ${SERVICE_NAME}-secrets \
            --from-literal=database-password="${DB_PASSWORD}" \
            --from-literal=minio-access-key="${MINIO_ACCESS_KEY}" \
            --from-literal=minio-secret-key="${MINIO_SECRET_KEY}" \
            --from-literal=rabbitmq-user="${RABBITMQ_USER}" \
            --from-literal=rabbitmq-password="${RABBITMQ_PASSWORD}" \
            --namespace=${NAMESPACE} \
            --dry-run=client -o yaml > ${TMP_DIR}/secret.yaml
        ;;

    webauthn)
        echo "Creating secrets for WebAuthn service"
        echo ""

        DB_PASSWORD=$(prompt_secret "database-password")
        REDIS_PASSWORD=$(prompt_secret "redis-password")
        JWT_MASTER_KEY=$(prompt_secret "jwt-master-key" "$(openssl rand -base64 32)")

        kubectl create secret generic webauthn-secrets \
            --from-literal=database-password="${DB_PASSWORD}" \
            --from-literal=redis-password="${REDIS_PASSWORD}" \
            --from-literal=jwt-master-key="${JWT_MASTER_KEY}" \
            --namespace=${NAMESPACE} \
            --dry-run=client -o yaml > ${TMP_DIR}/secret.yaml
        ;;

    *)
        echo "ERROR: Unknown service name: ${SERVICE_NAME}"
        echo "Supported services: health-api, etl-engine, webauthn"
        exit 1
        ;;
esac

# Seal the secret
echo ""
echo "Sealing secret..."
kubeseal --format yaml < ${TMP_DIR}/secret.yaml > ${SERVICE_NAME}-sealed-secret.yaml

echo ""
echo "✅ Sealed secret created: ${SERVICE_NAME}-sealed-secret.yaml"
echo ""
echo "Next steps:"
echo "  1. Review the sealed secret file"
echo "  2. Commit it to Git (it's encrypted and safe to commit)"
echo "  3. Apply it to the cluster:"
echo "     kubectl apply -f ${SERVICE_NAME}-sealed-secret.yaml"
echo ""
echo "The Sealed Secrets controller will automatically decrypt it and create"
echo "a regular Secret that your application can use."
