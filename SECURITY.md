# Security Architecture - Health Data AI Platform

This document describes the security architecture and implementation for the Health Data AI Platform Kubernetes deployment.

## Table of Contents

1. [Security Overview](#security-overview)
2. [Network Security](#network-security)
3. [Access Control (RBAC)](#access-control-rbac)
4. [Pod Security Standards](#pod-security-standards)
5. [Secrets Management](#secrets-management)
6. [Security Verification](#security-verification)
7. [Security Checklist](#security-checklist)
8. [Incident Response](#incident-response)

---

## Security Overview

The Health Data AI Platform implements defense-in-depth security with multiple layers:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Network Policies (Network Segmentation)            │
│  - Default deny all traffic                                 │
│  - Explicit allow rules for service communication           │
│  - Namespace isolation                                      │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: RBAC (Role-Based Access Control)                  │
│  - ServiceAccounts for each service                         │
│  - Least privilege Roles and RoleBindings                   │
│  - ClusterRoles for monitoring                              │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Pod Security Standards                             │
│  - Restricted profile enforcement                           │
│  - Non-root containers                                      │
│  - Read-only root filesystems                               │
│  - Capability dropping                                      │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Secrets Management                                 │
│  - Sealed Secrets for encryption at rest                    │
│  - No plaintext secrets in Git                              │
│  - Automatic key rotation                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Network Security

### Architecture

Network policies implement zero-trust networking with default deny and explicit allow rules.

**Namespaces:**
- `health-data`: Infrastructure (PostgreSQL, Redis, MinIO, RabbitMQ)
- `health-auth`: Authentication (WebAuthn, Envoy)
- `health-api`: Health API service
- `health-etl`: ETL Narrative Engine
- `health-observability`: Monitoring (Prometheus, Grafana, Jaeger, Loki)

### Network Policy Rules

#### Default Deny All
Every namespace has a default deny policy that blocks all ingress and egress traffic.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: health-data
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

#### DNS Access
All namespaces allow DNS queries to kube-system.

#### Service Communication Matrix

| Source Namespace | Target Namespace | Target Service | Port | Purpose |
|-----------------|------------------|----------------|------|---------|
| health-api | health-data | postgresql-health | 5432 | Database access |
| health-api | health-data | redis-health | 6379 | Rate limiting |
| health-api | health-data | minio | 9000 | Object storage |
| health-api | health-data | rabbitmq | 5672 | Message publishing |
| health-api | health-auth | webauthn-server | 8080 | JWT verification |
| health-api | health-observability | jaeger | 4317 | Distributed tracing |
| health-etl | health-data | postgresql-health | 5432 | Database access |
| health-etl | health-data | minio | 9000 | Object storage |
| health-etl | health-data | rabbitmq | 5672 | Message consumption |
| health-etl | health-observability | jaeger | 4317 | Distributed tracing |
| health-auth | health-data | postgresql-auth | 5432 | Auth database |
| health-auth | health-data | redis-auth | 6379 | Session storage |
| health-observability | * | * | * | Metrics scraping |

### Testing Network Policies

```bash
# Test allowed connection (should succeed)
kubectl exec -it deployment/health-api -n health-api -- \
  nc -zv postgresql-health.health-data.svc.cluster.local 5432

# Test blocked connection (should timeout)
kubectl exec -it deployment/health-api -n health-api -- \
  nc -zv postgresql-auth.health-data.svc.cluster.local 5432
```

---

## Access Control (RBAC)

### ServiceAccounts

Each service runs with its own ServiceAccount following the principle of least privilege.

**ServiceAccounts:**
- `health-api-sa` (health-api namespace)
- `etl-engine-sa` (health-etl namespace)
- `webauthn-sa` (health-auth namespace)
- `envoy-sa` (health-auth namespace)
- `prometheus-sa` (health-observability namespace)

### Roles and Permissions

#### Health API Role
```yaml
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["health-api-secrets"]
  verbs: ["get"]
- apiGroups: [""]
  resources: ["configmaps"]
  resourceNames: ["health-api-config"]
  verbs: ["get"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
```

#### ETL Engine Role
```yaml
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["etl-engine-secrets"]
  verbs: ["get"]
- apiGroups: [""]
  resources: ["configmaps"]
  resourceNames: ["etl-engine-config"]
  verbs: ["get"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
```

#### Prometheus Monitoring ClusterRole
```yaml
rules:
- apiGroups: ["monitoring.coreos.com"]
  resources: ["servicemonitors", "podmonitors"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["services", "endpoints", "pods"]
  verbs: ["get", "list", "watch"]
```

### Human User Roles

#### Developer Role (Read-Only)
```bash
# Bind developer role to user
kubectl create clusterrolebinding developer-binding \
  --clusterrole=health-platform-developer \
  --user=developer@example.com
```

Permissions:
- View pods, logs, services, configmaps
- View deployments, replicasets, statefulsets
- View ingresses, network policies
- View metrics and monitoring resources

#### Operator Role (Full Access)
```bash
# Bind operator role to user
kubectl create clusterrolebinding operator-binding \
  --clusterrole=health-platform-operator \
  --user=operator@example.com
```

Permissions:
- Full access to all resources in application namespaces
- **Note:** Should be restricted to specific namespaces in production

### Testing RBAC

```bash
# Test ServiceAccount permissions
kubectl auth can-i get secrets \
  --as=system:serviceaccount:health-api:health-api-sa \
  -n health-api

# Test user permissions
kubectl auth can-i delete pods \
  --as=developer@example.com \
  -n health-api
```

---

## Pod Security Standards

### Enforcement Levels

| Namespace | Pod Security Level | Justification |
|-----------|-------------------|---------------|
| health-api | restricted | Application service - highest security |
| health-etl | restricted | Application service - highest security |
| health-auth | restricted | Authentication service - highest security |
| health-data | baseline | Stateful services need some privileges |
| health-observability | baseline | Monitoring tools need some privileges |

### Restricted Profile Requirements

All application pods (health-api, health-etl, health-auth) must comply with:

#### Pod-level Security Context
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
```

#### Container-level Security Context
```yaml
securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
```

### Writable Directories

Services with read-only root filesystems use `emptyDir` volumes for writable directories:

```yaml
volumeMounts:
- name: tmp
  mountPath: /tmp
- name: cache
  mountPath: /app/.cache

volumes:
- name: tmp
  emptyDir: {}
- name: cache
  emptyDir: {}
```

### Verification

```bash
# Check namespace labels
kubectl get namespace health-api -o yaml | grep pod-security

# Check pod security context
kubectl get pod <pod-name> -n health-api -o jsonpath='{.spec.securityContext}'

# Check container security context
kubectl get pod <pod-name> -n health-api \
  -o jsonpath='{.spec.containers[0].securityContext}'
```

---

## Secrets Management

### Sealed Secrets

The platform uses [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) for encrypted secrets in Git.

**Workflow:**
1. Create regular Kubernetes Secret locally
2. Seal with `kubeseal` CLI (encrypted)
3. Commit SealedSecret to Git (safe)
4. Controller decrypts in cluster

### Installation

```bash
# Install Sealed Secrets controller
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets \
  --namespace kube-system \
  --values sealed-secrets/controller-values.yaml
```

See [`sealed-secrets/README.md`](sealed-secrets/README.md) for detailed instructions.

### Secret Types

| Secret Name | Namespace | Purpose | Keys |
|------------|-----------|---------|------|
| health-api-secrets | health-api | API service credentials | database-password, redis-password, minio-access-key, minio-secret-key, rabbitmq-password, secret-key |
| etl-engine-secrets | health-etl | ETL service credentials | database-password, minio-access-key, minio-secret-key, rabbitmq-user, rabbitmq-password |
| webauthn-secrets | health-auth | Auth service credentials | database-password, redis-password, jwt-master-key |

### Secret Rotation

**Schedule:**
- Database passwords: Every 90 days
- API keys: Every 180 days
- JWT master key: Every 365 days
- Sealed Secrets keys: Automatic (controller manages)

**Process:**
1. Generate new secret values
2. Create new SealedSecret
3. Apply to cluster
4. Restart affected pods
5. Verify services are healthy
6. Remove old secrets

### Backup

```bash
# Backup Sealed Secrets encryption keys
kubectl get secret -n sealed-secrets-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key \
  -o yaml > sealed-secrets-key-backup.yaml

# Store securely (NOT in Git!)
```

---

## Security Verification

### Network Policy Verification

```bash
# List all network policies
kubectl get networkpolicies -A

# Verify health-api can reach PostgreSQL
kubectl exec -it deployment/health-api -n health-api -- \
  nc -zv postgresql-health.health-data.svc.cluster.local 5432

# Verify health-api CANNOT reach PostgreSQL Auth (should timeout)
kubectl exec -it deployment/health-api -n health-api -- \
  timeout 5 nc -zv postgresql-auth.health-data.svc.cluster.local 5432
```

### RBAC Verification

```bash
# Check ServiceAccount can read its secret
kubectl auth can-i get secrets \
  --as=system:serviceaccount:health-api:health-api-sa \
  --namespace=health-api

# Check ServiceAccount CANNOT delete pods
kubectl auth can-i delete pods \
  --as=system:serviceaccount:health-api:health-api-sa \
  --namespace=health-api
```

### Pod Security Verification

```bash
# Check namespace labels
kubectl get namespace health-api -o yaml | grep pod-security

# Check all pods comply
kubectl get pods -n health-api -o json | jq '.items[] | {
  name: .metadata.name,
  runAsNonRoot: .spec.securityContext.runAsNonRoot,
  runAsUser: .spec.securityContext.runAsUser,
  readOnlyRootFilesystem: .spec.containers[0].securityContext.readOnlyRootFilesystem
}'
```

### Sealed Secrets Verification

```bash
# Check controller is running
kubectl get pods -n sealed-secrets-system

# Check SealedSecrets exist
kubectl get sealedsecrets -A

# Check regular Secrets were created
kubectl get secrets -n health-api health-api-secrets
```

---

## Security Checklist

### Pre-Deployment

- [ ] Sealed Secrets controller installed
- [ ] Encryption keys backed up securely
- [ ] SealedSecrets created for all services
- [ ] Network policies reviewed and tested
- [ ] RBAC roles defined with least privilege
- [ ] Pod Security Standards configured

### Post-Deployment

- [ ] All pods running with non-root users
- [ ] Read-only root filesystems enabled
- [ ] NetworkPolicies applied to all namespaces
- [ ] ServiceAccounts assigned to all pods
- [ ] Secrets encrypted with Sealed Secrets
- [ ] No plaintext secrets in Git
- [ ] Monitoring and alerting configured

### Ongoing

- [ ] Review audit logs weekly
- [ ] Rotate secrets quarterly
- [ ] Update container images monthly
- [ ] Scan for vulnerabilities weekly
- [ ] Review network policies quarterly
- [ ] Update RBAC policies as needed

---

## Incident Response

### Security Event Detection

**Monitoring:**
- Kubernetes audit logs
- Network policy violations
- Failed authentication attempts
- Unauthorized secret access
- Privilege escalation attempts

**Alerts:**
- Pod security violations
- Network policy denies
- RBAC access denials
- Secret access patterns
- Anomalous resource usage

### Incident Response Process

1. **Detection & Analysis**
   ```bash
   # Check audit logs
   kubectl logs -n kube-system kube-apiserver-* | grep "audit"

   # Check network policy denies
   kubectl logs -n health-system -l app=network-policy-controller

   # Check RBAC denials
   kubectl logs -n kube-system kube-apiserver-* | grep "Forbidden"
   ```

2. **Containment**
   ```bash
   # Isolate compromised pod
   kubectl label pod <pod-name> security-quarantine=true -n <namespace>

   # Apply strict network policy
   kubectl apply -f emergency-network-policy.yaml

   # Revoke ServiceAccount permissions
   kubectl delete rolebinding <binding-name> -n <namespace>
   ```

3. **Eradication**
   ```bash
   # Delete compromised resources
   kubectl delete pod <pod-name> -n <namespace>

   # Rotate secrets
   ./sealed-secrets/create-sealed-secret.sh <service> <namespace>

   # Update images
   kubectl set image deployment/<deployment> <container>=<new-image>
   ```

4. **Recovery**
   ```bash
   # Restore from backups if needed
   helm rollback <release> <revision>

   # Verify services are healthy
   kubectl get pods -A
   kubectl get events -A --sort-by='.lastTimestamp'
   ```

5. **Lessons Learned**
   - Document the incident
   - Update security policies
   - Improve detection mechanisms
   - Conduct team review

### Emergency Contacts

- **Security Lead:** [security@example.com]
- **Platform Team:** [platform@example.com]
- **On-Call Rotation:** [oncall@example.com]

---

## Security Resources

### Internal Documentation
- [Sealed Secrets README](sealed-secrets/README.md)
- [Network Policies Spec](specs/kubernetes-implementation-modules/security-module.md)
- [RBAC Configuration](helm-charts/health-platform/charts/security/)

### External Resources
- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Network Policies Documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [RBAC Best Practices](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)

### Compliance
- **HIPAA:** Health data encryption, access controls, audit logging
- **GDPR:** Data protection, right to erasure, access logging
- **SOC 2:** Security monitoring, incident response, change management

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-11-20 | Initial security architecture implemented | Platform Team |
| | Module 6 (Security & RBAC) completed | |
| | NetworkPolicies, RBAC, PSS, Sealed Secrets | |

---

**Last Updated:** 2025-11-20
**Version:** 1.0.0
**Status:** Production Ready
