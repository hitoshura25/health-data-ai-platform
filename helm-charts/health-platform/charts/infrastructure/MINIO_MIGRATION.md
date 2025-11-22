# MinIO Helm Chart Migration Guide: v12.11.3 → v17.0.21

## Overview

This guide documents the migration from MinIO Helm chart version 12.11.3 to 17.0.21. This is a **major version upgrade** spanning 4 major versions and includes breaking changes that require careful planning and testing.

## Breaking Changes

### 1. Ingress Configuration Restructuring

**Before (v12.x):**
```yaml
minio:
  ingress:
    enabled: true
    hostname: minio.example.com
```

**After (v17.x):**
```yaml
minio:
  # API ingress (MinIO S3 API)
  ingress:
    enabled: true
    hostname: minio-api.example.com

  # Console ingress (MinIO web console)
  console:
    ingress:
      enabled: true
      hostname: minio-console.example.com
```

**Impact:** The MinIO console now has a separate ingress configuration from the API, allowing independent access control and routing.

### 2. Authentication Mechanism Updates

**Changes:**
- Updated credential management structure
- Enhanced support for external secret providers
- New LDAP/AD integration options

**Action Required:**
- Verify existing credentials still work after upgrade
- Test authentication flows for all service accounts
- Review RBAC policies if using MinIO policy engine

### 3. API Compatibility

**Changes:**
- S3 API compatibility improvements
- New lifecycle management features
- Enhanced versioning capabilities

**Action Required:**
- Test all existing S3 API calls from applications
- Verify lifecycle policies are applied correctly
- Ensure data integrity with checksums

### 4. Storage Format

**Changes:**
- Erasure coding improvements
- Metadata format updates
- Optimized storage layout

**Action Required:**
- Existing data is compatible (in-place upgrade supported)
- New data will use optimized format
- No migration of existing data required

## Pre-Migration Checklist

### 1. Backup Current Data

**Critical:** Always backup before major version upgrades.

```bash
# Option 1: Use Velero for Kubernetes backup
velero backup create minio-pre-upgrade \
  --include-namespaces health-data \
  --include-resources persistentvolumeclaims,persistentvolumes

# Option 2: Use MinIO mc mirror
mc alias set current http://minio.example.com:9000 ACCESS_KEY SECRET_KEY
mc mirror current/data-lake /backup/data-lake-$(date +%Y%m%d)

# Option 3: Create volume snapshot (if supported by storage provider)
kubectl get pvc -n health-data
# Use your cloud provider's snapshot tool
```

### 2. Document Current Configuration

```bash
# Export current Helm values
helm get values health-platform -n health-data > current-values.yaml

# List all MinIO buckets
mc ls current/

# Export MinIO policies
mc admin policy list current

# Export MinIO users/service accounts
mc admin user list current
```

### 3. Test Migration in Non-Production Environment

**Required:** Test the upgrade in development/staging first.

```bash
# Deploy to dev environment first
helm upgrade health-platform ./helm-charts/health-platform \
  --namespace health-data-dev \
  --values values-dev.yaml \
  --dry-run --debug
```

## Migration Steps

### Step 1: Update Helm Dependencies

```bash
cd helm-charts/health-platform/charts/infrastructure

# Update Chart.yaml with new MinIO version
# (Already done: 17.0.21)

# Update dependencies
helm dependency update
```

### Step 2: Update Configuration Values

**Review and update the following in your values file:**

```yaml
infrastructure:
  minio:
    # Update ingress configuration (BREAKING CHANGE)
    ingress:
      enabled: true
      hostname: minio-api.example.com  # API endpoint
      annotations:
        cert-manager.io/cluster-issuer: letsencrypt-prod

    # NEW: Separate console ingress
    console:
      ingress:
        enabled: true
        hostname: minio-console.example.com  # Web console
        annotations:
          cert-manager.io/cluster-issuer: letsencrypt-prod

    # Existing configuration (no changes required)
    mode: standalone
    persistence:
      enabled: true
      size: 80Gi

    resources:
      requests:
        cpu: 200m
        memory: 512Mi
      limits:
        cpu: 400m
        memory: 1Gi

    # Credentials (unchanged)
    auth:
      rootUser: admin
      rootPassword: "CHANGE_ME"  # Use sealed secrets in production
```

### Step 3: Perform Upgrade

**Development Environment:**

