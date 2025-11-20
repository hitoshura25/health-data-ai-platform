# Sealed Secrets for Health Data AI Platform

This directory contains installation and configuration for [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets), a Kubernetes controller for one-way encrypted Secrets.

## Overview

Sealed Secrets allows you to store encrypted secrets in Git repositories safely. The secrets are encrypted with a cluster-specific key, and only the Sealed Secrets controller running in your cluster can decrypt them.

**Workflow:**
1. Create a regular Kubernetes Secret locally (not committed to Git)
2. Seal it using `kubeseal` CLI (encrypted with cluster public key)
3. Commit the SealedSecret to Git (safe to store in version control)
4. Apply to cluster - controller automatically decrypts and creates regular Secret

## Prerequisites

### 1. Install kubeseal CLI

**macOS:**
```bash
brew install kubeseal
```

**Linux:**
```bash
wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.5/kubeseal-0.24.5-linux-amd64.tar.gz
tar xfz kubeseal-0.24.5-linux-amd64.tar.gz
sudo install -m 755 kubeseal /usr/local/bin/kubeseal
```

**Windows:**
Download from [GitHub Releases](https://github.com/bitnami-labs/sealed-secrets/releases)

### 2. kubectl Access

Ensure kubectl is configured to access your cluster:
```bash
kubectl cluster-info
```

## Installation

### Option 1: Helm (Recommended)

```bash
# Add Helm repository
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm repo update

# Install controller
helm install sealed-secrets sealed-secrets/sealed-secrets \
  --namespace kube-system \
  --version 2.13.2 \
  --values controller-values.yaml

# Verify installation
kubectl get pods -n kube-system -l app.kubernetes.io/name=sealed-secrets
```

### Option 2: kubectl apply

```bash
# Install controller
kubectl apply -f install-controller.yaml

# Verify installation
kubectl get pods -n sealed-secrets-system
```

## Creating Sealed Secrets

### Method 1: Using the Script (Easiest)

```bash
# Create sealed secret for Health API
./create-sealed-secret.sh health-api health-api

# Create sealed secret for ETL Engine
./create-sealed-secret.sh etl-engine health-etl

# Create sealed secret for WebAuthn
./create-sealed-secret.sh webauthn health-auth
```

The script will:
1. Prompt for secret values interactively
2. Create a temporary regular Secret
3. Seal it using kubeseal
4. Save the sealed secret to a file
5. Clean up temporary files

### Method 2: Manual Creation

```bash
# 1. Create a regular secret (DO NOT commit this!)
kubectl create secret generic health-api-secrets \
  --from-literal=database-password='MySecurePassword123!' \
  --from-literal=redis-password='RedisPass456!' \
  --from-literal=minio-access-key='minioadmin' \
  --from-literal=minio-secret-key='MinioSecret789!' \
  --from-literal=rabbitmq-password='RabbitPass!' \
  --from-literal=secret-key='MySecretKeyMin32Characters!!' \
  --namespace=health-api \
  --dry-run=client -o yaml > /tmp/health-api-secrets.yaml

# 2. Seal the secret (encrypted, safe to commit)
kubeseal --format yaml < /tmp/health-api-secrets.yaml > health-api-sealed-secret.yaml

# 3. Clean up temporary file
rm /tmp/health-api-secrets.yaml

# 4. Apply sealed secret to cluster
kubectl apply -f health-api-sealed-secret.yaml

# 5. Verify the secret was created
kubectl get secrets -n health-api health-api-secrets
```

### Method 3: Using Templates

```bash
# 1. Copy template
cp templates/health-api-secret-template.yaml /tmp/health-api-secret.yaml

# 2. Edit the template and replace CHANGEME values
nano /tmp/health-api-secret.yaml

# 3. Seal it
kubeseal --format yaml < /tmp/health-api-secret.yaml > health-api-sealed-secret.yaml

# 4. Clean up and apply
rm /tmp/health-api-secret.yaml
kubectl apply -f health-api-sealed-secret.yaml
```

## Sealed Secret Example

```yaml
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: health-api-secrets
  namespace: health-api
spec:
  encryptedData:
    database-password: AgBQ8Zl... (long encrypted string)
    redis-password: AgC7P... (long encrypted string)
    minio-access-key: AgDf9... (long encrypted string)
    minio-secret-key: AgEk2... (long encrypted string)
    rabbitmq-password: AgFx5... (long encrypted string)
    secret-key: AgHm8... (long encrypted string)
  template:
    metadata:
      name: health-api-secrets
      namespace: health-api
    type: Opaque
```

## Key Management

### Backup Encryption Keys

**IMPORTANT:** Back up the encryption keys to prevent data loss!

```bash
# Backup the encryption key
kubectl get secret -n sealed-secrets-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key \
  -o yaml > sealed-secrets-key-backup.yaml

# Store this file securely (NOT in Git!)
# Options:
#   - Encrypted password manager (1Password, LastPass)
#   - Hardware security module (HSM)
#   - Cloud key management (AWS KMS, GCP KMS, Azure Key Vault)
```

### Rotate Encryption Keys

Sealed Secrets automatically generates new keys periodically (default: 30 days). Old keys are retained to decrypt existing secrets.

```bash
# Force key rotation
kubectl delete secret -n sealed-secrets-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key=active

# Controller will generate a new key automatically
# Old secrets will still work (controller keeps old keys)
# New sealed secrets will use the new key
```

### Restore from Backup

```bash
# If you need to restore keys (e.g., disaster recovery)
kubectl apply -f sealed-secrets-key-backup.yaml

# Restart controller to load the keys
kubectl rollout restart deployment/sealed-secrets-controller -n sealed-secrets-system
```

## Secret Scopes

Sealed Secrets supports three scopes:

### 1. Namespace-wide (Default)
Secret can only be decrypted in the specified namespace.
```bash
kubeseal --format yaml < secret.yaml > sealed-secret.yaml
```

### 2. Cluster-wide
Secret can be decrypted in any namespace.
```bash
kubeseal --scope cluster-wide --format yaml < secret.yaml > sealed-secret.yaml
```

### 3. Strict
Secret can only be decrypted with exact name and namespace.
```bash
kubeseal --scope strict --format yaml < secret.yaml > sealed-secret.yaml
```

**Recommendation:** Use namespace-wide scope (default) for this platform.

## Updating Secrets

To update an existing secret:

```bash
# 1. Create updated secret (with same name)
kubectl create secret generic health-api-secrets \
  --from-literal=database-password='NewPassword123!' \
  --from-literal=redis-password='NewRedisPass456!' \
  ... \
  --namespace=health-api \
  --dry-run=client -o yaml > /tmp/updated-secret.yaml

# 2. Seal it
kubeseal --format yaml < /tmp/updated-secret.yaml > health-api-sealed-secret.yaml

# 3. Apply (this will update the existing SealedSecret)
kubectl apply -f health-api-sealed-secret.yaml

# 4. Restart pods to use new secret
kubectl rollout restart deployment/health-api -n health-api
```

## Troubleshooting

### Check Controller Logs
```bash
kubectl logs -n sealed-secrets-system deployment/sealed-secrets-controller -f
```

### Verify Controller is Running
```bash
kubectl get pods -n sealed-secrets-system
```

### Test Sealing
```bash
# Create a test secret
echo -n "test-value" | kubectl create secret generic test-secret \
  --dry-run=client --from-file=key=/dev/stdin -o yaml | \
  kubeseal --format yaml > test-sealed-secret.yaml

# Apply it
kubectl apply -f test-sealed-secret.yaml -n default

# Check if it was decrypted
kubectl get secret test-secret -n default

# Clean up
kubectl delete sealedsecret test-secret -n default
```

### Common Errors

**Error: cannot fetch certificate**
```
Solution: Ensure the controller is running and accessible
kubectl get svc -n sealed-secrets-system sealed-secrets-controller
```

**Error: no key could decrypt secret**
```
Solution: The secret was sealed with a different cluster key.
Re-seal the secret with the current cluster key.
```

## Security Best Practices

1. **Never commit unsealed secrets to Git**
   - Add `*-secret.yaml` to `.gitignore` (except sealed secrets)
   - Use `.yaml` for templates, `-sealed-secret.yaml` for encrypted

2. **Backup encryption keys securely**
   - Store in encrypted password manager or HSM
   - Document restore procedures

3. **Rotate secrets regularly**
   - Database passwords: Every 90 days
   - API keys: Every 180 days
   - Encryption keys: Automatically rotated by controller

4. **Limit access to unsealed secrets**
   - Use RBAC to restrict Secret access
   - Audit secret access with Kubernetes audit logs

5. **Use strong secret values**
   - Generate with `openssl rand -base64 32`
   - Minimum 32 characters for keys
   - Use password managers to store locally

## Integration with Helm Charts

The Helm charts reference sealed secrets:

```yaml
# In deployment.yaml
env:
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: health-api-secrets  # Created by SealedSecret
      key: database-password
```

**Workflow:**
1. Install Sealed Secrets controller first
2. Create and apply SealedSecrets
3. Install Helm charts (they'll use the decrypted Secrets)

## Resources

- [Sealed Secrets GitHub](https://github.com/bitnami-labs/sealed-secrets)
- [Sealed Secrets Documentation](https://sealed-secrets.netlify.app/)
- [Kubernetes Secrets Best Practices](https://kubernetes.io/docs/concepts/security/secrets-good-practices/)
