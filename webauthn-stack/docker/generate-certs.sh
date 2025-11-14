#!/bin/bash
set -e

# Generate mTLS Certificates for WebAuthn Zero-Trust Stack
# This script creates self-signed certificates for Envoy Gateway and service sidecars
# Used in CI/CD and local development environments

CERTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/certs"

echo "========================================"
echo "Generating mTLS Certificates"
echo "========================================"

# Create certs directory if it doesn't exist
mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

# Step 1: Generate CA (Certificate Authority)
echo ""
echo "Step 1: Generating CA certificate..."
if [ ! -f ca-cert.pem ]; then
    # Generate CA private key
    openssl genrsa -out ca-key.pem 2048

    # Generate CA certificate (self-signed, valid for 365 days)
    openssl req -x509 -new -nodes \
        -key ca-key.pem \
        -sha256 \
        -days 365 \
        -out ca-cert.pem \
        -subj "/CN=WebAuthn-CA/O=Health-Data-AI-Platform/C=US"

    echo "✅ CA certificate generated"
else
    echo "ℹ️  CA certificate already exists, skipping"
fi

# Step 2: Generate Gateway Certificate
echo ""
echo "Step 2: Generating Gateway certificate..."
if [ ! -f gateway-cert.pem ]; then
    # Generate gateway private key
    openssl genrsa -out gateway-key.pem 2048

    # Generate gateway CSR (Certificate Signing Request)
    openssl req -new \
        -key gateway-key.pem \
        -out gateway-csr.pem \
        -subj "/CN=envoy-gateway/O=Health-Data-AI-Platform/C=US"

    # Sign gateway certificate with CA
    openssl x509 -req \
        -in gateway-csr.pem \
        -CA ca-cert.pem \
        -CAkey ca-key.pem \
        -CAcreateserial \
        -out gateway-cert.pem \
        -days 365 \
        -sha256

    echo "✅ Gateway certificate generated"
else
    echo "ℹ️  Gateway certificate already exists, skipping"
fi

# Step 3: Generate Service Certificate (for example-service sidecar)
echo ""
echo "Step 3: Generating Service certificate..."
if [ ! -f service-cert.pem ]; then
    # Generate service private key
    openssl genrsa -out service-key.pem 2048

    # Generate service CSR
    openssl req -new \
        -key service-key.pem \
        -out service-csr.pem \
        -subj "/CN=example-service/O=Health-Data-AI-Platform/C=US"

    # Sign service certificate with CA
    openssl x509 -req \
        -in service-csr.pem \
        -CA ca-cert.pem \
        -CAkey ca-key.pem \
        -CAcreateserial \
        -out service-cert.pem \
        -days 365 \
        -sha256

    echo "✅ Service certificate generated"
else
    echo "ℹ️  Service certificate already exists, skipping"
fi

# Step 4: Set proper permissions
# Note: Using 644 for all files (including private keys) for CI compatibility
# These are development/test certificates only, not production secrets
echo ""
echo "Step 4: Setting permissions..."
chmod 644 ca-cert.pem ca-key.pem
chmod 644 gateway-cert.pem gateway-csr.pem gateway-key.pem
chmod 644 service-cert.pem service-csr.pem service-key.pem
echo "✅ Permissions set (644 for all certificates - CI compatible)"

# Step 5: Verification
echo ""
echo "========================================"
echo "Certificate Generation Complete"
echo "========================================"
echo ""
echo "Generated certificates:"
ls -lh ca-cert.pem ca-key.pem gateway-cert.pem gateway-key.pem service-cert.pem service-key.pem 2>/dev/null || true

echo ""
echo "Certificate details:"
echo "  - CA: $(openssl x509 -in ca-cert.pem -noout -subject -dates | head -2)"
echo "  - Gateway: $(openssl x509 -in gateway-cert.pem -noout -subject -dates | head -2)"
echo "  - Service: $(openssl x509 -in service-cert.pem -noout -subject -dates | head -2)"

echo ""
echo "✅ All certificates generated and verified"
echo "   Certificates are valid for 365 days"