```bash
# 1. Backup (already done in pre-migration)

# 2. Perform upgrade
helm upgrade health-platform ./helm-charts/health-platform \
  --namespace health-data-dev \
  --values values-dev.yaml \
  --timeout 10m

# 3. Monitor rollout
kubectl rollout status statefulset/minio -n health-data-dev

# 4. Verify pods are running
kubectl get pods -n health-data-dev -l app.kubernetes.io/name=minio
```

**Production Environment:**

```bash
# 1. Create production backup
velero backup create minio-production-pre-upgrade \
  --include-namespaces health-data \
  --wait

# 2. Scale down applications using MinIO (optional, reduces risk)
kubectl scale deployment health-api -n health-data --replicas=0
kubectl scale deployment etl-engine -n health-data --replicas=0

# 3. Perform upgrade with extra caution
helm upgrade health-platform ./helm-charts/health-platform \
  --namespace health-data \
  --values values-production.yaml \
  --timeout 15m \
  --wait

# 4. Monitor upgrade
kubectl rollout status statefulset/minio -n health-data -w

# 5. Verify MinIO is healthy
kubectl exec -n health-data minio-0 -- mc admin info local

# 6. Scale applications back up
kubectl scale deployment health-api -n health-data --replicas=2
kubectl scale deployment etl-engine -n health-data --replicas=1
```

## Post-Migration Verification

### 1. MinIO Service Health

```bash
# Check pods are running
kubectl get pods -n health-data -l app.kubernetes.io/name=minio

# Check MinIO server status
kubectl exec -n health-data minio-0 -- mc admin info local

# Verify storage capacity
kubectl exec -n health-data minio-0 -- mc admin info local | grep Storage
```

### 2. API Endpoint Connectivity

```bash
# Test S3 API access
mc alias set upgraded https://minio-api.example.com ACCESS_KEY SECRET_KEY
mc ls upgraded/

# Verify bucket access
mc ls upgraded/data-lake/

# Test object upload/download
echo "test" > test.txt
mc cp test.txt upgraded/data-lake/test/
mc cat upgraded/data-lake/test/test.txt
mc rm upgraded/data-lake/test/test.txt
```

### 3. Console Access

```bash
# Open browser to console URL
open https://minio-console.example.com

# Verify:
# - Login works with root credentials
# - Dashboard displays correctly
# - Buckets are visible
# - Monitoring metrics are available
```

### 4. Application Integration Testing

```bash
# Test data-lake service
kubectl logs -n health-data -l app=data-lake --tail=100

# Test health-api uploads (if deployed)
# POST test file to /api/v1/upload endpoint

# Verify ETL engine can read from data lake
kubectl logs -n health-data -l app=etl-engine --tail=100
```

### 5. Backup/Restore Validation

```bash
# Test backup
velero backup create minio-post-upgrade \
  --include-namespaces health-data \
  --wait

# Test restore to different namespace (non-destructive)
velero restore create test-restore \
  --from-backup minio-post-upgrade \
  --namespace-mappings health-data:health-data-test

# Verify restored data
kubectl exec -n health-data-test minio-0 -- mc ls local/
```

## Rollback Procedure

If the upgrade fails or causes issues, follow this rollback procedure:

### Option 1: Helm Rollback (Preferred)

```bash
# 1. Rollback Helm release
helm rollback health-platform -n health-data

# 2. Wait for rollout to complete
kubectl rollout status statefulset/minio -n health-data

# 3. Verify service is healthy
kubectl exec -n health-data minio-0 -- mc admin info local
```

### Option 2: Restore from Velero Backup

```bash
# 1. Delete current MinIO deployment
helm delete health-platform -n health-data --no-hooks

# 2. Restore from backup
velero restore create minio-rollback \
  --from-backup minio-pre-upgrade \
  --wait

# 3. Reinstall with old chart version
cd helm-charts/health-platform
helm install health-platform . \
  --namespace health-data \
  --values values-production.yaml
```

### Option 3: Restore from Data Backup

```bash
# If Helm/Velero rollback fails, restore data manually

# 1. Deploy fresh MinIO instance (old version)
# Update Chart.yaml to use MinIO 12.11.3
helm dependency update
helm install health-platform-recovery ./helm-charts/health-platform \
  --namespace health-data-recovery \
  --values values-production.yaml

# 2. Restore data from mc mirror backup
mc alias set recovery http://minio.health-data-recovery:9000 ACCESS_KEY SECRET_KEY
mc mirror /backup/data-lake-20241122 recovery/data-lake

# 3. Verify data integrity
mc ls recovery/data-lake/
```

## Troubleshooting

### Issue: Pods in CrashLoopBackOff

**Symptoms:**
```bash
kubectl get pods -n health-data
# minio-0   0/1   CrashLoopBackOff
```

**Solutions:**
```bash
# Check logs
kubectl logs -n health-data minio-0

# Common causes:
# 1. PVC not bound (check storage class)
kubectl get pvc -n health-data

# 2. Insufficient resources
kubectl describe pod -n health-data minio-0 | grep -A 10 Events

# 3. Invalid credentials
kubectl get secret -n health-data minio
kubectl describe secret -n health-data minio
```

### Issue: Ingress Not Working

**Symptoms:**
- Cannot access MinIO console or API
- 404 or 502 errors

**Solutions:**
```bash
# Check ingress resources
kubectl get ingress -n health-data

# Verify ingress controller
kubectl get pods -n ingress-nginx

# Check cert-manager certificates
kubectl get certificate -n health-data

# Test internal service access
kubectl port-forward -n health-data svc/minio 9000:9000
# Access http://localhost:9000 in browser
```

### Issue: Data Not Accessible After Upgrade

**Symptoms:**
- Buckets appear empty
- Objects not found

**Solutions:**
```bash
# Verify PVC is still bound
kubectl get pvc -n health-data

# Check if data exists on volume
kubectl exec -n health-data minio-0 -- ls -la /data

# Verify bucket policies
kubectl exec -n health-data minio-0 -- mc admin policy list local

# Check MinIO logs for errors
kubectl logs -n health-data minio-0 --tail=500 | grep -i error
```

## Configuration Changes Reference

### Helm Values Changes

| Configuration Path | v12.11.3 | v17.0.21 | Notes |
|-------------------|----------|----------|-------|
| `ingress.enabled` | ✅ | ✅ | Now for API only |
| `ingress.hostname` | ✅ | ✅ | API endpoint |
| `console.ingress.enabled` | ❌ | ✅ | **NEW:** Separate console ingress |
| `console.ingress.hostname` | ❌ | ✅ | **NEW:** Console endpoint |
| `auth.rootUser` | ✅ | ✅ | Unchanged |
| `auth.rootPassword` | ✅ | ✅ | Unchanged |
| `persistence.enabled` | ✅ | ✅ | Unchanged |
| `persistence.size` | ✅ | ✅ | Unchanged |
| `resources` | ✅ | ✅ | Unchanged |
| `mode` | ✅ | ✅ | Unchanged (standalone/distributed) |

### API Endpoint Changes

| Endpoint | v12.11.3 | v17.0.21 | Notes |
|----------|----------|----------|-------|
| S3 API | `http://minio:9000` | `http://minio:9000` | Unchanged |
| Console | `http://minio:9000` | `http://minio:9001` | Now separate port |
| Ingress API | `https://minio.example.com` | `https://minio-api.example.com` | Recommend separate hostname |
| Ingress Console | N/A | `https://minio-console.example.com` | **NEW:** Dedicated console ingress |

## Best Practices

1. **Always test in non-production first**
   - Deploy to dev/staging environments
   - Run full integration test suite
   - Verify all application workflows

2. **Backup before upgrade**
   - Use Velero for Kubernetes resources
   - Use `mc mirror` for data backup
   - Document current configuration

3. **Monitor during upgrade**
   - Watch pod logs in real-time
   - Monitor resource usage
   - Check for error messages

4. **Validate after upgrade**
   - Test all API endpoints
   - Verify console access
   - Run application integration tests
   - Validate backup/restore procedures

5. **Plan rollback strategy**
   - Have rollback procedure documented
   - Test rollback in staging
   - Keep backups for 30+ days

## Support and Resources

- **MinIO Helm Chart:** https://github.com/bitnami/charts/tree/main/bitnami/minio
- **MinIO Documentation:** https://min.io/docs/minio/kubernetes/upstream/
- **Bitnami Chart Upgrade Guide:** https://docs.bitnami.com/kubernetes/infrastructure/minio/administration/upgrade/
- **Project Issues:** https://github.com/hitoshura25/health-data-ai-platform/issues

---

**Last Updated:** 2025-11-22
**Chart Version:** 17.0.21
**MinIO Version:** 2024.x
**Maintained By:** Health Data AI Platform Team
